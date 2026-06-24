from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.base import call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.enums import TaskPhase

logger = structlog.get_logger(__name__)

REVIEWER_SYSTEM_PROMPT = """You are a quality reviewer for research analysis. Your job:
1. Review all findings, evidence, and analysis from previous agents
2. Assess completeness and accuracy
3. Assign a quality score from 0 to 1
4. Identify gaps or issues that need more investigation

Output a JSON object with:
- "score": float between 0 and 1 (0.6 = minimum acceptable quality)
- "summary": brief assessment
- "strengths": list of what was done well
- "gaps": list of issues or missing information
- "needs_retry": boolean (true if score < 0.6 and should retry)
- "suggestions": what the researcher should do on retry (if applicable)

Return ONLY valid JSON (no markdown code fences)."""


async def reviewer_node(state: AgentState, llm_client: Any) -> dict:
    """Reviewer agent: assesses research quality and decides whether to loop back.

    Args:
        state: Current AgentState
        llm_client: LLMClient instance

    Returns:
        Partial state dict with review_score, review_retries updated.
        If score < 0.6 and retries remain, phase returns to 'researching'.
    """
    query = ""
    if isinstance(state.get("task_spec"), dict):
        query = state["task_spec"].get("query", "")
    elif hasattr(state.get("task_spec"), "query"):
        query = getattr(state["task_spec"], "query", "")

    plan = state.get("plan", [])
    findings = state.get("findings", [])
    evidence = state.get("evidence", [])
    retries = state.get("review_retries", 0)

    review_input = {
        "query": query,
        "plan": plan,
        "findings_count": len(findings),
        "evidence_count": len(evidence),
        "findings_summary": [f.get("content", "")[:300] for f in findings[-5:] if isinstance(f, dict)],
        "max_retries": 2,
        "current_retry": retries,
    }

    user_msg = f"""Review Request:
{json.dumps(review_input, default=str, indent=2)}

Assess the quality of this research. Consider:
- Is the research question adequately answered?
- Is there enough evidence to support conclusions?
- Are there gaps in analysis?
- Is the code analysis thorough enough?"""

    messages = [
        {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    response = await call_llm_with_tools(llm_client, messages, tool_schemas=None, temperature=0.1)
    content = response.get("content", "")

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        review = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("review_parse_failed", content=content[:200])
        review = {"score": 0.7, "summary": "Could not parse review", "strengths": [], "gaps": [], "needs_retry": False, "suggestions": ""}

    score = float(review.get("score", 0.7))
    score = max(0.0, min(1.0, score))
    needs_retry = review.get("needs_retry", False) or (score < 0.6 and retries < 2)
    new_retries = retries + 1

    logger.info("review_complete", score=score, needs_retry=needs_retry, retry=new_retries)

    # Add review to findings
    new_findings = list(findings)
    new_findings.append({
        "agent": "reviewer",
        "content": json.dumps(review),
        "score": score,
        "timestamp": "",
    })

    result: dict = {
        "review_score": score,
        "review_retries": new_retries,
        "findings": new_findings,
        "current_agent": "reviewer",
    }

    if needs_retry and new_retries <= 2:
        result["phase"] = TaskPhase.RESEARCHING
    else:
        result["phase"] = TaskPhase.REPORTING

    return result
