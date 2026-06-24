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

RESEARCHER_SYSTEM_PROMPT = """You are a code researcher. Your job is to gather information about a software project by:
1. Scraping relevant web pages for documentation and context
2. Reading key project files (README, config files, setup scripts)
3. Searching for information relevant to the research question

Available tools: read_file, list_directory, search_code, scrape_page, get_repo_info.

For each piece of information you find, note:
- Where it came from (URL, file path)
- Why it's relevant to the research question
- A confidence level (high/medium/low)

Be thorough but focused on the research question."""


async def researcher_node(state: AgentState, llm_client: Any, rag_pipeline: Any = None) -> dict:
    """Researcher agent: gathers information via web scraping, file reading, and RAG search.

    Args:
        state: Current AgentState
        llm_client: LLMClient instance
        rag_pipeline: Optional RAGPipeline for code retrieval

    Returns:
        Partial state dict with 'findings', 'evidence', and 'phase' updated.
    """
    query = ""
    if isinstance(state.get("task_spec"), dict):
        query = state["task_spec"].get("query", "")
    elif hasattr(state.get("task_spec"), "query"):
        query = getattr(state["task_spec"], "query", "")

    plan = state.get("plan", [])
    plan_summary = json.dumps(plan, default=str) if plan else "No plan yet"

    # Get current plan step for researcher
    researcher_steps = [p for p in plan if isinstance(p, dict) and p.get("agent") == "researcher"]
    step_text = json.dumps(researcher_steps[:3], default=str) if researcher_steps else "Gather general project information"

    user_msg = f"""Research Question: {query}
Plan steps for you: {step_text}

Current findings so far: {json.dumps(state.get('findings', [])[-5:], default=str)}

Please gather information to address these research steps. Use available tools to:
1. Read key project files (README, config, setup.py, pyproject.toml, etc.)
2. Search for relevant code patterns
3. Scrape documentation pages if URLs are available

Important: Record each finding with its source."""

    messages = [
        {"role": "system", "content": RESEARCHER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    tool_schemas = get_tool_schemas()
    response = await call_llm_with_tools(llm_client, messages, tool_schemas, temperature=0.3)
    content = response.get("content", "")

    # Collect findings
    findings = list(state.get("findings", []))
    findings.append({
        "agent": "researcher",
        "content": content,
        "timestamp": str(uuid.uuid4()),
    })

    # Also search RAG if available
    rag_results = []
    if rag_pipeline is not None:
        try:
            rag_results = await rag_pipeline.search(query, top_k=5, alpha=0.5, rerank=True)
        except Exception as exc:
            logger.warning("rag_search_failed", error=str(exc))

    # Build evidence items from tool calls and RAG results
    evidence = list(state.get("evidence", []))
    tool_log = state.get("tool_log", [])

    for tc in tool_log[-10:]:
        tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
        evidence.append(EvidenceItem(
            evidence_id=uuid.uuid4().hex,
            task_id=state.get("task_id", ""),
            source_type=SourceType.COMMAND_OUTPUT,
            source_path=tc_dict.get("params_json", ""),
            content_hash=str(hash(tc_dict.get("result_summary", ""))),
            excerpt=tc_dict.get("result_summary", "")[:500],
            full_content_ref=tc_dict.get("params_json", ""),
            agent_role="researcher",
        ).model_dump() if hasattr(EvidenceItem, "model_dump") else {})

    for rr in rag_results:
        evidence.append(EvidenceItem(
            evidence_id=uuid.uuid4().hex,
            task_id=state.get("task_id", ""),
            source_type=SourceType.RAG_CHUNK,
            source_path=rr.chunk.source_path,
            content_hash=str(hash(rr.chunk.content)),
            excerpt=rr.chunk.content[:500],
            full_content_ref=rr.chunk.chunk_id,
            agent_role="researcher",
            relevance_score=rr.score,
        ).model_dump())

    return {
        "findings": findings + [{"rag_results": [r.model_dump() for r in rag_results] if rag_results else []}],
        "evidence": evidence,
        "phase": TaskPhase.READING,
        "current_agent": "researcher",
    }
