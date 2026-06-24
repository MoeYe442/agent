from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from src.api.dependencies import get_redis

router = APIRouter(prefix="/tasks", tags=["events"])


@router.get("/{task_id}/events")
async def task_events(task_id: str):
    """SSE endpoint streaming task lifecycle events via Redis pub/sub."""
    redis = await get_redis()

    # Check task exists
    exists = await redis.exists(f"task:{task_id}")
    if not exists:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_stream():
        try:
            channel = f"task_events:{task_id}"
            pubsub = redis.client.pubsub()
            await pubsub.subscribe(channel)

            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'task_id': task_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            try:
                async for raw in pubsub.listen():
                    if raw["type"] == "message":
                        try:
                            data = json.loads(raw["data"])
                        except (json.JSONDecodeError, TypeError):
                            data = {"raw": str(raw.get("data", ""))}

                        event_type = data.get("event", "message")
                        yield f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

                        if event_type in ("task_completed", "task_failed", "task_cancelled"):
                            break
                    elif raw["type"] == "subscribe":
                        continue
            finally:
                await pubsub.unsubscribe(channel)

        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
