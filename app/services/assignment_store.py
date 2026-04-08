import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

from postgrest import APIError

from app.supabase_client import supabase_admin

_INCIDENT_ASSIGNMENTS_AVAILABLE: bool | None = None
_MISSING_TABLE_CODE = "PGRST205"
_ETA_MINUTES_PATTERN = re.compile(r"(\d+)")


def _looks_like_missing_table_error(exc: APIError) -> bool:
    payload = exc.args[0] if exc.args else None
    message = ""
    code = None

    if isinstance(payload, dict):
        message = payload.get("message", "")
        code = payload.get("code")
    else:
        message = str(payload or exc)

    if message and "Could not find the table" in message:
        return True
    return code == _MISSING_TABLE_CODE


def _ensure_incident_assignments_available() -> bool:
    global _INCIDENT_ASSIGNMENTS_AVAILABLE
    if _INCIDENT_ASSIGNMENTS_AVAILABLE is not None:
        return _INCIDENT_ASSIGNMENTS_AVAILABLE
    try:
        supabase_admin.table("incident_assignments").select("id").limit(1).execute()
        _INCIDENT_ASSIGNMENTS_AVAILABLE = True
    except APIError as exc:
        if _looks_like_missing_table_error(exc):
            logging.warning(
                "Incident assignments table not readable from Supabase; falling back to assignments table"
            )
            _INCIDENT_ASSIGNMENTS_AVAILABLE = False
        else:
            raise
    return _INCIDENT_ASSIGNMENTS_AVAILABLE


def incident_assignments_table_available() -> bool:
    """Public helper for other modules to probe whether incident_assignments can be touched."""
    return _ensure_incident_assignments_available()


def _mark_incident_assignments_unavailable() -> None:
    global _INCIDENT_ASSIGNMENTS_AVAILABLE
    _INCIDENT_ASSIGNMENTS_AVAILABLE = False


def _parse_eta_minutes(value: Any | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = _ETA_MINUTES_PATTERN.search(str(value))
    if match:
        return int(match.group(1))
    return None


def _normalize_assignment_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row or {})
    normalized_eta = normalized.get("eta_minutes")
    if normalized_eta is None:
        normalized_eta = _parse_eta_minutes(normalized.get("eta"))
    normalized["eta_minutes"] = normalized_eta
    if "assigned_at" not in normalized and normalized.get("created_at"):
        normalized["assigned_at"] = normalized["created_at"]
    return normalized


def fetch_latest_assignment(incident_id: str) -> Dict[str, Any] | None:
    if _ensure_incident_assignments_available():
        rows = (
            supabase_admin.table("incident_assignments")
            .select("*")
            .eq("incident_id", incident_id)
            .order("assigned_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return _normalize_assignment_row(rows[0])

    rows = (
        supabase_admin.table("assignments")
        .select("*")
        .eq("incident_id", incident_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    return _normalize_assignment_row(rows[0])


def record_assignment(
    incident_id: str,
    responder_id: str,
    eta_minutes: int,
    assigned_by: str | None = None,
    note: str | None = None,
) -> None:
    supabase_admin.table("assignments").insert(
        {
            "incident_id": incident_id,
            "responder_id": responder_id,
            "eta": f"{eta_minutes} mins",
            "status": "assigned",
        }
    ).execute()

    if not _ensure_incident_assignments_available():
        return

    payload: Dict[str, Any] = {
        "incident_id": incident_id,
        "responder_id": responder_id,
        "eta_minutes": eta_minutes,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
    }
    if assigned_by:
        payload["assigned_by"] = assigned_by
    if note is not None:
        payload["note"] = note

    try:
        supabase_admin.table("incident_assignments").insert(payload).execute()
    except APIError as exc:
        if _looks_like_missing_table_error(exc):
            logging.warning(
                "Incident assignments table became unavailable during insert; falling back to assignments only"
            )
            _mark_incident_assignments_unavailable()
        else:
            raise
