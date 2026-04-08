"""
Dashboard Stats Router
Aggregated summary data for the authority dashboard.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from app.supabase_client import supabase_admin

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_stats():
    """High-level summary: event counts, report counts, unit availability."""
    try:
        events = supabase_admin.table("disaster_events").select("id, severity, active, created_at").execute().data or []
    except Exception:
        events = supabase_admin.table("disaster_events").select("id, severity, created_at").execute().data or []
    reports = supabase_admin.table("reports").select("id, source, created_at").execute().data or []
    units = supabase_admin.table("rescue_units").select("id, status").execute().data or []

    active_events = [e for e in events if e.get("active")]
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    return {
        "events": {
            "total": len(events),
            "active": len(active_events),
            "high_severity": sum(1 for e in active_events if e.get("severity") == "high"),
            "medium_severity": sum(1 for e in active_events if e.get("severity") == "medium"),
            "low_severity": sum(1 for e in active_events if e.get("severity") == "low"),
        },
        "reports": {
            "total": len(reports),
            "last_24h": sum(1 for r in reports if r.get("created_at", "") >= cutoff_24h),
            "by_source": {
                "app": sum(1 for r in reports if r.get("source") == "app"),
                "whatsapp": sum(1 for r in reports if r.get("source") == "whatsapp"),
                "news": sum(1 for r in reports if r.get("source") == "news"),
                "social": sum(1 for r in reports if r.get("source") == "social"),
            },
        },
        "rescue_units": {
            "total": len(units),
            "available": sum(1 for u in units if u.get("status") == "available"),
            "busy": sum(1 for u in units if u.get("status") == "busy"),
        },
    }


@router.get("/feed")
def get_live_feed(limit: int = 20):
    """Latest activity feed for dashboard sidebar."""
    reports = supabase_admin.table("reports") \
        .select("id, source, disaster_type, description, created_at, latitude, longitude") \
        .order("created_at", desc=True).limit(limit).execute().data or []

    events = supabase_admin.table("disaster_events") \
        .select("id, type, confidence, severity, created_at, active") \
        .order("created_at", desc=True).limit(10).execute().data or []

    return {"recent_reports": reports, "recent_events": events}
