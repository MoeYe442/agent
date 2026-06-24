from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from src.models.agent_state import AgentState
from src.tools.registry import execute_tool, get_tool_schemas

logger = structlog.get_logger(__name__)

MAX_TOOL_ROUNDS = 5


def estimate_tokens(text: str) -> int:
    """Estimate token count using char/4 fallback (tiktoken not required)."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // 4)


def compress_context(messages: list[dict], max_tokens: int = 32000) -> list[dict]:
    """Compress conversation context to fit within max_tokens.

    Strategy: Keep system message + last N messages, dropping oldest first.
    """
    if not messages:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    total = sum(estimate_tokens(json.dumps(m, default=str)) for m in messages)
    if total <= max_tokens:
        return messages

    # Drop from the middle (keep system + recent)
    while other_msgs and total > max_tokens:
        removed = other_msgs.pop(0)
        total -= estimate_tokens(json.dumps(removed, default=str))

    return system_msgs + other_msgs


async def call_llm_with_tools(
    llm_client: Any,
    messages: list[dict],
    tool_schemas: list[dict] | None = None,
    temperature: float = 0.1,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> dict:
    """Call LLM with tool-calling loop. Returns final assistant message dict.

    The LLM can call tools and receive results for up to max_rounds iterations.
    """
    current_messages = list(messages)
    tools = tool_schemas or get_tool_schemas()

    for round_num in range(max_rounds):
        try:
            response = await asyncio.to_thread(
                llm_client.chat, current_messages, tools if tools else None, temperature
            )
        except Exception as exc:
            logger.error("llm_call_failed", round=round_num, error=str(exc))
            return {
                "role": "assistant",
                "content": f"LLM call failed after {round_num} rounds: {exc}",
            }

        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            return message

        # Append assistant message
        current_messages.append(message)

        # Execute tools and collect results
        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            try:
                arguments = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            logger.info("tool_call", tool=tool_name, round=round_num)
            result = await execute_tool(tool_name, arguments)

            current_messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result,
            })

    # Final LLM call to summarize after all tool rounds
    try:
        final = await asyncio.to_thread(
            llm_client.chat, current_messages, None, temperature
        )
        return final.get("choices", [{}])[0].get("message", {"role": "assistant", "content": ""})
    except Exception:
        return {"role": "assistant", "content": "Max tool rounds reached without final response."}
