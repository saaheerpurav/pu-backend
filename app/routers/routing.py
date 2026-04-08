"""
Routing helpers for responder dispatch and the digital twin.
"""

import logging
from typing import Literal

import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/routing", tags=["routing"])
logger = logging.getLogger("resqnet.backend.routing")

OSRM_ENDPOINT = "https://router.project-osrm.org/route/v1/driving"


@router.get("/driving")
def driving_route(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    overview: Literal["full", "simplified", "false"] = "full",
    steps: bool = False,
) -> dict:
    url = f"{OSRM_ENDPOINT}/{from_lng},{from_lat};{to_lng},{to_lat}"
    params = {
        "overview": overview,
        "geometries": "geojson",
        "steps": str(steps).lower(),
    }
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.warning("OSRM request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Routing provider unavailable") from exc

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise HTTPException(status_code=502, detail="Routing response invalid")

    route = payload["routes"][0]
    geometry = route.get("geometry")
    return {
        "distance_km": round(route.get("distance", 0) / 1000, 2),
        "travel_time_minutes": round(route.get("duration", 0) / 60, 2),
        "geometry": geometry,
        "summary": route.get("summary"),
        "legs": route.get("legs"),
        "weight_name": route.get("weight_name"),
        "status": payload.get("code"),
    }
