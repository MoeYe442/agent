from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.dependencies import get_workflow_executor
from src.models.task import TaskSpec

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("")
async def create_task(spec: TaskSpec) -> dict:
    """Submit a new research task."""
    executor = await get_workflow_executor()
    record = await executor.run(spec)
    return {"task_id": record.task_id, "status": record.status}


@router.get("/{task_id}")
async def get_task(task_id: str) -> dict:
    """Get task status and details."""
    executor = await get_workflow_executor()
    record = await executor.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return record.model_dump()


@router.delete("/{task_id}")
async def cancel_task(task_id: str) -> dict:
    """Cancel a running task."""
    executor = await get_workflow_executor()
    ok = await executor.cancel(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or not running")
    return {"task_id": task_id, "status": "cancelled"}


@router.get("")
async def list_tasks() -> dict:
    """List all tasks (summary)."""
    executor = await get_workflow_executor()
    redis = executor._redis
    if redis is None:
        return {"tasks": []}

    tasks = []
    # Scan for task keys
    cursor = 0
    while True:
        cursor, keys = await redis.client.scan(cursor, match="task:*", count=100)
        for key in keys:
            data = await redis.get_json(key)
            if data:
                tasks.append({
                    "task_id": data.get("task_id", ""),
                    "status": data.get("status", ""),
                    "query": data.get("spec", {}).get("query", "")[:100] if isinstance(data.get("spec"), dict) else "",
                    "created_at": data.get("created_at", ""),
                })
        if cursor == 0:
            break

    return {"tasks": tasks}
