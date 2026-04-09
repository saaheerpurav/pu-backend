from fastapi import APIRouter, HTTPException, Response

from app.services.audio_cache import get_audio_bytes

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/{token}.mp3")
def stream_audio(token: str):
    data = get_audio_bytes(token)
    if not data:
        raise HTTPException(status_code=404, detail="Audio not found or expired")
    return Response(content=data, media_type="audio/mpeg")
