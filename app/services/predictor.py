"""
Predictive Early Warning Engine
Triggers warnings based on:
- Rapid report density increase in last 30 min
- Weather severity spikes
- High confidence events forming
"""

from datetime import datetime, timezone, timedelta

REPORT_SPIKE_THRESHOLD = 3      # reports in 30 min → warning
CONFIDENCE_WARN_THRESHOLD = 55  # confidence at which we warn
WEATHER_SPIKE_THRESHOLD = 60    # weather severity 0–100


def check_early_warning(event: dict, recent_report_count: int) -> dict | None:
    """
    Returns a warning dict if conditions are met, else None.
    recent_report_count = reports for this event in last 30 min.
    """
    triggers = []

    if recent_report_count >= REPORT_SPIKE_THRESHOLD:
        triggers.append(f"Report density spike ({recent_report_count} reports in 30 min)")

    if event.get("weather_severity", 0) >= WEATHER_SPIKE_THRESHOLD:
        triggers.append(f"High weather severity ({event['weather_severity']}%)")

    if event.get("confidence", 0) >= CONFIDENCE_WARN_THRESHOLD:
        triggers.append(f"Confidence threshold reached ({event['confidence']}%)")

    if not triggers:
        return None

    disaster_type = event.get("type", "disaster").title()
    return {
        "event_id": event["id"],
        "warning": f"High {disaster_type} Probability in 30 Minutes",
        "triggers": triggers,
        "confidence": event.get("confidence", 0),
        "severity": event.get("severity", "medium"),
        "latitude": event["latitude"],
        "longitude": event["longitude"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def scan_all_warnings(events: list, report_counts: dict) -> list:
    """
    events: list of active disaster_event dicts
    report_counts: {event_id: count_last_30_min}
    Returns list of warning dicts.
    """
    warnings = []
    for event in events:
        count = report_counts.get(event["id"], 0)
        w = check_early_warning(event, count)
        if w:
            warnings.append(w)
    return warnings
