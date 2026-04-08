from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, UUID4
from postgrest import APIError

from app.supabase_client import supabase_admin


class NFCScanRequest(BaseModel):
    card_user_id: UUID4
    tag_payload: dict[str, Any] | None = None
    reader_context: dict[str, Any] | None = None
    reader_context_error: str | None = None
    profile_snapshot: dict[str, Any] | None = None
    profile_fetch_error: str | None = None
    scanner_user_id: UUID4 | None = None


router = APIRouter(prefix="/nfc", tags=["nfc"])


def _fetch_latest_scan(card_user_id: str):
    res = (
        supabase_admin.table("nfc_card_scans")
        .select("*")
        .eq("card_user_id", card_user_id)
        .order("scanned_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


@router.get("/profile/{user_id}")
def get_nfc_profile(user_id: str):
    try:
        profile_res = (
            supabase_admin.table("users")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except APIError:
        profile_res = None
    profile = profile_res.data[0] if profile_res and profile_res.data else None
    scan_row = _fetch_latest_scan(user_id)

    reader_context = scan_row.get("reader_context") if scan_row else None

    if profile:
        payload = {
            "name": profile.get("name"),
            "blood_group": profile.get("blood_group", "Unknown"),
            "allergies": profile.get("allergies", "None"),
            "emergency_contact": profile.get("phone"),
        }
        if reader_context:
            payload["reader_context"] = reader_context
        return payload

    if not scan_row:
        raise HTTPException(status_code=404, detail="Profile not found")

    snapshot = scan_row.get("profile_snapshot") or scan_row.get("tag_payload") or {}
    return {
        "name": snapshot.get("name"),
        "blood_group": snapshot.get("blood_group", "Unknown"),
        "allergies": snapshot.get("allergies") or snapshot.get("health_conditions", "None"),
        "emergency_contact": snapshot.get("emergency_contact") or snapshot.get("phone"),
        "scanned_at": scan_row.get("scanned_at"),
        "reader_context": reader_context,
    }


@router.post("/scans", status_code=201)
def ingest_nfc_scan(body: NFCScanRequest):
    payload = {
        "card_user_id": str(body.card_user_id),
        "tag_payload": body.tag_payload,
        "reader_context": body.reader_context,
        "reader_context_error": body.reader_context_error,
        "profile_snapshot": body.profile_snapshot,
        "profile_fetch_error": body.profile_fetch_error,
        "scanner_user_id": str(body.scanner_user_id) if body.scanner_user_id else None,
    }
    try:
        res = supabase_admin.table("nfc_card_scans").insert(payload).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to record NFC scan") from exc
    row = res.data[0] if res.data else {}
    return {
        "id": row.get("id"),
        "card_user_id": row.get("card_user_id"),
        "scanned_at": row.get("scanned_at"),
    }


@router.get("/scans")
def list_nfc_scans(limit: int = 50, card_user_id: UUID4 | None = None):
    sanitized_limit = max(1, min(limit, 500))
    query = (
        supabase_admin.table("nfc_card_scans")
        .select("*")
        .order("scanned_at", desc=True)
        .limit(sanitized_limit)
    )
    if card_user_id:
        query = query.eq("card_user_id", str(card_user_id))
    rows = query.execute().data or []
    return {
        "items": [
            {
                "id": row.get("id"),
                "card_user_id": row.get("card_user_id"),
                "scanner_user_id": row.get("scanner_user_id"),
                "scanned_at": row.get("scanned_at"),
                "tag_payload": row.get("tag_payload"),
                "reader_context": row.get("reader_context"),
                "reader_context_error": row.get("reader_context_error"),
                "profile_snapshot": row.get("profile_snapshot"),
                "profile_fetch_error": row.get("profile_fetch_error"),
            }
            for row in rows
        ],
        "count": len(rows),
    }
