from __future__ import annotations

import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import Any

import structlog

from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.tools.registry import execute_tool, get_tool_schemas

logger = structlog.get_logger(__name__)

MAX_TOOL_ROUNDS = 5

# DeepSeek DSML format: <DSML|tool_calls> / <DSML｜tool_calls>
# The separator can be ASCII pipe | or full-width vertical bar ｜(U+FF5C)
_DSML_SEP = r"[|\uFF5C]"
_DSML_TOOL_CALLS = re.compile(
    rf"<\s*DSML{_DSML_SEP}tool_calls\s*>(.*?)<\s*/\s*DSML{_DSML_SEP}tool_calls\s*>",
    re.DOTALL,
)
_DSML_INVOKE = re.compile(
    rf"<\s*DSML{_DSML_SEP}invoke\s+name\s*=\s*\"([^\"]+)\"\s*>(.*?)<\s*/\s*DSML{_DSML_SEP}invoke\s*>",
    re.DOTALL,
)
_DSML_PARAM = re.compile(
    rf"<\s*DSML{_DSML_SEP}parameter\s+name\s*=\s*\"([^\"]+)\"\s+string\s*=\s*\"([^\"]+)\"\s*>(.*?)<\s*/\s*DSML{_DSML_SEP}parameter\s*>",
    re.DOTALL,
)


def _parse_dsml_tool_calls(content: str) -> tuple[str, list[dict]]:
    """Extract DSML-format tool calls from LLM content.

    Returns (clean_content, tool_calls) where clean_content strips DSML blocks,
    and tool_calls are converted to OpenAI-compatible format.
    """
    match = _DSML_TOOL_CALLS.search(content)
    if not match:
        return content, []

    clean = _DSML_TOOL_CALLS.sub("", content).strip()

    invokes = _DSML_INVOKE.findall(match.group(1))
    tool_calls = []
    for idx, (func_name, params_block) in enumerate(invokes):
        params = _DSML_PARAM.findall(params_block)
        arguments = {}
        for p_name, is_string, value in params:
            val = value.strip()
            if is_string == "false":
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    pass
            arguments[p_name] = val

        tool_calls.append({
            "id": f"dsml_{idx}",
            "type": "function",
            "function": {"name": func_name, "arguments": json.dumps(arguments)},
        })

    return clean, tool_calls


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

    When tool_schemas is None, DSML tool calls in content are stripped rather
    than executed (planner/reviewer/reporter expect JSON output).
    """
    current_messages = list(messages)
    wants_tools = tool_schemas is not None
    tools = tool_schemas or get_tool_schemas()

    for round_num in range(max_rounds):
        try:
            response = await asyncio.to_thread(
                llm_client.chat, current_messages, tools if wants_tools else None, temperature
            )
        except Exception as exc:
            logger.error("llm_call_failed", round=round_num, error=str(exc))
            return {
                "role": "assistant",
                "content": f"LLM call failed after {round_num} rounds: {exc}",
            }

        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Check for native tool calls
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            # Fallback: parse DSML tool calls from content (DeepSeek format)
            content = message.get("content", "")
            clean_content, dsml_calls = _parse_dsml_tool_calls(content)
            if dsml_calls and wants_tools:
                # Agent wants tools: parse DSML, execute them
                message = {**message, "content": clean_content, "tool_calls": dsml_calls}
                tool_calls = dsml_calls
            else:
                # Agent doesn't want tools (or no DSML): strip DSML, return clean content
                if clean_content != content:
                    message = {**message, "content": clean_content}
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
        msg = final.get("choices", [{}])[0].get("message", {"role": "assistant", "content": ""})
        # Strip any DSML from the final message content
        content = msg.get("content", "")
        clean, _ = _parse_dsml_tool_calls(content)
        if clean != content:
            msg = {**msg, "content": clean}
        return msg
    except Exception:
        return {"role": "assistant", "content": "Max tool rounds reached without final response."}


class BaseAgent(ABC):
    """Abstract base class for all agents with contract-driven validation.

    Subclasses define their contract and implement _run(). The execute()
    method is a template method that validates input/output, audits tool
    usage, and checks quality gates around the agent's core logic.
    """

    contract: AgentContract

    def __init__(self, llm_client: Any, tool_registry: Any = None) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry

    async def execute(self, state: AgentState) -> dict:
        """Template method: validate, run, validate, audit, quality-gate."""
        errors: list[str] = list(state.get("errors", []))

        self._validate_input(state, errors)

        result = await self._run(state)

        self._validate_output(result, errors)
        self._audit_tools(result, state, errors)
        quality_passed = self._check_quality_gate(result)

        if not quality_passed:
            errors.append(
                f"Quality gate not passed for {self.contract.agent_role.value}: "
                f"{self.contract.quality_gate}"
            )

        if errors:
            result["errors"] = errors
        result["current_agent"] = self.contract.agent_role.value
        return result

    @abstractmethod
    async def _run(self, state: AgentState) -> dict:
        """Core agent logic. Subclasses must implement this."""
        ...

    def _validate_input(self, state: AgentState, errors: list[str]) -> None:
        """Check that required input_schema fields exist in state."""
        for field in self.contract.input_schema:
            if field not in state or state.get(field) is None:
                msg = (
                    f"Agent '{self.contract.agent_role.value}': "
                    f"required input field '{field}' missing or None in state"
                )
                logger.warning("contract_input_validation_failed", field=field, agent=self.contract.agent_role.value)
                errors.append(msg)

    def _validate_output(self, result: dict, errors: list[str]) -> None:
        """Check that required output_schema fields exist in result."""
        for field in self.contract.output_schema:
            if field not in result:
                msg = (
                    f"Agent '{self.contract.agent_role.value}': "
                    f"required output field '{field}' missing from result"
                )
                logger.warning("contract_output_validation_failed", field=field, agent=self.contract.agent_role.value)
                errors.append(msg)

    def _audit_tools(self, result: dict, state: AgentState, errors: list[str]) -> None:
        """Check that any tools used are in the allowed_tools whitelist.

        Scans tool_log for entries that appeared during this agent's run.
        """
        if not self.contract.allowed_tools:
            return

        allowed = set(self.contract.allowed_tools)
        # Check tool_log from state - we scan recent entries
        tool_log = state.get("tool_log", [])
        for tc in tool_log[-20:]:
            tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
            tool_name = tc_dict.get("tool_name", "")
            if tool_name and tool_name not in allowed:
                msg = (
                    f"Agent '{self.contract.agent_role.value}': "
                    f"tool '{tool_name}' not in allowed_tools whitelist"
                )
                logger.warning("contract_tool_violation", tool=tool_name, agent=self.contract.agent_role.value)
                if msg not in errors:
                    errors.append(msg)

    def _check_quality_gate(self, result: dict) -> bool:
        """Check if result passes quality gate thresholds.

        Quality gates use simple comparisons:
        - "min_<field>": result[field] must have len() >= value
        - "<field>_gte": result[field] must be >= value
        """
        if not self.contract.quality_gate:
            return True

        for key, threshold in self.contract.quality_gate.items():
            if key.startswith("min_"):
                field_name = key[4:]  # strip "min_" prefix
                actual = result.get(field_name)
                if actual is None:
                    return False
                if isinstance(actual, (list, str, dict)):
                    if len(actual) < threshold:
                        return False
                else:
                    if actual < threshold:
                        return False
            elif key.endswith("_gte"):
                field_name = key[:-4]  # strip "_gte" suffix
                actual = result.get(field_name)
                if actual is None:
                    return False
                if isinstance(actual, (int, float)):
                    if actual < threshold:
                        return False

        return True
