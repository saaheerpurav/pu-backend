"""
Social Reporting Router — Mobile App
Lets citizens interact with existing disaster events:
  - Confirm a reported event ("I can see this too")
  - Add an observation (quick text, no full report flow)
  - Get community feed near their location
  - Get confirmation count for an event
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.supabase_client import supabase_admin
from app.services.clustering import haversine_km
from app.services.report_service import submit_report

router = APIRouter(prefix="/social", tags=["social"])


class ConfirmRequest(BaseModel):
    latitude: float
    longitude: float
    user_id: str = None          # optional, from auth token


class ObservationRequest(BaseModel):
    latitude: float
    longitude: float
    disaster_type: str
    observation: str             # short text from citizen
    user_id: str = None


# ─────────────────────────────────────────────────────────────
# POST /social/events/{event_id}/confirm
# One-tap "I can see this too" — boosts confidence as a social signal
# ─────────────────────────────────────────────────────────────
@router.post("/events/{event_id}/confirm")
def confirm_event(event_id: str, body: ConfirmRequest):
    event = supabase_admin.table("disaster_events") \
        .select("*").eq("id", event_id).single().execute()
    if not event.data:
        raise HTTPException(status_code=404, detail="Event not found")

    e = event.data

    # Validate user is reasonably near the event (within 10km)
    dist = haversine_km(body.latitude, body.longitude, e["latitude"], e["longitude"])
    if dist > 10:
        raise HTTPException(
            status_code=400,
            detail=f"You are {dist:.1f}km from this event. Confirmations must be within 10km."
        )

    # Log as a social-source report — this feeds into confidence scoring
    result = submit_report(
        source="social",
        latitude=body.latitude,
        longitude=body.longitude,
        disaster_type=e["type"],
        description=f"Community confirmation of event {event_id[:8]}",
        people_count=1,
        injuries=False,
    )

    return {
        "message": "Confirmation recorded. Thank you.",
        "event_id": event_id,
        "new_confidence": result["confidence"],
    }


# ─────────────────────────────────────────────────────────────
# POST /social/observe
# Quick observation — citizen shares what they're seeing
# Gets geo-clustered like a normal report but lighter weight
# ─────────────────────────────────────────────────────────────
@router.post("/observe")
def post_observation(body: ObservationRequest):
    result = submit_report(
        source="social",
        latitude=body.latitude,
        longitude=body.longitude,
        disaster_type=body.disaster_type,
        description=body.observation,
        people_count=1,
        injuries=False,
    )
    return {
        "message": "Observation posted.",
        "report_id": result["report_id"],
        "event_id": result["event_id"],
        "confidence": result["confidence"],
    }


# ─────────────────────────────────────────────────────────────
# GET /social/feed
# Community feed — active events near user with confirmation counts
# ─────────────────────────────────────────────────────────────
@router.get("/feed")
def community_feed(lat: float, lng: float, radius_km: float = 10.0):
    # Fetch active events
    try:
        events = supabase_admin.table("disaster_events") \
            .select("*").eq("active", True).order("created_at", desc=True).execute().data or []
    except Exception:
        events = supabase_admin.table("disaster_events") \
            .select("*").order("created_at", desc=True).execute().data or []

    # Filter by radius and attach confirmation count + distance
    feed = []
    for event in events:
        dist = haversine_km(lat, lng, event["latitude"], event["longitude"])
        if dist > radius_km:
            continue

        # Count social confirmations for this event
        confirmations = supabase_admin.table("reports") \
            .select("id", count="exact") \
            .eq("event_id", event["id"]) \
            .eq("source", "social") \
            .execute()

        feed.append({
            **event,
            "distance_km": round(dist, 2),
            "confirmations": confirmations.count or 0,
        })

    feed.sort(key=lambda e: e["distance_km"])
    return feed


# ─────────────────────────────────────────────────────────────
# GET /social/events/{event_id}/confirmations
# How many citizens have confirmed this event
# ─────────────────────────────────────────────────────────────
@router.get("/events/{event_id}/confirmations")
def get_confirmations(event_id: str):
    res = supabase_admin.table("reports") \
        .select("id, latitude, longitude, created_at", count="exact") \
        .eq("event_id", event_id) \
        .eq("source", "social") \
        .execute()

    return {
        "event_id": event_id,
        "confirmation_count": res.count or 0,
        "confirmations": res.data or [],
    }
