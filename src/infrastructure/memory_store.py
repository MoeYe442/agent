from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

import structlog

logger = structlog.get_logger(__name__)


class InMemoryStore:
    """Dict-based drop-in replacement for RedisClient.

    Implements the same interface: get_json, set_json, delete, exists,
    publish, subscribe (via asyncio.Queue per channel), rpush, brpoplpush,
    lrem, llen, lrange, health_check, connect, disconnect, and client property.
    """

    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._ttl: dict[str, float] = {}  # key -> expiry timestamp
        self._lists: dict[str, list[str]] = {}
        self._list_events: dict[str, asyncio.Event] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = {}
        self._connected = False

    # -- Connection ----------------------------------------------------------

    @property
    def client(self) -> InMemoryStore:
        return self

    async def connect(self) -> None:
        self._connected = True
        logger.info("memory_store_connected")

    async def disconnect(self) -> None:
        self._connected = False
        self._kv.clear()
        self._ttl.clear()
        self._lists.clear()
        self._list_events.clear()
        self._subscribers.clear()
        logger.info("memory_store_disconnected")

    async def health_check(self) -> bool:
        return self._connected

    # -- JSON helpers --------------------------------------------------------

    async def get_json(self, key: str) -> dict | None:
        self._expire_if_needed(key)
        data = self._kv.get(key)
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, key: str, value: dict, ttl: int | None = None) -> None:
        self._kv[key] = json.dumps(value, default=str)
        if ttl is not None:
            self._ttl[key] = time.monotonic() + ttl
        else:
            self._ttl.pop(key, None)

    # -- Basic key-value -----------------------------------------------------

    async def delete(self, key: str) -> int:
        self._ttl.pop(key, None)
        if key in self._kv:
            del self._kv[key]
            return 1
        return 0

    async def exists(self, key: str) -> bool:
        self._expire_if_needed(key)
        return key in self._kv

    # -- Pub/Sub ------------------------------------------------------------

    async def publish(self, channel: str, message: str) -> int:
        count = 0
        queues = self._subscribers.get(channel, [])
        for q in queues:
            try:
                data = json.loads(message) if isinstance(message, str) else message
            except (json.JSONDecodeError, TypeError):
                data = message
            await q.put({"channel": channel, "data": data})
            count += 1
        return count

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers.setdefault(channel, []).append(queue)
        try:
            while True:
                item = await queue.get()
                yield item
        finally:
            queues = self._subscribers.get(channel, [])
            if queue in queues:
                queues.remove(queue)
            if not queues:
                self._subscribers.pop(channel, None)

    # -- List operations ----------------------------------------------------

    async def lpush(self, key: str, *values: str) -> int:
        lst = self._lists.setdefault(key, [])
        for v in reversed(values):
            lst.insert(0, v)
        self._signal_list(key)
        return len(lst)

    async def rpush(self, key: str, *values: str) -> int:
        lst = self._lists.setdefault(key, [])
        lst.extend(values)
        self._signal_list(key)
        return len(lst)

    async def brpoplpush(self, source: str, dest: str, timeout: int) -> str | None:
        src_list = self._lists.setdefault(source, [])
        if not src_list:
            event = self._list_events.setdefault(source, asyncio.Event())
            event.clear()
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
        if not src_list:
            return None
        value = src_list.pop(0)
        dst_list = self._lists.setdefault(dest, [])
        dst_list.append(value)
        return value

    async def lrem(self, key: str, count: int, value: str) -> int:
        lst = self._lists.get(key, [])
        removed = 0
        if count > 0:
            i = 0
            while i < len(lst) and removed < count:
                if lst[i] == value:
                    lst.pop(i)
                    removed += 1
                else:
                    i += 1
        elif count < 0:
            i = len(lst) - 1
            while i >= 0 and removed < abs(count):
                if lst[i] == value:
                    lst.pop(i)
                    removed += 1
                i -= 1
        else:
            new_lst = [v for v in lst if v != value]
            removed = len(lst) - len(new_lst)
            self._lists[key] = new_lst
        return removed

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        lst = self._lists.get(key, [])
        if end < 0:
            end = len(lst) + end
        return lst[start:end + 1]

    async def keys(self, pattern: str = "*") -> list[str]:
        """List keys matching a glob pattern (simple * and ? support)."""
        import fnmatch
        result = []
        for key in list(self._kv):
            self._expire_if_needed(key)
            if key in self._kv and fnmatch.fnmatch(key, pattern):
                result.append(key)
        return result

    # -- Internal helpers ----------------------------------------------------

    def _expire_if_needed(self, key: str) -> None:
        expiry = self._ttl.get(key)
        if expiry is not None and time.monotonic() >= expiry:
            self._kv.pop(key, None)
            self._ttl.pop(key, None)

    def _signal_list(self, key: str) -> None:
        event = self._list_events.get(key)
        if event is not None:
            event.set()
