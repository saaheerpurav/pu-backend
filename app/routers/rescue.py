"""
Rescue Allocation Router
Dashboard dispatches rescue units; units tracked in realtime.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.supabase_client import supabase_admin
from app.services.rescue_allocator import find_nearest_unit, calculate_eta_minutes

router = APIRouter(prefix="/rescue", tags=["rescue"])


class AllocateRequest(BaseModel):
    event_id: str


@router.get("/units")
def list_units(status: str = None):
    query = supabase_admin.table("rescue_units").select("*")
    if status:
        query = query.eq("status", status)
    return query.execute().data or []


@router.post("/allocate")
def allocate_rescue(body: AllocateRequest):
    """Find and dispatch nearest available unit to the event."""
    event = supabase_admin.table("disaster_events").select("*").eq("id", body.event_id).single().execute()
    if not event.data:
        raise HTTPException(status_code=404, detail="Event not found")

    units = supabase_admin.table("rescue_units").select("*").eq("status", "available").execute().data or []
    if not units:
        raise HTTPException(status_code=409, detail="No available rescue units")

    unit = find_nearest_unit(event.data["latitude"], event.data["longitude"], units)
    if not unit:
        raise HTTPException(status_code=409, detail="No available rescue units")

    eta = calculate_eta_minutes(unit["_distance_km"])

    # Mark unit as busy and assign event
    try:
        supabase_admin.table("rescue_units").update({
            "status": "busy",
            "assigned_event_id": body.event_id,
        }).eq("id", unit["id"]).execute()
    except Exception:
        supabase_admin.table("rescue_units").update({"status": "busy"}).eq("id", unit["id"]).execute()

    return {
        "unit_id": unit["id"],
        "unit_name": unit["name"],
        "event_id": body.event_id,
        "distance_km": unit["_distance_km"],
        "eta_minutes": eta,
        "message": f"{unit['name']} dispatched — ETA {eta} min",
    }


@router.patch("/units/{unit_id}/status")
def update_unit_status(unit_id: str, status: str):
    """Mark unit as available/busy. Call when unit completes a job."""
    if status not in ("available", "busy"):
        raise HTTPException(status_code=400, detail="status must be 'available' or 'busy'")

    try:
        update = {"status": status}
        if status == "available":
            update["assigned_event_id"] = None
        supabase_admin.table("rescue_units").update(update).eq("id", unit_id).execute()
    except Exception:
        supabase_admin.table("rescue_units").update({"status": status}).eq("id", unit_id).execute()
    return {"message": f"Unit {unit_id} marked as {status}"}
