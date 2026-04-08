"""
Supabase Realtime helper: maintains websocket subscriptions to the `incidents`, `responders`,
and `incident_assignments` tables and fans their payloads out via asyncio queues.
"""

import asyncio
import logging
from typing import Any, Dict, Set

from supabase import acreate_client, AsyncClient

from app.supabase_client import SUPABASE_SERVICE_KEY, SUPABASE_URL


CHANNEL_TABLES = {
    "incidents_live": "incidents",
    "responders_live": "responders",
    "assignments_live": "incident_assignments",
}


class RealtimeBroker:
    def __init__(self) -> None:
        self.client: AsyncClient | None = None
        self.channels: Dict[str, Any] = {}
        self.subscribers: Dict[str, Set[asyncio.Queue]] = {
            name: set() for name in CHANNEL_TABLES
        }
        self._tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self.client:
                return
            self.client = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            for channel_name, table in CHANNEL_TABLES.items():
                task = asyncio.create_task(self._subscribe_channel(channel_name, table))
                self._tasks.append(task)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for channel in self.channels.values():
            if hasattr(channel, "unsubscribe"):
                try:
                    await channel.unsubscribe()
                except Exception as exc:
                    logging.debug("Realtime channel unsubscribe failed: %s", exc)
        if self.client:
            try:
                await self.client.close()
            except Exception:
                pass
            self.client = None

    async def _subscribe_channel(self, channel_name: str, table: str) -> None:
        assert self.client, "Realtime client is not initialized"
        while True:
            try:
                channel = self.client.channel(channel_name)
                callback = self._make_callback(channel_name, table)
                await (
                    channel
                    .on_postgres_changes("*", schema="public", table=table, callback=callback)
                    .subscribe()
                )
                self.channels[channel_name] = channel
                logging.debug("Subscribed to realtime channel %s (table %s)", channel_name, table)
                return
            except Exception as exc:
                logging.error("Realtime channel %s subscribe failed: %s", channel_name, exc)
                await asyncio.sleep(4)

    def _make_callback(self, channel_name: str, table: str):
        async def callback(payload: Dict[str, Any]) -> None:
            record = {
                "channel": channel_name,
                "table": table,
                "payload": payload,
            }
            await self._broadcast(channel_name, record)

        return callback

    async def _broadcast(self, channel_name: str, data: Dict[str, Any]) -> None:
        queues = list(self.subscribers.get(channel_name, set()))
        for queue in queues:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logging.debug("Realtime queue full for %s", channel_name)

    def register(self, channel_name: str) -> asyncio.Queue:
        if channel_name not in CHANNEL_TABLES:
            raise ValueError("Unknown channel")
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self.subscribers.setdefault(channel_name, set()).add(queue)
        return queue

    def unregister(self, channel_name: str, queue: asyncio.Queue) -> None:
        self.subscribers.get(channel_name, set()).discard(queue)

    def get_table(self, channel_name: str) -> str:
        return CHANNEL_TABLES[channel_name]


realtime_broker = RealtimeBroker()
