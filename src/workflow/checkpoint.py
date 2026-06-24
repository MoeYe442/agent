from __future__ import annotations

import json
from typing import Any

import structlog

from src.models.agent_state import AgentState

logger = structlog.get_logger(__name__)


async def save_checkpoint(
    state: AgentState,
    redis_client: Any,
    task_id: str,
) -> None:
    """Save agent state checkpoint to Redis for recovery."""
    if redis_client is None:
        return

    checkpoint_data = {
        "task_id": task_id,
        "phase": state.get("phase", ""),
        "current_agent": state.get("current_agent", ""),
        "plan": state.get("plan", []),
        "findings_count": len(state.get("findings", [])),
        "evidence_count": len(state.get("evidence", [])),
        "review_retries": state.get("review_retries", 0),
        "review_score": state.get("review_score"),
        "errors": state.get("errors", []),
    }

    try:
        await redis_client.set_json(
            f"checkpoint:{task_id}",
            checkpoint_data,
            ttl=86400,  # 24h TTL
        )
        logger.debug("checkpoint_saved", task_id=task_id)
    except Exception as exc:
        logger.warning("checkpoint_save_failed", task_id=task_id, error=str(exc))


async def load_checkpoint(
    redis_client: Any,
    task_id: str,
) -> dict | None:
    """Load agent state checkpoint from Redis."""
    if redis_client is None:
        return None

    try:
        data = await redis_client.get_json(f"checkpoint:{task_id}")
        if data:
            logger.debug("checkpoint_loaded", task_id=task_id)
        return data
    except Exception as exc:
        logger.warning("checkpoint_load_failed", task_id=task_id, error=str(exc))
        return None
