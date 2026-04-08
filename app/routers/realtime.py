import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.realtime_broker import realtime_broker
from app.supabase_client import supabase_admin

router = APIRouter(prefix="/realtime", tags=["realtime"])


def _snapshot(channel_name: str) -> list[dict]:
    table = realtime_broker.get_table(channel_name)
    try:
        return supabase_admin.table(table) \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(20) \
            .execute().data or []
    except Exception:
        return []


@router.get("/{channel_name}")
def stream_channel(channel_name: str):
    if channel_name not in realtime_broker.subscribers:
        raise HTTPException(status_code=404, detail="Unknown realtime channel")

    async def event_generator() -> AsyncIterator[str]:
        initial = _snapshot(channel_name)
        if initial:
            yield f"event: snapshot\n"
            yield f"data: {json.dumps(initial, default=str)}\n\n"
        queue = realtime_broker.register(channel_name)
        try:
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload, default=str)}\n\n"
        finally:
            realtime_broker.unregister(channel_name, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
