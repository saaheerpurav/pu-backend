"""
External Data Ingestion Router
Simulates signals from news APIs, social media, and weather APIs.
In production these would be scheduled jobs; for hackathon demo they're manual triggers.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.supabase_client import supabase_admin
from app.services.clustering import find_nearest_event, snap_to_grid
from app.services.confidence import calculate_confidence, get_severity

router = APIRouter(prefix="/external", tags=["external"])


class ExternalSignal(BaseModel):
    source: str           # news | social | weather
    latitude: float
    longitude: float
    disaster_type: str
    severity_score: float = 0    # 0–100 (for weather); count for news/social
    description: str = None


@router.post("/ingest")
def ingest_signal(body: ExternalSignal):
    """
    Inject an external signal (news article, social hit, weather alert).
    Behaves like /reports but for non-human sources.
    Auto-clusters into nearest event or creates one.
    """
    try:
        active_events = supabase_admin.table("disaster_events") \
            .select("*").eq("active", True).eq("type", body.disaster_type).execute().data or []
    except Exception:
        active_events = supabase_admin.table("disaster_events") \
            .select("*").eq("type", body.disaster_type).execute().data or []

    nearest = find_nearest_event(body.latitude, body.longitude, active_events)

    weather_sev = body.severity_score if body.source == "weather" else 0

    if nearest:
        event_id = nearest["id"]
        breakdown = nearest.get("source_breakdown") or {"app": 0, "whatsapp": 0, "news": 0, "social": 0}
        if body.source in ("news", "social"):
            breakdown[body.source] = breakdown.get(body.source, 0) + 1

        new_confidence = calculate_confidence(
            breakdown,
            max(weather_sev, nearest.get("weather_severity", 0))
        )
        new_severity = get_severity(new_confidence)

        supabase_admin.table("disaster_events").update({
            "confidence": new_confidence,
            "severity": new_severity,
            "source_breakdown": breakdown,
            "weather_severity": max(weather_sev, nearest.get("weather_severity", 0)),
        }).eq("id", event_id).execute()

    else:
        breakdown = {"app": 0, "whatsapp": 0, "news": 0, "social": 0}
        if body.source in breakdown:
            breakdown[body.source] = 1

        confidence = calculate_confidence(breakdown, weather_sev)
        severity = get_severity(confidence)

        event_res = supabase_admin.table("disaster_events").insert({
            "type": body.disaster_type,
            "latitude": body.latitude,
            "longitude": body.longitude,
            "confidence": confidence,
            "severity": severity,
            "source_breakdown": breakdown,
            "weather_severity": weather_sev,
            "active": True,
        }).execute()

        event_id = event_res.data[0]["id"] if event_res.data else None

    # Log as a report entry for audit trail
    supabase_admin.table("reports").insert({
        "source": body.source,
        "event_id": event_id,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "disaster_type": body.disaster_type,
        "description": body.description,
    }).execute()

    # Update grid
    if event_id:
        grid_lat, grid_lng = snap_to_grid(body.latitude, body.longitude)
        event_data = supabase_admin.table("disaster_events").select("confidence") \
            .eq("id", event_id).single().execute().data or {}
        supabase_admin.table("grid_risk").upsert({
            "grid_lat": grid_lat,
            "grid_lng": grid_lng,
            "risk_score": min(round(event_data.get("confidence", 0) * 0.9, 1), 100),
            "updated_at": "now()",
        }, on_conflict="grid_lat,grid_lng").execute()

    return {"message": f"{body.source} signal ingested", "event_id": event_id}


@router.post("/ingest/bulk")
def ingest_bulk(signals: list[ExternalSignal]):
    """Ingest multiple signals at once — useful for demo seeding."""
    results = []
    for signal in signals:
        result = ingest_signal(signal)
        results.append(result)
    return {"ingested": len(results), "results": results}
