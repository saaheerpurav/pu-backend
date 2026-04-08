"""
Geo-Clustering — assigns incoming reports to existing events or creates new ones.
Uses a simple 1km radius threshold (no ML needed for hackathon).
"""

import math

CLUSTER_RADIUS_KM = 1.0
GRID_PRECISION = 2   # ~1.1km per 0.01 degree


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in km between two points."""
    R = 6371.0
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def find_nearest_event(lat: float, lng: float, events: list) -> dict | None:
    """
    Given a list of active disaster_event dicts, return the nearest one
    within CLUSTER_RADIUS_KM, or None if no match.
    """
    best = None
    best_dist = float("inf")
    for event in events:
        dist = haversine_km(lat, lng, event["latitude"], event["longitude"])
        if dist <= CLUSTER_RADIUS_KM and dist < best_dist:
            best = event
            best_dist = dist
    return best


def snap_to_grid(lat: float, lng: float) -> tuple[float, float]:
    """Snap lat/lng to the nearest 0.01-degree grid cell (~1km)."""
    return (
        round(round(lat / 0.01) * 0.01, GRID_PRECISION),
        round(round(lng / 0.01) * 0.01, GRID_PRECISION),
    )
