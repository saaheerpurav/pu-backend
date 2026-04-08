"""
Delegates health advice requests to the shared triage service so /health/advice
returns the same strict JSON shape as the WhatsApp triage endpoint.
"""

from app.services.triage import health_advice


def generate_health_advice(symptoms: str) -> dict:
    return health_advice(symptoms)
