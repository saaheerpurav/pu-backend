"""
Seed realistic disaster events across India's known disaster-prone regions.
Run once: python seed_disasters.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.supabase_client import supabase_admin
from app.services.clustering import snap_to_grid

DISASTERS = [
    # ── FLOODS ──────────────────────────────────────────────────────────
    {
        "type": "flood",
        "latitude": 26.1445, "longitude": 91.7362,
        "confidence": 88.0, "severity": "high",
        "region": "Guwahati, Assam",
        "description": "Brahmaputra river overflowing, low-lying areas submerged",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 10},
        "weather_severity": 82,
    },
    {
        "type": "flood",
        "latitude": 25.8500, "longitude": 85.7833,
        "confidence": 85.0, "severity": "high",
        "region": "Darbhanga, Bihar",
        "description": "Kosi river breached embankment, villages inundated",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 8},
        "weather_severity": 78,
    },
    {
        "type": "flood",
        "latitude": 11.6854, "longitude": 76.1320,
        "confidence": 92.0, "severity": "high",
        "region": "Wayanad, Kerala",
        "description": "Flash floods and landslides following heavy rainfall in Western Ghats",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 15},
        "weather_severity": 91,
    },
    {
        "type": "flood",
        "latitude": 19.0760, "longitude": 72.8777,
        "confidence": 72.0, "severity": "high",
        "region": "Mumbai, Maharashtra",
        "description": "Mithi river flooding, Kurla and Sion waterlogged",
        "source_breakdown": {"app": 2, "whatsapp": 1, "news": 2, "social": 12},
        "weather_severity": 65,
    },
    {
        "type": "flood",
        "latitude": 13.0827, "longitude": 80.2707,
        "confidence": 68.0, "severity": "high",
        "region": "Chennai, Tamil Nadu",
        "description": "Adyar river overflow affecting Velachery and Tambaram",
        "source_breakdown": {"app": 2, "whatsapp": 1, "news": 2, "social": 8},
        "weather_severity": 60,
    },
    {
        "type": "flood",
        "latitude": 20.4625, "longitude": 85.8830,
        "confidence": 78.0, "severity": "high",
        "region": "Cuttack, Odisha",
        "description": "Mahanadi river in spate, coastal districts on alert",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 1, "social": 9},
        "weather_severity": 74,
    },
    {
        "type": "flood",
        "latitude": 22.5726, "longitude": 88.3639,
        "confidence": 55.0, "severity": "medium",
        "region": "Kolkata, West Bengal",
        "description": "Waterlogging in Salt Lake and Dum Dum after heavy overnight rain",
        "source_breakdown": {"app": 1, "whatsapp": 1, "news": 1, "social": 6},
        "weather_severity": 50,
    },
    {
        "type": "flood",
        "latitude": 34.0836, "longitude": 74.7973,
        "confidence": 62.0, "severity": "medium",
        "region": "Srinagar, J&K",
        "description": "Jhelum river rising, Dal Lake area flooded",
        "source_breakdown": {"app": 1, "whatsapp": 2, "news": 1, "social": 5},
        "weather_severity": 58,
    },
    {
        "type": "flood",
        "latitude": 17.3850, "longitude": 78.4867,
        "confidence": 48.0, "severity": "medium",
        "region": "Hyderabad, Telangana",
        "description": "Musi river flooding low-lying areas in old city",
        "source_breakdown": {"app": 1, "whatsapp": 1, "news": 1, "social": 4},
        "weather_severity": 45,
    },

    # ── LANDSLIDES ───────────────────────────────────────────────────────
    {
        "type": "landslide",
        "latitude": 30.4221, "longitude": 79.3347,
        "confidence": 80.0, "severity": "high",
        "region": "Chamoli, Uttarakhand",
        "description": "Major landslide blocking NH-58, rescue teams deployed",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 6},
        "weather_severity": 70,
    },
    {
        "type": "landslide",
        "latitude": 31.1048, "longitude": 77.1734,
        "confidence": 65.0, "severity": "high",
        "region": "Shimla, Himachal Pradesh",
        "description": "Landslide on Shimla-Kalka highway, traffic disrupted",
        "source_breakdown": {"app": 2, "whatsapp": 1, "news": 2, "social": 4},
        "weather_severity": 55,
    },
    {
        "type": "landslide",
        "latitude": 27.0330, "longitude": 88.2663,
        "confidence": 58.0, "severity": "medium",
        "region": "Darjeeling, West Bengal",
        "description": "Hillside collapse near Ghoom, 3 houses damaged",
        "source_breakdown": {"app": 1, "whatsapp": 2, "news": 1, "social": 3},
        "weather_severity": 52,
    },
    {
        "type": "landslide",
        "latitude": 24.8170, "longitude": 93.9368,
        "confidence": 45.0, "severity": "medium",
        "region": "Senapati, Manipur",
        "description": "Mudslide on NH-2 following continuous rainfall",
        "source_breakdown": {"app": 1, "whatsapp": 1, "news": 1, "social": 2},
        "weather_severity": 48,
    },

    # ── EARTHQUAKES ──────────────────────────────────────────────────────
    {
        "type": "earthquake",
        "latitude": 23.2419, "longitude": 69.6669,
        "confidence": 95.0, "severity": "high",
        "region": "Bhuj, Gujarat",
        "description": "5.8 magnitude earthquake, tremors felt across Kutch district",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 15},
        "weather_severity": 10,
    },
    {
        "type": "earthquake",
        "latitude": 27.5330, "longitude": 88.5122,
        "confidence": 75.0, "severity": "high",
        "region": "Gangtok, Sikkim",
        "description": "4.9 magnitude quake, buildings evacuated in city centre",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 1, "social": 8},
        "weather_severity": 0,
    },
    {
        "type": "earthquake",
        "latitude": 22.7196, "longitude": 88.3432,
        "confidence": 82.0, "severity": "high",
        "region": "Kolkata, West Bengal",
        "description": "5.4 magnitude earthquake, offices evacuated across the city",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 12},
        "weather_severity": 0,
    },
    {
        "type": "earthquake",
        "latitude": 30.9457, "longitude": 79.1088,
        "confidence": 50.0, "severity": "medium",
        "region": "Uttarkashi, Uttarakhand",
        "description": "4.2 magnitude tremors, cracks reported in older structures",
        "source_breakdown": {"app": 1, "whatsapp": 1, "news": 1, "social": 3},
        "weather_severity": 0,
    },

    # ── CYCLONES ────────────────────────────────────────────────────────
    {
        "type": "other",
        "latitude": 17.6868, "longitude": 83.2185,
        "confidence": 90.0, "severity": "high",
        "region": "Visakhapatnam, Andhra Pradesh",
        "description": "Cyclone Horacio making landfall, Category 2, 150kmph winds",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 15},
        "weather_severity": 95,
    },
    {
        "type": "other",
        "latitude": 19.8135, "longitude": 85.8312,
        "confidence": 78.0, "severity": "high",
        "region": "Puri, Odisha",
        "description": "Severe cyclonic storm approaching coast, evacuation ordered for 5 districts",
        "source_breakdown": {"app": 2, "whatsapp": 2, "news": 2, "social": 9},
        "weather_severity": 88,
    },

    # ── FIRES ───────────────────────────────────────────────────────────
    {
        "type": "fire",
        "latitude": 29.9457, "longitude": 79.5431,
        "confidence": 70.0, "severity": "high",
        "region": "Nainital, Uttarakhand",
        "description": "Forest fire spreading in Kumaon hills, 200 hectares affected",
        "source_breakdown": {"app": 2, "whatsapp": 1, "news": 2, "social": 7},
        "weather_severity": 30,
    },
    {
        "type": "fire",
        "latitude": 25.4670, "longitude": 94.0236,
        "confidence": 55.0, "severity": "medium",
        "region": "Nagaland",
        "description": "Forest fire in Dzukou Valley, fire brigade teams deployed",
        "source_breakdown": {"app": 1, "whatsapp": 1, "news": 2, "social": 4},
        "weather_severity": 20,
    },
]


def seed():
    print("Seeding disaster events...")
    inserted = 0
    skipped = 0

    for d in DISASTERS:
        base = {
            "type": d["type"],
            "latitude": d["latitude"],
            "longitude": d["longitude"],
            "confidence": d["confidence"],
            "severity": d["severity"],
        }
        try:
            res = supabase_admin.table("disaster_events").insert({
                **base,
                "source_breakdown": d["source_breakdown"],
                "weather_severity": d["weather_severity"],
                "active": True,
            }).execute()
        except Exception:
            try:
                res = supabase_admin.table("disaster_events").insert(base).execute()
            except Exception as e:
                print(f"  [!] Skipped {d['region']}: {e}")
                skipped += 1
                continue

        event_id = res.data[0]["id"] if res.data else None

        # Seed a report for this event
        if event_id:
            try:
                supabase_admin.table("reports").insert({
                    "source": "app",
                    "event_id": event_id,
                    "latitude": d["latitude"],
                    "longitude": d["longitude"],
                    "description": d["description"],
                }).execute()
            except Exception:
                pass

            # Update grid
            grid_lat, grid_lng = snap_to_grid(d["latitude"], d["longitude"])
            try:
                supabase_admin.table("grid_risk").upsert({
                    "grid_lat": grid_lat,
                    "grid_lng": grid_lng,
                    "risk_score": min(round(d["confidence"] * 0.9, 1), 100),
                    "updated_at": "now()",
                }, on_conflict="grid_lat,grid_lng").execute()
            except Exception:
                pass

        print(f"  + [{d['severity'].upper():6}] {d['region']} — {d['type']} ({d['confidence']}%)")
        inserted += 1

    print(f"\nDone. {inserted} events seeded, {skipped} skipped.")


if __name__ == "__main__":
    seed()
