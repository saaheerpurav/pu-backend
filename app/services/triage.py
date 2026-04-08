"""
AI triage helpers for WhatsApp, health advice, and other OpenAI-driven touchpoints.
Provides structured JSON, language detection, fallback rules, and observability logging.
"""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from langdetect import DetectorFactory, LangDetectException, detect

from app.services.llm import get_client
from app.supabase_client import supabase_admin

DetectorFactory.seed = 0

PROMPT_VERSION = "triage-v1.0"
COMPACT_MODEL = "gpt-4o-mini"
GUIDANCE_MODEL = "gpt-4o"
DEFAULT_LANGUAGE = "en"

SYSTEM_PROMPT = """You are ResQNet's emergency triage assistant.
Answer as a compassionate, decisive emergency professional who never offers a definitive diagnosis.
Use short actionable phrases and always match the user's language (indicated by language_code).
Return a strict JSON object with the following keys:
  - severity: one of low, medium, high
  - steps: array of 1-5 concise first-aid or safety steps
  - medicines: array of 1-4 OTC-friendly recommendations (include Indian-brand names when possible)
  - dispatch_recommended: boolean (true when authorities should be dispatched)
  - confidence: number between 0 and 1 representing your confidence in the result
Do not include any extra explanation outside the JSON object.
"""

RULES = [
    {
        "keywords": ["bleeding", "cut", "wound", "injury"],
        "severity": "medium",
        "steps": [
            "Apply firm pressure with a clean cloth.",
            "Elevate the limb and keep it still.",
            "Monitor for heavy bleeding and seek help if it continues.",
        ],
        "medicines": ["Antiseptic spray", "Paracetamol", "ORS sachets"],
    },
    {
        "keywords": ["burn", "burning", "scald"],
        "severity": "high",
        "steps": [
            "Run cool water over the burn for 20 minutes.",
            "Do not rub or apply oil; cover with a clean cloth.",
            "Escalate to responders if blisters form or pain is severe.",
        ],
        "medicines": ["Burn care gel", "Paracetamol", "Avil syrup"],
    },
    {
        "keywords": ["pain", "chest", "breathing", "faint", "unconscious"],
        "severity": "high",
        "steps": [
            "Keep the person still and comfort them.",
            "Call local emergency services immediately.",
            "Monitor breathing and start CPR if needed.",
        ],
        "medicines": ["Aspirin only if already prescribed"],
    },
    {
        "keywords": ["fever", "headache", "cold", "vomit", "nausea"],
        "severity": "medium",
        "steps": [
            "Rest in a cool, shaded place and sip clean water.",
            "Monitor for worsening symptoms or breathing trouble.",
            "Seek help if fever persists or dehydration signs appear.",
        ],
        "medicines": ["Paracetamol", "ORS sachet"],
    },
]


def _detect_language(text: str, hint: Optional[str]) -> str:
    if hint:
        return hint
    try:
        return detect(text or "") or DEFAULT_LANGUAGE
    except LangDetectException:
        return DEFAULT_LANGUAGE


def _normalize_choices(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1", "dispatch")
    if isinstance(value, (int, float)):
        return value >= 0.5
    return False


def _normalize_confidence(value: Any) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, conf))


def _fallback_triage(message: str, language: str) -> Dict[str, Any]:
    text = (message or "").lower()
    for rule in RULES:
        if any(keyword in text for keyword in rule["keywords"]):
            severity = rule["severity"]
            dispatch = severity in ("high",)
            return {
                "severity": severity,
                "steps": rule["steps"],
                "medicines": rule["medicines"],
                "dispatch_recommended": dispatch,
                "confidence": 0.75 if severity == "high" else 0.55,
                "language": language,
            }
    return {
        "severity": "medium",
        "steps": [
            "Stay calm and move to a safe place.",
            "Rehydrate and monitor symptoms hourly.",
            "Call for help if breathing worsens or consciousness drops.",
        ],
        "medicines": ["Paracetamol", "ORS sachet"],
        "dispatch_recommended": False,
        "confidence": 0.5,
        "language": language,
    }


