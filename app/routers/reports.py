"""
Reports Router
Mobile app submits disaster reports here.
Core flow: report → geo-cluster → create/update event → recalculate confidence → update grid
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from app.supabase_client import supabase_admin
from app.services.report_service import submit_report as _submit

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportRequest(BaseModel):
    source: str
    latitude: float
    longitude: float
    disaster_type: str
    description: str = None
    people_count: int = 1
    injuries: bool = False
    weather_severity: float = 0


class ReportResponse(BaseModel):
    id: str
    source: str
    event_id: Optional[str] = None
    latitude: float
    longitude: float
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    disaster_type: Optional[str] = None
    people_count: Optional[int] = None
    injuries: Optional[bool] = None
    weather_severity: Optional[float] = None


@router.post("")
def submit_report(body: ReportRequest):
    try:
        result = _submit(
            source=body.source,
            latitude=body.latitude,
            longitude=body.longitude,
            disaster_type=body.disaster_type,
            description=body.description,
            people_count=body.people_count,
            injuries=body.injuries,
            weather_severity=body.weather_severity,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {**result, "message": "Report submitted and event updated"}


@router.get("", response_model=List[ReportResponse])
def list_reports(limit: int = 50, source: str = None, event_id: str = None):
    query = supabase_admin.table("reports").select("*").order("created_at", desc=True).limit(limit)
    if source:
        query = query.eq("source", source)
    if event_id:
        query = query.eq("event_id", event_id)
    return query.execute().data or []


@router.get("/{report_id}")
def get_report(report_id: str):
    res = supabase_admin.table("reports").select("*").eq("id", report_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Report not found")
    return res.data
