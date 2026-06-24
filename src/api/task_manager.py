from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog

from src.models.task import TaskSpec, TaskStatus

logger = structlog.get_logger(__name__)


class TaskManager:
    """Background task scheduler using Redis queues.

    Workers poll the queue and execute tasks via WorkflowExecutor.
    """

    def __init__(
        self,
        redis_client: Any,
        workflow_executor: Any,
        queue_key: str = "task_queue",
        processing_key: str = "task_processing",
    ) -> None:
        self._redis = redis_client
        self._executor = workflow_executor
        self._queue_key = queue_key
        self._processing_key = processing_key
        self._worker_task: asyncio.Task | None = None

    async def enqueue(self, task_spec: TaskSpec) -> str:
        """Enqueue a task for processing. Returns task_id."""
        task_data = task_spec.model_dump()
        await self._redis.rpush(self._queue_key, json.dumps(task_data, default=str))
        logger.info("task_enqueued", queue=self._queue_key)
        return "queued"

    async def start_worker(self, concurrency: int = 2) -> None:
        """Start background workers."""
        self._worker_task = asyncio.create_task(self._worker_loop(concurrency))
        logger.info("worker_started", concurrency=concurrency)

    async def stop_worker(self) -> None:
        """Stop background workers."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("worker_stopped")

    async def _worker_loop(self, concurrency: int) -> None:
        """Main worker loop."""
        workers = [
            asyncio.create_task(self._process_queue())
            for _ in range(concurrency)
        ]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            for w in workers:
                w.cancel()
            raise

    async def _process_queue(self) -> None:
        """Process tasks from the queue."""
        while True:
            try:
                # Blocking reliable queue pattern (brpoplpush)
                task_json = await self._redis.brpoplpush(
                    self._queue_key,
                    self._processing_key,
                    timeout=5,
                )
                if task_json is None:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    task_data = json.loads(task_json)
                    spec = TaskSpec(**task_data)
                except Exception as exc:
                    logger.error("task_parse_failed", error=str(exc))
                    continue

                logger.info("task_dequeued", query=spec.query[:80])
                record = await self._executor.run(spec)

                # Remove from processing queue
                await self._redis.lrem(self._processing_key, 1, task_json)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("worker_error", error=str(exc))
                await asyncio.sleep(1)
