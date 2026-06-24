from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import structlog

from src.agents.base import call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.enums import TaskPhase
from src.models.report import AnalysisReport, Citation, ReportSection

logger = structlog.get_logger(__name__)

REPORTER_SYSTEM_PROMPT = """You are a technical report writer. Your job is to synthesize all research findings into a comprehensive analysis report.

The report must have exactly these 7 sections in order:
1. Project Overview - summary from README and directory structure
2. Tech Stack Identification - languages, frameworks, and tools discovered
3. Core Architecture - module organization and key abstractions
4. Key Code Paths - critical functions and call chains
5. Business Logic / Data Flow - how data moves through the system
6. Dependencies and Risks - external dependencies and potential issues
7. Evidence Citations - all evidence items with source references

For every claim you make, cite the evidence by its evidence_id.

Output a JSON object with:
- "title": report title
- "summary": executive summary
- "sections": array of objects with "title", "content" (markdown), "order", "citations" (array of {"evidence_id": "...", "text": "..."})

Return ONLY valid JSON (no markdown code fences)."""


async def reporter_node(state: AgentState, llm_client: Any) -> dict:
    """Reporter agent: assembles the final AnalysisReport from all findings.

    Args:
        state: Current AgentState
        llm_client: LLMClient instance

    Returns:
        Partial state dict with final_report and phase=completed.
    """
    query = ""
    if isinstance(state.get("task_spec"), dict):
        query = state["task_spec"].get("query", "")
    elif hasattr(state.get("task_spec"), "query"):
        query = getattr(state["task_spec"], "query", "")

    findings = state.get("findings", [])
    evidence = state.get("evidence", [])
    project_index = state.get("project_index")
    score = state.get("review_score", 0.0)

    # Summarize findings
    findings_text = ""
    for f in findings[-15:]:
        if isinstance(f, dict):
            agent = f.get("agent", "unknown")
            content = f.get("content", "")
            findings_text += f"\n[{agent}]: {content[:1000]}\n"

    # Summarize evidence
    evidence_summary = []
    for e in evidence[-20:]:
        if isinstance(e, dict):
            evidence_summary.append({
                "id": e.get("evidence_id", ""),
                "source": e.get("source_path", ""),
                "type": str(e.get("source_type", "")),
            })

    pi_summary = {}
    if project_index:
        if hasattr(project_index, "model_dump"):
            pi_summary = project_index.model_dump()
        elif isinstance(project_index, dict):
            pi_summary = project_index
        pi_summary = {
            "project": pi_summary.get("project_name", ""),
            "files": len(pi_summary.get("files", [])),
            "symbols": len(pi_summary.get("symbols", [])),
            "key_symbols": [s.get("name", "") for s in pi_summary.get("symbols", [])[:20]] if isinstance(pi_summary.get("symbols"), list) else [],
        }

    user_msg = f"""Research Question: {query}
Review Score: {score}

Project Index Summary: {json.dumps(pi_summary, default=str)}

All Findings:
{findings_text[:8000]}

Evidence Items ({len(evidence_summary)} total):
{json.dumps(evidence_summary, default=str, indent=2)[:4000]}

Please produce the final analysis report with all 7 sections. Cite evidence items by their ID."""

    messages = [
        {"role": "system", "content": REPORTER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    response = await call_llm_with_tools(llm_client, messages, tool_schemas=None, temperature=0.3)
    content = response.get("content", "")

    # Parse report JSON
    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        report_data = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("report_parse_failed", content=content[:300])
        report_data = {
            "title": f"Analysis: {query[:100]}",
            "summary": "Report generation encountered issues. See findings for raw analysis.",
            "sections": [
                {"title": "Project Overview", "content": findings_text[:2000], "order": 1, "citations": []},
            ],
        }

    # Build sections
    sections: list[ReportSection] = []
    for i, sec in enumerate(report_data.get("sections", []), 1):
        citations: list[Citation] = []
        for c in sec.get("citations", []):
            citations.append(Citation(
                evidence_id=c.get("evidence_id", ""),
                text=c.get("text", ""),
                source_path=c.get("source_path", ""),
            ))
        sections.append(ReportSection(
            section_id=f"sec_{i}",
            title=sec.get("title", f"Section {i}"),
            content=sec.get("content", ""),
            order=sec.get("order", i),
            citations=citations,
        ))

    report = AnalysisReport(
        report_id=uuid.uuid4().hex,
        task_id=state.get("task_id", ""),
        title=report_data.get("title", f"Analysis Report"),
        summary=report_data.get("summary", ""),
        sections=sections,
        generated_at=datetime.utcnow(),
        review_score=score,
        total_evidence_items=len(evidence),
    )

    logger.info("report_generated", report_id=report.report_id, sections=len(sections))

    return {
        "final_report": report.model_dump(),
        "phase": TaskPhase.COMPLETED,
        "current_agent": "reporter",
    }
