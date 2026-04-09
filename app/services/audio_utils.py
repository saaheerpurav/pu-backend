import asyncio
import io
import re

import edge_tts

VOICES = {
    "en-IN": "en-IN-NeerjaNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "kn-IN": "kn-IN-SapnaNeural",
    "te-IN": "te-IN-ShrutiNeural",
}
DEFAULT_VOICE = "en-IN-NeerjaNeural"


def detect_lang(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "hi-IN"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn-IN"
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te-IN"
    return "en-IN"


def strip_markdown(text: str) -> str:
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`+(.+?)`+", r"\1", text)
    text = re.sub(r"^\s*[-•*→‘“]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    for old, new in [("₹", "rupees "), ("°C", " degrees Celsius"), ("°F", " degrees Fahrenheit"), ("°", " degrees")]:
        text = text.replace(old, new)
    text = text.replace("%", " percent")
    text = text.replace("#", "")
    text = text.replace("|", "")
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", ", ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def truncate_for_speech(text: str, max_chars: int = 400) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in (".", "!", "?", ","):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[: idx + 1].strip()
    return cut.strip()


def prepare_for_tts(text: str, fallback: str = "Sorry, I could not generate a response.") -> str:
    cleaned = truncate_for_speech(strip_markdown(text))
    speakable = re.sub(r"[^\w\s]", "", cleaned).strip()
    if not speakable:
        return fallback
    return cleaned


async def _create_tts_bytes(text: str) -> bytes:
    clean = prepare_for_tts(text)
    lang = detect_lang(clean)
    voice = VOICES.get(lang, DEFAULT_VOICE)
    communicate = edge_tts.Communicate(clean, voice, rate="+15%")
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    if buf.tell() == 0:
        raise RuntimeError(f"edge-tts returned no audio for text: {clean[:80]}")
    return buf.getvalue()


def generate_tts(text: str) -> bytes:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_create_tts_bytes(text))
    finally:
        loop.close()
