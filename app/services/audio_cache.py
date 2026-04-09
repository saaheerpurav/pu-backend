import time
import uuid
from threading import Lock

_CACHE: dict[str, tuple[bytes, float]] = {}
_LOCK = Lock()
_TTL = 60  # seconds to keep audio before it expires


def _cleanup():
    now = time.time()
    with _LOCK:
        expired = [key for key, (_, ts) in _CACHE.items() if ts <= now]
        for key in expired:
            _CACHE.pop(key, None)


def store_audio_bytes(data: bytes) -> str:
    token = uuid.uuid4().hex
    with _LOCK:
        _cleanup()
        _CACHE[token] = (data, time.time() + _TTL)
    return token


def get_audio_bytes(token: str) -> bytes | None:
    with _LOCK:
        entry = _CACHE.get(token)
        if not entry:
            return None
        data, expires = entry
        if time.time() > expires:
            _CACHE.pop(token, None)
            return None
        return data
