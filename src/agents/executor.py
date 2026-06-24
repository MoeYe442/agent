from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from src.agents.base import call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.enums import SourceType, TaskPhase
from src.models.evidence import EvidenceItem
from src.tools.registry import get_tool_schemas

logger = structlog.get_logger(__name__)

EXECUTOR_SYSTEM_PROMPT = """You are a code executor and validator. Your job:
1. Run commands to verify hypotheses about the codebase
2. Execute Python snippets to test code behavior
3. Validate findings from the researcher and code reader

Available tools: run_command, run_python, read_file.

For each execution, note:
- The command/code that was run
- The output and what it means
- Whether it confirms or contradicts previous findings"""


async def executor_node(state: AgentState, llm_client: Any, repo_path: str = "") -> dict:
    """Executor agent: runs verification commands and validates hypotheses.

    Args:
        state: Current AgentState
        llm_client: LLMClient instance
        repo_path: Path to the cloned repository

    Returns:
        Partial state dict with findings and evidence updated.
    """
    query = ""
    if isinstance(state.get("task_spec"), dict):
        query = state["task_spec"].get("query", "")
    elif hasattr(state.get("task_spec"), "query"):
        query = getattr(state["task_spec"], "query", "")

    findings = state.get("findings", [])
    all_findings_text = json.dumps(findings[-8:], default=str) if findings else "None"

    user_msg = f"""Research Question: {query}
Repository path: {repo_path}
Accumulated findings: {all_findings_text}

Your job is to validate and verify the findings. Run commands or Python snippets to:
1. Verify project structure (e.g., list files, check dependencies)
2. Confirm API/function behavior
3. Validate any claims made by previous agents

Be specific about what you're testing and what the results mean."""

    messages = [
        {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    response = await call_llm_with_tools(llm_client, messages, get_tool_schemas(), temperature=0.1)
    content = response.get("content", "")

    new_findings = list(findings)
    new_findings.append({
        "agent": "executor",
        "content": content,
        "timestamp": str(uuid.uuid4()),
    })

    # Record tool outputs as evidence
    evidence = list(state.get("evidence", []))
    tool_log = state.get("tool_log", [])

    for tc in tool_log[-10:]:
        tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
        if tc_dict.get("tool_name") in ("run_command", "run_python"):
            evidence.append(EvidenceItem(
                evidence_id=uuid.uuid4().hex,
                task_id=state.get("task_id", ""),
                source_type=SourceType.COMMAND_OUTPUT,
                source_path=tc_dict.get("params_json", ""),
                content_hash=str(hash(tc_dict.get("result_summary", ""))),
                excerpt=tc_dict.get("result_summary", "")[:500],
                full_content_ref=tc_dict.get("params_json", ""),
                agent_role="executor",
            ).model_dump())

    return {
        "findings": new_findings,
        "evidence": evidence,
        "phase": TaskPhase.REVIEWING,
        "current_agent": "executor",
    }
