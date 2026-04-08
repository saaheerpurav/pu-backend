"""
Disaster Events Router
Dashboard reads events; mobile app checks nearby events.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException
from app.supabase_client import supabase_admin
from app.services.clustering import haversine_km
from app.services.responder_utils import column_exists

logger = logging.getLogger("resqnet.backend.events")

router = APIRouter(prefix="/events", tags=["events"])

DEFAULT_EVENT_LIMIT = 200
MAX_EVENT_LIMIT = 500


def _ensure_event_coordinates(event: dict) -> dict | None:
    if event.get("latitude") is not None and event.get("longitude") is not None:
        return event
    if not event.get("id"):
        return None
    report = (
        supabase_admin.table("reports")
        .select("latitude", "longitude")
        .eq("event_id", event["id"])
        .limit(1)
        .execute()
        .data
    )
    if report:
        coords = report[0]
        if coords.get("latitude") is not None and coords.get("longitude") is not None:
            event["latitude"] = coords["latitude"]
            event["longitude"] = coords["longitude"]
            return event
    logger.warning("Event %s missing coordinates and had no reports to fill them", event.get("id"))
    return None


@router.get("")
def list_events(
    active_only: bool = True,
    limit: int = DEFAULT_EVENT_LIMIT,
    severity: str | None = None,
    min_lat: float | None = None,
    min_lng: float | None = None,
    max_lat: float | None = None,
    max_lng: float | None = None,
) -> List[dict]:
    query = supabase_admin.table("disaster_events").select("*").order("created_at", desc=True)
    sanitized_limit = max(1, min(limit, MAX_EVENT_LIMIT))
    fetch_limit = max(sanitized_limit, 1)

    latlng_columns = (
        column_exists("disaster_events", "latitude") and column_exists("disaster_events", "longitude")
    )
    if min_lat is not None and latlng_columns:
        query = query.gte("latitude", min_lat)
    if max_lat is not None and latlng_columns:
        query = query.lte("latitude", max_lat)
    if min_lng is not None and latlng_columns:
        query = query.gte("longitude", min_lng)
    if max_lng is not None and latlng_columns:
        query = query.lte("longitude", max_lng)

    if severity:
        query = query.eq("severity", severity)
    try:
        if active_only:
            query = query.eq("active", True)
        rows = query.limit(fetch_limit).execute().data or []
    except Exception:
        # active column may not exist yet (run migration.sql)
        rows = (
            supabase_admin.table("disaster_events")
            .select("*")
            .order("created_at", desc=True)
            .limit(fetch_limit)
            .execute()
            .data
            or []
        )

    enriched = []
    for event in rows:
        safe_event = _ensure_event_coordinates(event)
        if safe_event:
            enriched.append(safe_event)
    return enriched[:sanitized_limit]


@router.get("/nearby")
def nearby_events(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    cluster_hint: bool = False,
    cluster_threshold: int = 3,
):
    """Mobile app uses this to show alerts near user's location."""
    try:
        all_events = supabase_admin.table("disaster_events") \
            .select("*").eq("active", True).execute().data or []
    except Exception:
        all_events = supabase_admin.table("disaster_events").select("*").execute().data or []

    nearby = []
    for event in all_events:
        dist = haversine_km(lat, lng, event["latitude"], event["longitude"])
        if dist <= radius_km:
            nearby.append({**event, "distance_km": round(dist, 2)})

    nearby.sort(key=lambda e: e["distance_km"])
    response = {"events": nearby}
    if cluster_hint and len(nearby) >= cluster_threshold:
        response.update(
            {
                "cluster_hint": True,
                "cluster_message": f"{len(nearby)} nearby reports — monitor closely.",
                "cluster_count": len(nearby),
            }
        )
    return response


@router.get("/{event_id}")
def get_event(event_id: str):
    event = supabase_admin.table("disaster_events").select("*").eq("id", event_id).single().execute()
    if not event.data:
        raise HTTPException(status_code=404, detail="Event not found")

    reports = supabase_admin.table("reports").select("*").eq("event_id", event_id).execute().data or []

    return {**event.data, "reports": reports, "report_count": len(reports)}


@router.patch("/{event_id}/resolve")
def resolve_event(event_id: str):
    """Mark event as inactive (resolved)."""
    supabase_admin.table("disaster_events").update({"active": False}).eq("id", event_id).execute()
    return {"message": "Event resolved"}
