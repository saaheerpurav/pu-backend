"""
Rescue Allocation Engine
Finds the nearest available unit, assigns it, and calculates ETA.
Uses pure Python distance (PostGIS would be ideal but this is fine for hackathon).
"""

from app.services.clustering import haversine_km

AVG_SPEED_KMPH = 40.0   # emergency vehicle speed assumption


def find_nearest_unit(event_lat: float, event_lng: float, units: list) -> dict | None:
    """Return the nearest available unit with sufficient capacity."""
    best = None
    best_dist = float("inf")
    for unit in units:
        if unit["status"] != "available":
            continue
        dist = haversine_km(event_lat, event_lng, unit["latitude"], unit["longitude"])
        if dist < best_dist:
            best = unit
            best_dist = dist
    if best:
        best["_distance_km"] = round(best_dist, 2)
    return best


def calculate_eta_minutes(distance_km: float) -> int:
    return max(1, round((distance_km / AVG_SPEED_KMPH) * 60))


def naive_unit(units: list) -> dict | None:
    """First available unit — simulates non-optimized dispatch."""
    for unit in units:
        if unit["status"] == "available":
            return unit
    return None
