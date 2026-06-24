from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import redis.asyncio as aioredis
import structlog

from src.config import Settings

logger = getattr(structlog, "get_logger")("src.infrastructure.redis")


class RedisClient:
    """Async Redis client wrapper with JSON helpers and connection pooling."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("RedisClient is not connected. Use 'async with' context manager or call connect().")
        return self._client

    async def connect(self) -> None:
        """Create the connection pool and connect."""
        if self._client is not None:
            return
        self._client = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        logger.info("redis_connected", url=self._redis_url)

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("redis_disconnected")

    async def __aenter__(self) -> RedisClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()

    async def health_check(self) -> bool:
        """Ping Redis to verify connectivity."""
        try:
            ok = await self.client.ping()
            logger.debug("redis_health_check", ok=ok)
            return ok is True or (isinstance(ok, str) and ok.lower() == "pong")
        except Exception:
            logger.exception("redis_health_check_failed")
            return False

    # -- JSON helpers ---------------------------------------------------------

    async def get_json(self, key: str) -> dict | None:
        data = await self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def set_json(self, key: str, value: dict, ttl: int | None = None) -> None:
        payload = json.dumps(value, default=str)
        if ttl is not None:
            await self.client.setex(key, ttl, payload)
        else:
            await self.client.set(key, payload)

    # -- Basic key-value ------------------------------------------------------

    async def delete(self, key: str) -> int:
        return await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        n = await self.client.exists(key)
        return n > 0

    # -- Pub/Sub -------------------------------------------------------------

    async def publish(self, channel: str, message: str) -> int:
        return await self.client.publish(channel, message)

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for raw in pubsub.listen():
                if raw["type"] == "message":
                    try:
                        yield {"channel": raw["channel"], "data": json.loads(raw["data"])}
                    except (json.JSONDecodeError, TypeError):
                        yield {"channel": raw["channel"], "data": raw["data"]}
        finally:
            await pubsub.unsubscribe(channel)

    # -- List operations -----------------------------------------------------

    async def lpush(self, key: str, *values: str) -> int:
        return await self.client.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        return await self.client.rpush(key, *values)

    async def brpoplpush(self, source: str, dest: str, timeout: int) -> str | None:
        return await self.client.brpoplpush(source, dest, timeout)

    async def lrem(self, key: str, count: int, value: str) -> int:
        return await self.client.lrem(key, count, value)

    async def llen(self, key: str) -> int:
        return await self.client.llen(key)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return await self.client.lrange(key, start, end)


# ------------------------------------------------------------------------


def get_redis_client() -> RedisClient:  # noqa: D103
    settings = Settings()
    return RedisClient(redis_url=settings.redis_url)