def _log_ai_call(
    feature: str,
    model: str,
    prompt_version: str,
    latency_ms: float,
    confidence: float,
    escalation: bool,
    language: str,
    message_hash: str,
) -> None:
    try:
        supabase_admin.table("ai_logs").insert({
            "feature": feature,
            "model": model,
            "prompt_version": prompt_version,
            "latency_ms": round(latency_ms),
            "confidence": round(confidence, 3),
            "escalation": escalation,
            "language_code": language,
            "message_hash": message_hash,
        }).execute()
    except Exception:
        pass


def _call_model(model: str, message: str, language: str, extra_context: Optional[str] = None) -> Dict[str, Any]:
    payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"language_code: {language}\n"
                f"{extra_context or ''}\n"
                f"User message: {message}"
            ),
        },
    ]

    response = get_client().chat.completions.create(
        model=model,
        messages=payload,
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=320,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _validate_response(payload: Dict[str, Any]) -> bool:
    if not payload:
        return False
    severity = str(payload.get("severity", "")).lower()
    if severity not in {"low", "medium", "high"}:
        return False
    if not _normalize_choices(payload.get("steps")):
        return False
    if not _normalize_choices(payload.get("medicines")):
        return False
    if "dispatch_recommended" not in payload:
        return False
    return True


def _build_result(payload: Dict[str, Any], language: str) -> Dict[str, Any]:
    severity = str(payload.get("severity", "medium")).lower()
    steps = _normalize_choices(payload.get("steps"))
    medicines = _normalize_choices(payload.get("medicines"))
    if len(steps) > 5:
        steps = steps[:5]
    if len(medicines) > 4:
        medicines = medicines[:4]

    dispatch = _normalize_boolean(payload.get("dispatch_recommended"))
    confidence = _normalize_confidence(payload.get("confidence", 0.6))

    return {
        "severity": severity if severity in {"low", "medium", "high"} else "medium",
        "steps": steps or ["Move to a safe place and seek help if unsure."],
        "medicines": medicines or ["Paracetamol"],
        "dispatch_recommended": dispatch,
        "confidence": confidence,
        "language": language,
    }


def triage_message(
    message: str,
    feature: str,
    language_hint: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> Dict[str, Any]:
    language = _detect_language(message, language_hint)
    normalized_message = message or "No symptoms provided."
    message_hash = hashlib.sha256(normalized_message.encode("utf-8")).hexdigest()

    start = time.monotonic()
    try:
        payload = _call_model(COMPACT_MODEL, normalized_message, language, extra_context)
        latency = (time.monotonic() - start) * 1000
        if not _validate_response(payload):
            raise ValueError("Invalid response payload")
        result = _build_result(payload, language)
        model_used = COMPACT_MODEL

        if result["severity"] == "high" or result["dispatch_recommended"]:
            extra_payload = _call_model(
                GUIDANCE_MODEL,
                normalized_message,
                language,
                extra_context or "Refine the safety steps with more detail before dispatching.",
            )
            extra_latency = (time.monotonic() - start) * 1000 - latency
            if _validate_response(extra_payload):
                result = _build_result(extra_payload, language)
                latency += max(extra_latency, 0)
                model_used = GUIDANCE_MODEL
    except Exception:
        latency = (time.monotonic() - start) * 1000
        result = _fallback_triage(normalized_message, language)
        model_used = "fallback"
    finally:
        _log_ai_call(
            feature=feature,
            model=model_used,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency,
            confidence=result.get("confidence", 0.5),
            escalation=result.get("dispatch_recommended", False),
            language=language,
            message_hash=message_hash,
        )

    return result


def health_advice(message: str) -> Dict[str, Any]:
    return triage_message(message, feature="health-advice")
