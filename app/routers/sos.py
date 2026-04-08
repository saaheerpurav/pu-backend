from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.sos_service import create_sos_incident


router = APIRouter(tags=["sos"])


class SOSRequest(BaseModel):
    user_id: str | None = None
    type: str
    latitude: float | None = None
    longitude: float | None = None
    source: str
    context: dict[str, Any] | None = None


@router.post("/sos")
def trigger_sos(body: SOSRequest):
    return create_sos_incident(
        user_id=body.user_id,
        incident_type=body.type,
        latitude=body.latitude,
        longitude=body.longitude,
        source=body.source,
        context=body.context,
    )
