from fastapi import APIRouter

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("/safe")
def safe_route(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
):
    """
    Returns a mock safe corridor between two points; can be replaced with real routing data later.
    """
    return {
        "polyline": "}_p~F~ps|U_ulLnnqC_mqNvxq`@",
        "from": {"lat": from_lat, "lng": from_lng},
        "to": {"lat": to_lat, "lng": to_lng},
        "distance_km": 4.3,
        "travel_time_minutes": 12,
        "avoid": ["flooded_zone", "fire_boundary"],
    }
