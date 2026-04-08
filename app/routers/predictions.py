"""
Predictive Early Warning Router
Scans active events and returns warnings for dashboard/mobile.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from app.supabase_client import supabase_admin
from app.services.predictor import scan_all_warnings

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("")
def get_predictions():
    """Returns active early warnings across all events."""
    try:
        active_events = supabase_admin.table("disaster_events") \
            .select("*").eq("active", True).execute().data or []
    except Exception:
        active_events = supabase_admin.table("disaster_events").select("*").execute().data or []

    if not active_events:
        return []

    # Count reports per event in the last 30 minutes
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    recent_reports = supabase_admin.table("reports") \
        .select("event_id") \
        .gte("created_at", cutoff) \
        .execute().data or []

    report_counts = {}
    for r in recent_reports:
        eid = r["event_id"]
        if eid:
            report_counts[eid] = report_counts.get(eid, 0) + 1

    return scan_all_warnings(active_events, report_counts)
