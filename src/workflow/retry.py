from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


def with_node_retry(
    max_retries: int = 3,
    backoff_base: float = 1.5,
    max_backoff: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Decorator for agent node functions to add retry with exponential backoff.

    Usage:
        @with_node_retry(max_retries=3)
        async def my_node(state: AgentState) -> dict: ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exception = exc
                    if attempt < max_retries:
                        delay = min(backoff_base ** attempt, max_backoff)
                        logger.warning(
                            "node_retry",
                            node=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=round(delay, 2),
                            error=str(exc),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "node_exhausted_retries",
                            node=func.__name__,
                            attempts=max_retries + 1,
                            error=str(exc),
                        )
            # Return graceful failure state
            return {"errors": [f"Node '{func.__name__}' failed after {max_retries + 1} attempts: {last_exception}"]}
        return wrapper
    return decorator
