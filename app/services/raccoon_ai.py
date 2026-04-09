import logging
import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from requests import RequestException

from app.schemas.confidence import ConfidenceRequest

logger = logging.getLogger(__name__)

RACOON_LAM_URL = "https://api.raccoonai.tech/lam/run"
load_dotenv()
RACOON_API_KEY = os.getenv("RACOONAI_API_KEY")
RACOON_PASSCODE = os.getenv("RACOONAI_PASSCODE")


def _build_query_text(payload: ConfidenceRequest) -> str:
    fragments: List[str] = []
    counts = payload.report_counts
    for label, count in counts.items():
        if count:
            fragments.append(f"{count} {label} report{'s' if count != 1 else ''}")
    if payload.weather_severity is not None:
        fragments.append(f"weather severity around {payload.weather_severity:.1f}/10")
    if payload.local_grid_risk_score is not None:
        fragments.append(f"local grid risk score {payload.local_grid_risk_score:.1f}")
    if payload.nearby_ready_responders is not None:
        fragments.append(f"{payload.nearby_ready_responders} ready responders nearby")
    if payload.eonet_event_count_24h is not None:
        fragments.append(f"{payload.eonet_event_count_24h} EONET events in the last 24h")
    if payload.source_entropy is not None:
        fragments.append(f"source entropy {payload.source_entropy:.2f}")
    if not fragments:
        fragments.append("no signals yet")
    return "; ".join(fragments)


def _normalize_reasons(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(part) for part in value if part]
    return []


def score_confidence_with_raccoon(payload: ConfidenceRequest) -> Optional[Dict[str, Any]]:
    if not RACOON_API_KEY:
        logger.debug("Raccoon AI key missing, skipping integration")
        return None
    if not RACOON_PASSCODE:
        logger.warning("Raccoon AI passcode missing, skipping integration")
        return None

    headers = {
        "Content-Type": "application/json",
        "raccoon-secret-key": RACOON_API_KEY,
    }
    schema = {
        "confidence": "Normalized confidence between 0 and 1, where 0 = no trust and 1 = fully confirmed",
        "reasons": "Short bullet list of why the score changed",
    }
    body = {
        "query": (
            "Assess the disaster confidence based on the following signals: "
            + _build_query_text(payload)
        ),
        "schema": schema,
        "max_count": 1,
        "mode": "deepsearch",
        "stream": False,
        "raccoon_passcode": RACOON_PASSCODE,
    }

    try:
        response = requests.post(RACOON_LAM_URL, headers=headers, json=body, timeout=20)
        response.raise_for_status()
        data = response.json().get("data") or []
        if not data:
            logger.warning("Raccoon AI returned no data for confidence payload")
            return None
        item = data[0]
        confidence = item.get("confidence")
        if confidence is None:
            confidence = item.get("confidence_score")
        if confidence is None:
            logger.warning("Raccoon AI response missing confidence field")
            return None
        reasons = item.get("reasons") or item.get("summary") or item.get("properties") or []
        normalized = min(max(float(confidence), 0.0), 1.0)
        return {
            "confidence": normalized,
            "base_confidence": normalized,
            "reasons": _normalize_reasons(reasons),
        }
    except RequestException as exc:
        logger.warning("Raccoon AI call failed: %s", exc)
        return None
    except ValueError:
        logger.warning("Raccoon AI returned non-json response")
        return None
