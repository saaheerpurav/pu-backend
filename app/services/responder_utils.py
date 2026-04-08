import re
from typing import Any, Mapping

from postgrest import APIError

from app.supabase_client import supabase_admin

_COLUMN_EXISTS_CACHE: dict[tuple[str, str], bool] = {}
_RESPONDERS_TABLE = "responders"
_READY_STATUSES = {"ready", "available", "idle", "online"}


def column_exists(table: str, column: str) -> bool:
    key = (table, column)
    if key in _COLUMN_EXISTS_CACHE:
        return _COLUMN_EXISTS_CACHE[key]
    try:
        exists_query = (
            supabase_admin.table("information_schema.columns")
            .select("column_name")
            .eq("table_schema", "public")
            .eq("table_name", table)
            .eq("column_name", column)
            .limit(1)
            .execute()
        )
    except APIError:
        exists = False
    else:
        exists = bool(exists_query.data)
    _COLUMN_EXISTS_CACHE[key] = exists
    return exists


def availability_to_bool(status: str | None) -> bool:
    if not status:
        return True
    normalized = status.strip().lower()
    return normalized in _READY_STATUSES


def bool_to_availability(value: bool) -> str:
    return "ready" if value else "offline"


def derive_availability(row: Mapping[str, Any]) -> str:
    if "availability" in row:
        value = row.get("availability")
        return value if value else "ready"
    if "available" in row:
        flag = row.get("available")
        if flag is True:
            return "ready"
        if flag is False:
            return "offline"
    if column_exists(_RESPONDERS_TABLE, "availability"):
        value = row.get("availability")
        return value if value else "ready"
    if column_exists(_RESPONDERS_TABLE, "available"):
        flag = row.get("available")
        if flag is True:
            return "ready"
        if flag is False:
            return "offline"
    return "ready"


def safe_responder_update(responder_id: str, payload: dict[str, Any]) -> None:
    if not payload:
        return
    mutable = payload.copy()
    has_available = column_exists(_RESPONDERS_TABLE, "available")
    while mutable:
        try:
            supabase_admin.table(_RESPONDERS_TABLE).update(mutable).eq("id", responder_id).execute()
            return
        except APIError as exc:
            message = getattr(exc, "args", [None])[0]
            if not message:
                raise
            match = re.search(r"Could not find the '([^']+)' column", str(message))
            if not match:
                raise
            missing = match.group(1)
            if missing == "availability" and has_available:
                status_value = mutable.get("availability")
                mutable["available"] = availability_to_bool(status_value)
            mutable.pop(missing, None)
