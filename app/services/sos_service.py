"""
SOS incident creation and responder assignment for the new schema.
"""

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from typing import Any, Dict

from app.services.assignment_store import fetch_latest_assignment, record_assignment
from app.supabase_client import supabase_admin
from app.services.rescue_allocator import calculate_eta_minutes, find_nearest_unit
from app.services.responder_utils import column_exists, derive_availability, safe_responder_update


DEFAULT_COORDS = (12.9716, 77.5946)
DEDUP_WINDOW_MINUTES = 5


def _normalize_context(context: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not context:
        return None
    copied = context.copy()
    nfc_user = copied.get("nfc_user_id_recent")
    nfc_secs = copied.get("nfc_linked_seconds_ago")
    if nfc_user and isinstance(nfc_secs, (int, float)) and nfc_secs <= 900:
        try:
            profile = supabase_admin.table("users") \
                .select("id").eq("id", nfc_user).limit(1).execute()
            copied["nfc_verified"] = bool(profile.data)
        except Exception:
            copied["nfc_verified"] = False
    return copied


def _compute_dedupe_key(user_id: str | None, incident_type: str, latitude: float, longitude: float, source: str) -> str:
    base = f"{user_id or 'anon'}|{incident_type}|{round(latitude, 5)}|{round(longitude, 5)}|{source}"
    return sha256(base.encode("utf-8")).hexdigest()


def _find_recent_incident(dedupe_key: str) -> Dict[str, Any] | None:
    if not column_exists("incidents", "dedupe_key"):
        return None
    window = (datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MINUTES)).isoformat()
    try:
        rows = supabase_admin.table("incidents").select("*") \
            .eq("dedupe_key", dedupe_key).gte("created_at", window) \
            .order("created_at", desc=True).limit(1).execute().data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_responder_info(responder_id: str) -> Dict[str, Any] | None:
    responder = supabase_admin.table("responders").select("*").eq("id", responder_id).single().execute()
    return responder.data if responder.data else None


def _build_incident_response(incident_row: Dict[str, Any]) -> dict:
    assignment = fetch_latest_assignment(incident_row["id"])
    response = {
        "incident_id": incident_row["id"],
        "status": incident_row.get("status", "pending"),
        "type": incident_row.get("type"),
        "latitude": incident_row.get("latitude"),
        "longitude": incident_row.get("longitude"),
        "created_at": incident_row.get("created_at"),
        "updated_at": incident_row.get("updated_at"),
        "next_poll_after_seconds": None,
        "responder": None,
        "eta_minutes": None,
    }

    if assignment:
        responder = _get_responder_info(assignment["responder_id"])
        response["eta_minutes"] = assignment.get("eta_minutes")
        response["responder"] = {
            "id": responder.get("id") if responder else assignment["responder_id"],
            "name": (responder or {}).get("name", "Responder"),
            "type": (responder or {}).get("type", "ambulance"),
            "eta_minutes": assignment.get("eta_minutes"),
        }
        response["status"] = "assigned"
    else:
        response["next_poll_after_seconds"] = 30
        response["status"] = "pending"

    if incident_row.get("status") == "resolved":
        response["status"] = "resolved"

    return response


def _load_responder_candidates() -> list:
    responders = supabase_admin.table("responders") \
        .select("*").execute().data or []
    return [res for res in responders if derive_availability(res) == "ready"]


def _store_incident(
    user_id: str | None,
    incident_type: str,
    latitude: float,
    longitude: float,
    source: str,
    status: str,
    context: Dict[str, Any] | None,
    dedupe_key: str | None,
) -> str:
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "type": incident_type,
        "source": source,
        "status": status,
        "latitude": latitude,
        "longitude": longitude,
    }
    if context and column_exists("incidents", "context"):
        payload["context"] = context
    if dedupe_key and column_exists("incidents", "dedupe_key"):
        payload["dedupe_key"] = dedupe_key

    res = supabase_admin.table("incidents").insert(payload).execute()
    return res.data[0]["id"]


def _mark_responder_busy(responder_id: str, eta_minutes: int):
    safe_responder_update(responder_id, {
        "availability": "en_route",
        "current_status": "Assigned via SOS",
        "eta_minutes": eta_minutes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def create_sos_incident(
    user_id: str | None,
    incident_type: str,
    latitude: float | None,
    longitude: float | None,
    source: str,
    context: Dict[str, Any] | None = None,
) -> dict:
    lat = latitude if latitude is not None else DEFAULT_COORDS[0]
    lng = longitude if longitude is not None else DEFAULT_COORDS[1]
    normalized_context = _normalize_context(context)

    dedupe_key = _compute_dedupe_key(user_id, incident_type, lat, lng, source)
    duplicate = _find_recent_incident(dedupe_key)
    if duplicate:
        return _build_incident_response(duplicate)

    incident_id = _store_incident(
        user_id,
        incident_type,
        lat,
        lng,
        source,
        status="pending",
        context=normalized_context,
        dedupe_key=dedupe_key,
    )

    responders = _load_responder_candidates()
    responder = find_nearest_unit(lat, lng, responders)

    if not responder:
        response = {
            "incident_id": incident_id,
            "status": "pending",
            "responder": None,
            "next_poll_after_seconds": 30,
        }
        if normalized_context:
            response["context"] = normalized_context
        return response

    eta_minutes = calculate_eta_minutes(responder["_distance_km"])
    record_assignment(incident_id, responder["id"], eta_minutes, assigned_by="system")
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase_admin.table("incidents").update({
        "status": "assigned",
        "updated_at": now_iso,
    }).eq("id", incident_id).execute()
    _mark_responder_busy(responder["id"], eta_minutes)

    return {
        "incident_id": incident_id,
        "status": "assigned",
        "responder": {
            "id": responder["id"],
            "name": responder.get("name", "Responder"),
            "type": responder.get("type", "ambulance"),
            "eta": f"{eta_minutes} mins",
            "eta_minutes": eta_minutes,
        },
        "eta_minutes": eta_minutes,
        "context": normalized_context,
    }
