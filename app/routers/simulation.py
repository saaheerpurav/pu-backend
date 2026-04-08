"""
Digital Twin Simulation Router
Spread simulation + ResQNet vs naive response comparison.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.supabase_client import supabase_admin
from app.services.simulator import simulate_spread, simulate_response_comparison

router = APIRouter(prefix="/simulation", tags=["simulation"])


class SpreadRequest(BaseModel):
    event_id: str


class CompareRequest(BaseModel):
    event_id: str


@router.post("/spread")
def run_spread_simulation(body: SpreadRequest):
    """
    Simulate disaster spreading to adjacent grid cells.
    Writes updated risk scores to grid_risk table.
    """
    event = supabase_admin.table("disaster_events").select("*").eq("id", body.event_id).single().execute()
    if not event.data:
        raise HTTPException(status_code=404, detail="Event not found")

    existing_grid = supabase_admin.table("grid_risk").select("*").execute().data or []
    affected_cells = simulate_spread(event.data, existing_grid)

    # Upsert all affected cells
    for cell in affected_cells:
        supabase_admin.table("grid_risk").upsert({
            "grid_lat": cell["grid_lat"],
            "grid_lng": cell["grid_lng"],
            "risk_score": cell["risk_score"],
            "updated_at": "now()",
        }, on_conflict="grid_lat,grid_lng").execute()

    return {
        "event_id": body.event_id,
        "cells_affected": len(affected_cells),
        "spread_data": affected_cells,
    }


@router.post("/compare")
def run_response_comparison(body: CompareRequest):
    """
    Compare ResQNet smart dispatch vs naive dispatch.
    Returns time saved and projected casualty impact.
    """
    event = supabase_admin.table("disaster_events").select("*").eq("id", body.event_id).single().execute()
    if not event.data:
        raise HTTPException(status_code=404, detail="Event not found")

    # Use ALL units (including busy) for simulation — don't modify state
    all_units = supabase_admin.table("rescue_units").select("*").execute().data or []
    available_units = [u for u in all_units if u["status"] == "available"]

    if not available_units:
        # For demo: reset all units temporarily for simulation
        available_units = all_units

    return simulate_response_comparison(event.data, available_units)
