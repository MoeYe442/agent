from __future__ import annotations

import json
from typing import Any

import structlog

from src.config import Settings
from src.utils.token_counter import count_tokens

logger = structlog.get_logger(__name__)


class ContextManager:
    """Manages context window compression for agent conversations."""

    def __init__(self, threshold: int | None = None) -> None:
        if threshold is None:
            threshold = Settings().context_compress_threshold
        self._threshold = threshold

    def maybe_compress(self, messages: list[dict]) -> list[dict]:
        """Compress messages if total tokens exceed threshold.

        Strategy:
        1. Calculate total token count
        2. If under threshold, return unchanged
        3. If over, keep system messages + recent messages, drop middle
        """
        total = sum(count_tokens(json.dumps(m, default=str)) for m in messages)
        if total <= self._threshold:
            return messages

        logger.info("context_compression_triggered", total_tokens=total, threshold=self._threshold)

        # Separate system messages
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]

        # Calculate system token usage
        system_tokens = sum(count_tokens(json.dumps(m, default=str)) for m in system)
        available = self._threshold - system_tokens

        # Keep recent messages that fit within available tokens
        kept: list[dict] = []
        kept_tokens = 0
        for m in reversed(others):
            mt = count_tokens(json.dumps(m, default=str))
            if kept_tokens + mt > available:
                break
            kept.insert(0, m)
            kept_tokens += mt

        result = system + kept
        new_total = sum(count_tokens(json.dumps(m, default=str)) for m in result)
        logger.info("context_compressed", original_tokens=total, compressed_tokens=new_total, kept_messages=len(kept))
        return result

    def summarize_for_context(self, text: str, max_summary_tokens: int = 500) -> str:
        """Create a brief summary of a long text to save context space."""
        if count_tokens(text) <= max_summary_tokens:
            return text
        # Simple truncation + indicator
        char_limit = max_summary_tokens * 4
        return text[:char_limit] + f"\n... (truncated, estimated {count_tokens(text)} total tokens)"
