from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.clustering import haversine_km
from app.services.rescue_allocator import calculate_eta_minutes
from app.services.responder_utils import column_exists, derive_availability
from app.supabase_client import supabase_admin

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


class DispatchOptimizeRequest(BaseModel):
    incident_id: str
    latitude: float
    longitude: float
    required_unit: str


def _fetch_ready_responders() -> list[dict]:
    query = supabase_admin.table("responders").select("*")
    if column_exists("responders", "availability"):
        return query.eq("availability", "ready").execute().data or []
    if column_exists("responders", "available"):
        return query.eq("available", True).execute().data or []
    candidates = query.execute().data or []
    return [unit for unit in candidates if derive_availability(unit) == "ready"]


@router.post("/optimize")
def optimize_dispatch(body: DispatchOptimizeRequest):
    responders = _fetch_ready_responders()
    candidates = [r for r in responders if r.get("type") == body.required_unit]
    if not candidates:
        candidates = responders

    if not candidates:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="No eligible responders available")

    enriched = []
    for responder in candidates:
        distance = haversine_km(body.latitude, body.longitude, responder["latitude"], responder["longitude"])
        enriched.append({**responder, "distance": distance})

    enriched.sort(key=lambda item: item["distance"])
    best = enriched[0]
    eta = calculate_eta_minutes(best["distance"])
    alternates = [
        {
            "id": item["id"],
            "eta_minutes": calculate_eta_minutes(item["distance"]),
            "distance_km": round(item["distance"], 2),
        }
        for item in enriched[1:3]
    ]

    return {
        "selected_responder": {
            "id": best["id"],
            "name": best.get("name"),
            "distance_km": round(best["distance"], 2),
            "eta_minutes": eta,
        },
        "alternates": alternates,
        "hospital_recommendation": {
            "name": "City Trauma Center",
            "distance_km": 4.3,
            "capacity_status": "available",
        },
    }
