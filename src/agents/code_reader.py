from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from src.agents.base import call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.enums import SourceType, TaskPhase
from src.models.evidence import EvidenceItem

logger = structlog.get_logger(__name__)

CODE_READER_SYSTEM_PROMPT = """You are a code analysis specialist. Your job is to deeply analyze source code:
1. Read source files to understand architecture and design patterns
2. Trace function call chains and data flow
3. Identify key abstractions, classes, and modules
4. Build a mental model of how the codebase is structured

Available tools: read_file, list_directory, search_code.

For each file you analyze, note:
- The purpose of the file/module
- Key functions/classes and their responsibilities
- Dependencies and imports
- How it connects to the rest of the codebase"""


async def code_reader_node(
    state: AgentState,
    llm_client: Any,
    project_index: Any = None,
    repo_path: str = "",
) -> dict:
    """CodeReader agent: performs deep code analysis using Jedi and file reading.

    Args:
        state: Current AgentState
        llm_client: LLMClient instance
        project_index: Optional ProjectIndex from repo analysis
        repo_path: Path to the cloned repository

    Returns:
        Partial state dict with findings, evidence, and project_index updated.
    """
    query = ""
    if isinstance(state.get("task_spec"), dict):
        query = state["task_spec"].get("query", "")
    elif hasattr(state.get("task_spec"), "query"):
        query = getattr(state["task_spec"], "query", "")

    findings = state.get("findings", [])
    findings_summary = json.dumps(findings[-5:], default=str) if findings else "None"

    # Include project index info if available
    index_info = ""
    if project_index is not None:
        if hasattr(project_index, "model_dump"):
            pi = project_index.model_dump()
        elif isinstance(project_index, dict):
            pi = project_index
        else:
            pi = {}
        index_info = f"""
Project Index:
- Files: {len(pi.get('files', []))}
- Symbols: {len(pi.get('symbols', []))}
- Key symbols: {json.dumps([s.get('name', '') for s in pi.get('symbols', [])[:30]], default=str)}
"""

    user_msg = f"""Research Question: {query}
Repository path: {repo_path}
Previous findings: {findings_summary}
{index_info}

Please analyze the codebase deeply. Focus on:
1. Core architecture and module organization
2. Key functions and classes and their relationships
3. Data flow and business logic
4. How the code relates to the research question

Use available tools to read and search files."""

    messages = [
        {"role": "system", "content": CODE_READER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    from src.tools.registry import get_tool_schemas

    response = await call_llm_with_tools(llm_client, messages, get_tool_schemas(), temperature=0.2)
    content = response.get("content", "")

    # Record findings
    new_findings = list(findings)
    new_findings.append({
        "agent": "code_reader",
        "content": content,
        "timestamp": str(uuid.uuid4()),
    })

    # Build evidence from analysis
    evidence = list(state.get("evidence", []))
    tool_log = state.get("tool_log", [])

    for tc in tool_log[-15:]:
        tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
        if tc_dict.get("tool_name") in ("read_file", "search_code"):
            evidence.append(EvidenceItem(
                evidence_id=uuid.uuid4().hex,
                task_id=state.get("task_id", ""),
                source_type=SourceType.CODE_FILE,
                source_path=tc_dict.get("params_json", ""),
                content_hash=str(hash(tc_dict.get("result_summary", ""))),
                excerpt=tc_dict.get("result_summary", "")[:500],
                full_content_ref=tc_dict.get("params_json", ""),
                agent_role="code_reader",
            ).model_dump())

    result: dict = {
        "findings": new_findings,
        "evidence": evidence,
        "phase": TaskPhase.EXECUTING,
        "current_agent": "code_reader",
    }

    if project_index is not None:
        if hasattr(project_index, "model_dump"):
            result["project_index"] = project_index.model_dump()
        else:
            result["project_index"] = project_index

    return result
