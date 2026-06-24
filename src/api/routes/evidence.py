from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.dependencies import get_redis

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/{task_id}")
async def get_evidence(
    task_id: str,
    source_type: str = Query("", description="Filter by source type"),
):
    """Get the evidence chain for a task."""
    redis = await get_redis()
    task_data = await redis.get_json(f"task:{task_id}")
    if task_data is None:
        raise HTTPException(status_code=404, detail="Task not found")

    evidence_items = task_data.get("evidence", [])

    # Also check for evidence stored separately
    evidence_data = await redis.get_json(f"evidence:{task_id}")
    if evidence_data:
        evidence_items.extend(evidence_data.get("items", []))

    if source_type:
        evidence_items = [
            e for e in evidence_items
            if str(e.get("source_type", "")).lower() == source_type.lower()
        ]

    return {
        "task_id": task_id,
        "total": len(evidence_items),
        "items": evidence_items,
    }
