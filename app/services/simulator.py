"""
Digital Twin Simulation Engine

1. Spread Simulation — expands disaster risk across adjacent grid cells
2. Response Impact Comparison — ResQNet vs naive dispatch
"""

from app.services.clustering import haversine_km
from app.services.rescue_allocator import (
    find_nearest_unit, naive_unit, calculate_eta_minutes
)

SPREAD_DECAY = 0.65         # adjacent cells get 65% of source risk
CASUALTY_RATE_PER_MIN = 0.3  # simulated: casualties per extra minute of delay


def simulate_spread(event: dict, existing_grid: list) -> list:
    """
    Expand event risk to the 8 adjacent 0.01-degree grid cells.
    Returns list of {grid_lat, grid_lng, risk_score} for upsert.
    """
    lat = round(event["latitude"] / 0.01) * 0.01
    lng = round(event["longitude"] / 0.01) * 0.01
    base_risk = event.get("confidence", 50)

    existing_map = {(g["grid_lat"], g["grid_lng"]): g for g in existing_grid}

    results = []
    offsets = [-0.01, 0, 0.01]
    for dlat in offsets:
        for dlng in offsets:
            if dlat == 0 and dlng == 0:
                # Source cell gets full risk
                results.append({
                    "grid_lat": round(lat, 2),
                    "grid_lng": round(lng, 2),
                    "risk_score": min(round(base_risk, 1), 100),
                })
            else:
                cell_lat = round(lat + dlat, 2)
                cell_lng = round(lng + dlng, 2)
                existing_score = existing_map.get((cell_lat, cell_lng), {}).get("risk_score", 0)
                new_score = min(round(max(existing_score, base_risk * SPREAD_DECAY), 1), 100)
                results.append({
                    "grid_lat": cell_lat,
                    "grid_lng": cell_lng,
                    "risk_score": new_score,
                })
    return results


def simulate_response_comparison(event: dict, units: list) -> dict:
    """
    Compare ResQNet smart dispatch vs naive (first-available) dispatch.
    Returns response time difference and projected casualty impact.
    """
    elat, elng = event["latitude"], event["longitude"]

    smart = find_nearest_unit(elat, elng, units)
    naive = naive_unit(units)

    if not smart or not naive:
        return {"error": "No available rescue units"}

    smart_dist = haversine_km(elat, elng, smart["latitude"], smart["longitude"])
    naive_dist = haversine_km(elat, elng, naive["latitude"], naive["longitude"])

    smart_eta = calculate_eta_minutes(smart_dist)
    naive_eta = calculate_eta_minutes(naive_dist)

    time_saved = max(0, naive_eta - smart_eta)
    casualties_avoided = round(time_saved * CASUALTY_RATE_PER_MIN, 1)

    return {
        "resqnet": {
            "unit": smart["name"],
            "distance_km": round(smart_dist, 2),
            "eta_minutes": smart_eta,
        },
        "naive": {
            "unit": naive["name"],
            "distance_km": round(naive_dist, 2),
            "eta_minutes": naive_eta,
        },
        "time_saved_minutes": time_saved,
        "projected_casualties_avoided": casualties_avoided,
        "impact_summary": (
            f"ResQNet saves {time_saved} min — preventing ~{casualties_avoided} casualties"
            if time_saved > 0 else "ResQNet selected the same optimal unit"
        ),
    }
