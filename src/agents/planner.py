from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.base import BaseAgent, call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.models.enums import AgentRole, TaskPhase

logger = structlog.get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a research planner. Given a user's research question and context about a code repository, create a structured research plan.

Your task:
1. Analyze the research question
2. Break it into concrete, sequential sub-tasks
3. For each sub-task, specify which agent role should handle it and what information to gather

Output a JSON array of plan items. Each item must have:
- "step": integer (1-based)
- "title": short description
- "agent": one of "researcher", "code_reader", "executor"
- "goal": what this step should accomplish
- "tools": list of tool names that may be useful

Return ONLY valid JSON (no markdown code fences)."""

PLANNER_CONTRACT = AgentContract(
    agent_role=AgentRole.PLANNER,
    description="Parse research questions and produce step-by-step plans. Do not analyze code or draw conclusions.",
    input_schema=["task_spec"],
    output_schema=["plan", "phase"],
    allowed_tools=["read_file", "list_directory"],
    forbidden_actions=["analyze source code logic", "infer architecture conclusions", "search the web"],
    failure_conditions=["plan is empty", "plan step is not executable"],
    fallback_behavior="Produce a default single-step plan",
    quality_gate={"min_plan": 1},
)


class PlannerAgent(BaseAgent):
    contract = PLANNER_CONTRACT

    async def _run(self, state: AgentState) -> dict:
        query = state.get("task_spec", {}).get("query", "") if isinstance(state.get("task_spec"), dict) else getattr(state.get("task_spec", ""), "query", "")
        repo_urls = []
        if isinstance(state.get("task_spec"), dict):
            repo_urls = state["task_spec"].get("repo_urls", [])
        elif hasattr(state.get("task_spec"), "repo_urls"):
            repo_urls = getattr(state["task_spec"], "repo_urls", [])

        findings_summary = ""
        if state.get("findings"):
            findings_summary = json.dumps(state["findings"][-5:], default=str)

        user_msg = f"""Research Question: {query}
Repository URLs: {', '.join(repo_urls) if repo_urls else 'none'}
Previous findings (if any): {findings_summary}

Create a research plan for this question."""

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        response = await call_llm_with_tools(self.llm_client, messages, tool_schemas=None, temperature=0.2)
        content = response.get("content", "")

        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            plan = json.loads(cleaned)
            if not isinstance(plan, list):
                plan = [plan]
        except (json.JSONDecodeError, AttributeError):
            logger.warning("plan_parse_failed", content=content[:200])
            plan = [{"step": 1, "title": "Analyze and research", "agent": "researcher", "goal": query, "tools": []}]

        logger.info("plan_created", steps=len(plan))
        return {
            "plan": plan,
            "phase": TaskPhase.RESEARCHING,
        }


# Backward-compatible wrapper for existing callers
async def planner_node(state: AgentState, llm_client: Any) -> dict:
    agent = PlannerAgent(llm_client)
    return await agent.execute(state)
