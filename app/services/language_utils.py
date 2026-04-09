from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

SUPPORTED_LANGUAGES = {"hi", "kn", "te"}
FALLBACK_MAP = {
    "ur": "hi",
}


def normalize_language(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.strip().lower()
    normalized = FALLBACK_MAP.get(normalized, normalized)
    if normalized in SUPPORTED_LANGUAGES:
        return normalized
    return None


def infer_language(text: str) -> str | None:
    if not text:
        return None
    try:
        detected = detect(text)
    except LangDetectException:
        return None
    return normalize_language(detected)
