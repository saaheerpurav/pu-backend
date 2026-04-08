from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.sos_service import create_sos_incident
from app.supabase_client import supabase_admin

router = APIRouter(prefix="/wearables", tags=["wearables"])


class FallDetectedRequest(BaseModel):
    user_id: str
    device_id: str
    event_time: str
    latitude: float
    longitude: float
    impact_score: float
    heart_rate: float | None = None


class HeartAlertRequest(BaseModel):
    user_id: str
    device_id: str
    heart_rate: float
    latitude: float
    longitude: float
    event_time: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/wearables/fall-detected")
def fall_detected(body: FallDetectedRequest):
    event_payload = {
        "event_time": body.event_time,
        "impact_score": body.impact_score,
        "heart_rate": body.heart_rate,
    }
    supabase_admin.table("wearable_events").insert({
        "user_id": body.user_id,
        "device_id": body.device_id,
        "event_type": "fall_detected",
        "payload_json": event_payload,
        "created_at": _now_iso(),
    }).execute()

    incident = create_sos_incident(
        user_id=body.user_id,
        incident_type="fall",
        latitude=body.latitude,
        longitude=body.longitude,
        source="wearable",
    )

    return {
        "message": "Fall detected and SOS triggered",
        "incident_id": incident["incident_id"],
        "status": incident["status"],
    }


@router.post("/wearables/heart-alert")
def heart_alert(body: HeartAlertRequest):
    event_payload = {
        "event_time": body.event_time or _now_iso(),
        "heart_rate": body.heart_rate,
    }
    supabase_admin.table("wearable_events").insert({
        "user_id": body.user_id,
        "device_id": body.device_id,
        "event_type": "heart_alert",
        "payload_json": event_payload,
        "created_at": _now_iso(),
    }).execute()

    incident = create_sos_incident(
        user_id=body.user_id,
        incident_type="medical",
        latitude=body.latitude,
        longitude=body.longitude,
        source="wearable",
    )

    return {
        "message": "Heart alert recorded and SOS dispatched",
        "incident_id": incident["incident_id"],
        "status": incident["status"],
    }
