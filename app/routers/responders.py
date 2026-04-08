from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from postgrest import APIError

from app.services.clustering import haversine_km
from app.services.rescue_allocator import calculate_eta_minutes
from app.services.responder_utils import (
    availability_to_bool,
    column_exists,
    derive_availability,
    safe_responder_update,
)
from app.supabase_client import supabase_admin

router = APIRouter(prefix="/responders", tags=["responders"])

DEFAULT_RESPONDER_LIMIT = 200
MAX_RESPONDER_LIMIT = 1000


class ResponderCreateRequest(BaseModel):
    name: str
    type: str
    phone: str
    latitude: float
    longitude: float
    availability: str = "ready"


class ResponderUpdateRequest(BaseModel):
    availability: Optional[str] = None
    current_status: Optional[str] = None
    eta_minutes: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None


class LocationReport(BaseModel):
    latitude: float
    longitude: float
    speed_kmph: Optional[float] = None


def _ordered_responder_query():
    base = supabase_admin.table("responders").select("*")
    sort_column = "updated_at" if column_exists("responders", "updated_at") else "created_at"
    return base.order(sort_column, desc=True)


def _normalize_responder(row: dict) -> dict:
    availability = derive_availability(row)
    status = row.get("current_status")
    if not status:
        status = "Available" if availability == "ready" else "Busy"
    return {
        "id": row.get("id"),
        "name": row.get("name") or "Responder",
        "type": row.get("type"),
        "phone": row.get("phone"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "availability": availability,
        "current_status": status,
        "eta_minutes": row.get("eta_minutes") or 0,
        "updated_at": row.get("updated_at") or row.get("created_at"),
    }


def _build_create_payload(body: ResponderCreateRequest) -> dict:
    payload = {
        "type": body.type,
        "latitude": body.latitude,
        "longitude": body.longitude,
    }
    if column_exists("responders", "name"):
        payload["name"] = body.name
    if column_exists("responders", "phone"):
        payload["phone"] = body.phone
    if column_exists("responders", "availability"):
        payload["availability"] = body.availability
    elif column_exists("responders", "available"):
        payload["available"] = availability_to_bool(body.availability)
    if column_exists("responders", "current_status"):
        payload["current_status"] = "Ready"
    if column_exists("responders", "eta_minutes"):
        payload["eta_minutes"] = 0
    if column_exists("responders", "updated_at"):
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


@router.get("")
def list_responders(
    availability: str | None = None,
    type: str | None = None,
    limit: int = DEFAULT_RESPONDER_LIMIT,
    min_lat: float | None = None,
    min_lng: float | None = None,
    max_lat: float | None = None,
    max_lng: float | None = None,
    updated_before: datetime | None = None,
) -> List[dict]:
    query = _ordered_responder_query()
    sanitized_limit = max(1, min(limit, MAX_RESPONDER_LIMIT))
    fetch_limit = sanitized_limit
    availability_filter_applied = False

    has_latlng = column_exists("responders", "latitude") and column_exists("responders", "longitude")
    if min_lat is not None and has_latlng:
        query = query.gte("latitude", min_lat)
    if max_lat is not None and has_latlng:
        query = query.lte("latitude", max_lat)
    if min_lng is not None and has_latlng:
        query = query.gte("longitude", min_lng)
    if max_lng is not None and has_latlng:
        query = query.lte("longitude", max_lng)

    if updated_before:
        timestamp_column = "updated_at" if column_exists("responders", "updated_at") else "created_at"
        query = query.lt(timestamp_column, updated_before.isoformat())

    if availability:
        if column_exists("responders", "availability"):
            query = query.eq("availability", availability)
            availability_filter_applied = True
        elif column_exists("responders", "available"):
            query = query.eq("available", availability_to_bool(availability))
            availability_filter_applied = True
        else:
            fetch_limit = max(sanitized_limit * 3, sanitized_limit + 20)
    if type:
        query = query.eq("type", type)

    rows = query.limit(max(fetch_limit, 1)).execute().data or []

    if availability and not availability_filter_applied:
        rows = [
            row for row in rows
            if derive_availability(row).lower() == availability.lower()
        ]

    normalized = [_normalize_responder(row) for row in rows]
    return normalized[:sanitized_limit]


@router.post("")
def create_responder(body: ResponderCreateRequest):
    payload = _build_create_payload(body)
    res = supabase_admin.table("responders").insert(payload).execute()
    responder_id = res.data[0].get("id") if res.data else None
    return {"message": "Responder created", "responder_id": responder_id}


@router.patch("/{responder_id}")
def update_responder(responder_id: str, body: ResponderUpdateRequest):
    payload = {k: v for k, v in body.dict(exclude_none=True).items()}
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    safe_responder_update(responder_id, payload)
    return {"message": "Responder updated"}


@router.post("/{responder_id}/location")
def responder_location(responder_id: str, body: LocationReport):
    updated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "latitude": body.latitude,
        "longitude": body.longitude,
    }
    if column_exists("responders", "current_status"):
        payload["current_status"] = "En route" if body.speed_kmph else "Available"
    if column_exists("responders", "availability"):
        payload["availability"] = "en_route" if body.speed_kmph else "ready"
    elif column_exists("responders", "available"):
        payload["available"] = bool(body.speed_kmph)
    if column_exists("responders", "updated_at"):
        payload["updated_at"] = updated_at

    safe_responder_update(responder_id, payload)

    supabase_admin.table("responder_locations").insert({
        "responder_id": responder_id,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "speed_kmph": body.speed_kmph,
        "captured_at": updated_at,
    }).execute()

    return {"message": "Location updated", "updated_at": updated_at}


@router.get("/nearby")
def nearby_responders(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    availability: str | None = None,
):
    target_availability = availability.lower() if availability else None
    all_units = supabase_admin.table("responders").select("*").execute().data or []
    nearby = []
    for unit in all_units:
        dist = haversine_km(lat, lng, unit["latitude"], unit["longitude"])
        if dist > radius_km:
            continue
        if target_availability and derive_availability(unit).lower() != target_availability:
            continue
        availability_value = derive_availability(unit)
        nearby.append({
            "id": unit["id"],
            "name": unit.get("name") or "Responder",
            "type": unit.get("type"),
            "distance_km": round(dist, 2),
            "eta_minutes": unit.get("eta_minutes") or calculate_eta_minutes(dist),
            "availability": availability_value,
        })
    nearby.sort(key=lambda entry: entry["distance_km"])
    return nearby
