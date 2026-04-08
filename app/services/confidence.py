"""
Confidence Scoring Engine

Designed so:
  1 report (app/whatsapp)              → ~25-30%  (possible event)
  2-3 reports same area                → ~50-60%  (likely event)
  5+ reports + news/weather            → 80-100%  (confirmed)

Weights are per-report but capped at low counts so cross-source
validation is what pushes confidence to the top.
"""

WEIGHTS = {
    "app":      30.0,   # 1 = 30, cap 2 → max 60
    "whatsapp": 25.0,   # 1 = 25, cap 2 → max 50
    "news":     20.0,   # 1 = 20, cap 2 → max 40
    "social":    2.0,   # per hit, cap 15 → max 30
}
WEATHER_WEIGHT = 0.3    # severity 0–100 → max 30 pts

MAX_COUNTS = {
    "app":      2,
    "whatsapp": 2,
    "news":     2,
    "social":   15,
}

# What each scenario produces (for reference):
# 1 WhatsApp report                        = 25%  (low severity)
# 1 app report                             = 30%  (low severity)
# 2 app reports                            = 60%  (medium)
# 1 app + 1 news                           = 50%  (medium)
# 2 app + 1 news + weather(50)             = 75%  (high)
# 2 app + 2 news + 15 social + weather(80) = 100% (confirmed)


def calculate_confidence(source_counts: dict, weather_severity: float = 0) -> float:
    score = 0.0
    for source, weight in WEIGHTS.items():
        count = min(source_counts.get(source, 0), MAX_COUNTS[source])
        score += weight * count
    score += WEATHER_WEIGHT * min(weather_severity, 100)
    return min(round(score, 1), 100.0)


def get_severity(confidence: float) -> str:
    if confidence >= 65:
        return "high"
    elif confidence >= 35:
        return "medium"
    return "low"
