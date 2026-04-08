import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.assignment_store import (
    fetch_latest_assignment,
    incident_assignments_table_available,
    record_assignment,
)
from app.services.clustering import haversine_km
from app.services.rescue_allocator import calculate_eta_minutes
from app.services.responder_utils import safe_responder_update
from app.supabase_client import supabase_admin

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentStatusRequest(BaseModel):
    status: str
    note: str | None = None


class IncidentAssignRequest(BaseModel):
    responder_id: str
    assigned_by: str
    note: str | None = None


def _get_responder(responder_id: str) -> Dict[str, Any] | None:
    res = supabase_admin.table("responders").select("*").eq("id", responder_id).single().execute()
    return res.data if res.data else None


def _build_incident_summary(incident: Dict[str, Any]) -> Dict[str, Any]:
    if incident.get("status") == "resolved":
        status = "resolved"
    else:
        status = incident.get("status", "pending")

    assignment = fetch_latest_assignment(incident["id"])
    responder_payload = None
    eta_minutes = None
    next_poll = None

    if assignment:
        eta_minutes = assignment.get("eta_minutes")
        responder_data = _get_responder(assignment["responder_id"])
        responder_payload = {
            "id": assignment["responder_id"],
            "name": responder_data.get("name") if responder_data else "Responder",
            "type": responder_data.get("type") if responder_data else "ambulance",
            "eta_minutes": eta_minutes,
        }
        status = "assigned"
    else:
        next_poll = 15
        status = status if status != "resolved" else "resolved"

    priority = (
        "high"
        if incident.get("status") in ("assigned", "escalated")
        else "medium"
    )

    return {
        "incident_id": incident["id"],
        "type": incident.get("type"),
        "status": status,
        "priority": priority,
        "latitude": incident.get("latitude"),
        "longitude": incident.get("longitude"),
        "created_at": incident.get("created_at"),
        "updated_at": incident.get("updated_at"),
        "responder": responder_payload,
        "eta_minutes": eta_minutes,
        "next_poll_after_seconds": next_poll,
    }


@router.get("/live")
def live_incidents(limit: int = 20, user_id: str | None = None, incident_id: str | None = None) -> List[dict]:
    try:
        query = supabase_admin.table("incidents").select("*").order("created_at", desc=True).limit(limit)
        if user_id:
            query = query.eq("user_id", user_id)
        if incident_id:
            query = query.eq("id", incident_id)

        incidents = query.execute().data or []

        return [
            summary
            for summary in (
                _build_incident_summary(incident) for incident in incidents
            )
            if summary["status"] != "resolved"
        ]
    except Exception:
        logging.exception("failed to fetch live incidents")
        raise HTTPException(status_code=500, detail="Unable to fetch live incidents right now")


@router.patch("/{incident_id}/status")
def update_incident_status(incident_id: str, body: IncidentStatusRequest):
    allowed = {"pending", "assigned", "resolved", "escalated"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status")
    supabase_admin.table("incidents").update({"status": body.status}).eq("id", incident_id).execute()
    return {"message": "Incident status updated"}


@router.post("/{incident_id}/assign")
def assign_responder(incident_id: str, body: IncidentAssignRequest):
    incident_res = supabase_admin.table("incidents").select("*").eq("id", incident_id).single().execute()
    if not incident_res.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    responder_res = supabase_admin.table("responders").select("*").eq("id", body.responder_id).single().execute()
    if not responder_res.data:
        raise HTTPException(status_code=404, detail="Responder not found")

    incident = incident_res.data
    responder = responder_res.data
    distance = haversine_km(incident["latitude"], incident["longitude"], responder["latitude"], responder["longitude"])
    eta = calculate_eta_minutes(distance)
    now_iso = datetime.now(timezone.utc).isoformat()

    safe_responder_update(body.responder_id, {
        "availability": "en_route",
        "current_status": f"Heading to incident {incident_id[:8]}",
        "eta_minutes": eta,
        "updated_at": now_iso,
    })

    existing = fetch_latest_assignment(incident_id)
    assignments_table_ready = incident_assignments_table_available()

    if existing and existing.get("responder_id") == body.responder_id:
        if assignments_table_ready:
            supabase_admin.table("incident_assignments").update({
                "status": "assigned",
                "eta_minutes": eta,
                "note": body.note,
            }).eq("id", existing["id"]).execute()
        else:
            supabase_admin.table("assignments").update({
                "eta": f"{eta} mins",
                "status": "assigned",
            }).eq("id", existing["id"]).execute()

        return {
            "message": "Responder already assigned",
            "incident_id": incident_id,
            "responder_id": body.responder_id,
            "status": existing.get("status", "assigned"),
            "distance_km": round(distance, 2),
            "eta_minutes": eta,
        }

    record_assignment(incident_id, body.responder_id, eta, assigned_by=body.assigned_by, note=body.note)

    supabase_admin.table("incidents").update({
        "status": "assigned",
    }).eq("id", incident_id).execute()

    return {
        "message": "Responder assigned",
        "incident_id": incident_id,
        "responder_id": body.responder_id,
        "status": "assigned",
        "distance_km": round(distance, 2),
        "eta_minutes": eta,
    }
