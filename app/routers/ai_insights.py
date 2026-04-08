from typing import List

from fastapi import APIRouter

from app.services.triage import PROMPT_VERSION
from app.supabase_client import supabase_admin

router = APIRouter(prefix="/ai/insights", tags=["ai-insights"])


def _fetch_events(limit: int = 20) -> List[dict]:
    return supabase_admin.table("disaster_events") \
        .select("id, type, severity, confidence, latitude, longitude, created_at, active") \
        .order("confidence", desc=True).limit(limit).execute().data or []


@router.get("/summary")
def ai_insights_summary():
    events = _fetch_events(20)
    top_event = events[0] if events else None
    high_risk_zones = len({
        (round(evt.get("latitude", 0), 2), round(evt.get("longitude", 0), 2))
        for evt in events
        if evt.get("severity") == "high"
    })
    summary_text = (
        f"Likely {top_event['type']} escalation near {round(top_event['latitude'], 3)},"
        f" {round(top_event['longitude'], 3)} in ~40 min"
        if top_event else "No active high-risk events"
    )
    recommended_actions = []
    for evt in events[:3]:
        sev = evt.get("severity", "medium")
        recommended_actions.append(
            f"Monitor {evt.get('type', 'incident')} at ({round(evt.get('latitude', 0), 2)}, "
            f"{round(evt.get('longitude', 0), 2)}) — {sev.upper()} severity"
        )

    if not recommended_actions:
        recommended_actions = [
            "Keep telemetry open; no actionable emergencies right now."
        ]

    return {
        "top_prediction": summary_text,
        "high_risk_zones": high_risk_zones,
        "recommended_actions": recommended_actions,
        "model_version": PROMPT_VERSION,
    }


@router.get("/actions")
def ai_insights_actions(limit: int = 10):
    events = _fetch_events(limit * 2)
    actions = []
    for evt in events:
        severity = evt.get("severity", "low")
        urgency = "Immediate" if severity == "high" else ("Watch" if severity == "medium" else "Monitor")
        actions.append({
            "id": evt["id"],
            "urgency": urgency,
            "owner": "Urban Response Cell" if severity == "high" else "Field Monitor",
            "action": (
                f"{'Dispatch responders' if severity == 'high' else 'Track'} {evt.get('type')} near "
                f"{round(evt.get('latitude', 0), 2)},{round(evt.get('longitude', 0), 2)}."
            ),
        })
        if len(actions) >= limit:
            break

    if not actions:
        actions.append({
            "id": "none",
            "urgency": "Monitor",
            "owner": "Command Center",
            "action": "No AI-suggested actions right now.",
        })

    return actions
