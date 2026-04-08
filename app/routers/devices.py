from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.supabase_client import supabase_admin

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegisterRequest(BaseModel):
    user_id: str
    device_type: str
    device_id: str
    platform: str
    push_token: str | None = None


@router.post("/register")
def register_device(body: DeviceRegisterRequest):
    now_iso = datetime.now(timezone.utc).isoformat()
    res = supabase_admin.table("devices").insert({
        "user_id": body.user_id,
        "device_type": body.device_type,
        "device_id": body.device_id,
        "platform": body.platform,
        "push_token": body.push_token,
        "last_seen_at": now_iso,
    }).execute()

    return {
        "message": "Device registered",
        "device_record_id": res.data[0]["id"] if res.data else None,
    }
