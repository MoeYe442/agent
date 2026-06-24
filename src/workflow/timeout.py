from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

import structlog

from src.config import Settings

logger = structlog.get_logger(__name__)


def with_timeout(timeout_seconds: int | None = None):
    """Decorator to wrap a node function with a timeout.

    Args:
        timeout_seconds: Max seconds for the node. If None, uses TASK_TIMEOUT_SECONDS / 6.

    Usage:
        @with_timeout(timeout_seconds=300)
        async def my_node(state: AgentState) -> dict: ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            effective_timeout = timeout_seconds
            if effective_timeout is None:
                effective_timeout = Settings().task_timeout_seconds // 6

            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "node_timeout",
                    node=func.__name__,
                    timeout=effective_timeout,
                )
                return {
                    "errors": [f"Node '{func.__name__}' timed out after {effective_timeout}s"],
                    "phase": "failed",
                }
        return wrapper
    return decorator
