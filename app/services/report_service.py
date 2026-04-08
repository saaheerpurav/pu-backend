"""
Core report submission logic — shared by the REST API and WhatsApp bot.
Extracted so the WhatsApp webhook doesn't need to HTTP-call itself.
"""

from app.supabase_client import supabase_admin
from app.services.clustering import find_nearest_event, snap_to_grid
from app.services.confidence import calculate_confidence, get_severity


def submit_report(
    source: str,
    latitude: float,
    longitude: float,
    disaster_type: str,
    description: str = None,
    people_count: int = 1,
    injuries: bool = False,
    weather_severity: float = 0,
) -> dict:
    """
    Geo-cluster report → create/update event → update grid.
    Returns { report_id, event_id, confidence }
    Raises Exception on failure.
    """

    # 1. Fetch active events to cluster against
    try:
        active_events = supabase_admin.table("disaster_events") \
            .select("*").eq("active", True).eq("type", disaster_type).execute().data or []
    except Exception:
        active_events = supabase_admin.table("disaster_events") \
            .select("*").eq("type", disaster_type).execute().data or []

    # 2. Find nearest event within 1km
    nearest = find_nearest_event(latitude, longitude, active_events)

    if nearest:
        event_id = nearest["id"]
        breakdown = nearest.get("source_breakdown") or {"app": 0, "whatsapp": 0, "news": 0, "social": 0}
        breakdown[source] = breakdown.get(source, 0) + 1
        new_confidence = calculate_confidence(breakdown, weather_severity or nearest.get("weather_severity", 0))
        new_severity = get_severity(new_confidence)

        base_update = {"confidence": new_confidence, "severity": new_severity}
        try:
            supabase_admin.table("disaster_events").update({
                **base_update,
                "source_breakdown": breakdown,
                "weather_severity": max(weather_severity, nearest.get("weather_severity", 0)),
            }).eq("id", event_id).execute()
        except Exception:
            supabase_admin.table("disaster_events").update(base_update).eq("id", event_id).execute()

    else:
        # 3. Create new disaster event
        breakdown = {"app": 0, "whatsapp": 0, "news": 0, "social": 0}
        breakdown[source] = 1
        new_confidence = calculate_confidence(breakdown, weather_severity)
        new_severity = get_severity(new_confidence)

        base_payload = {
            "type": disaster_type,
            "latitude": latitude,
            "longitude": longitude,
            "confidence": new_confidence,
            "severity": new_severity,
        }
        try:
            event_res = supabase_admin.table("disaster_events").insert({
                **base_payload,
                "source_breakdown": breakdown,
                "weather_severity": weather_severity,
                "active": True,
            }).execute()
        except Exception:
            event_res = supabase_admin.table("disaster_events").insert(base_payload).execute()

        if not event_res.data:
            raise Exception("Failed to create disaster event")

        event_id = event_res.data[0]["id"]

    # 4. Insert report
    report_base = {
        "source": source,
        "event_id": event_id,
        "latitude": latitude,
        "longitude": longitude,
        "description": description,
    }
    try:
        report_res = supabase_admin.table("reports").insert({
            **report_base,
            "disaster_type": disaster_type,
            "people_count": people_count,
            "injuries": injuries,
        }).execute()
    except Exception:
        report_res = supabase_admin.table("reports").insert(report_base).execute()

    report_id = report_res.data[0]["id"] if report_res.data else None

    # 5. Update grid risk
    grid_lat, grid_lng = snap_to_grid(latitude, longitude)
    supabase_admin.table("grid_risk").upsert({
        "grid_lat": grid_lat,
        "grid_lng": grid_lng,
        "risk_score": min(round(new_confidence * 0.9, 1), 100),
        "updated_at": "now()",
    }, on_conflict="grid_lat,grid_lng").execute()

    return {
        "report_id": report_id,
        "event_id": event_id,
        "confidence": new_confidence,
    }
