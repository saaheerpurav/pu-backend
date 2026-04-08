"""
Risk Grid Router
Returns heatmap data for the dashboard.
"""

from fastapi import APIRouter
from app.supabase_client import supabase_admin
from app.services.clustering import haversine_km

router = APIRouter(prefix="/grid", tags=["grid"])


@router.get("")
def get_grid(min_risk: float = 0):
    """All grid cells — dashboard uses this for the heatmap."""
    query = supabase_admin.table("grid_risk").select("*").order("risk_score", desc=True)
    if min_risk > 0:
        query = query.gte("risk_score", min_risk)
    return query.execute().data or []


@router.get("/nearby")
def get_nearby_grid(lat: float, lng: float, radius_km: float = 3.0):
    """Mobile app: grid cells near the user to show local risk."""
    all_cells = supabase_admin.table("grid_risk").select("*").execute().data or []
    nearby = []
    for cell in all_cells:
        dist = haversine_km(lat, lng, cell["grid_lat"], cell["grid_lng"])
        if dist <= radius_km:
            nearby.append({**cell, "distance_km": round(dist, 2)})
    nearby.sort(key=lambda c: c["risk_score"], reverse=True)
    return nearby
