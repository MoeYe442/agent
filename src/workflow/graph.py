from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from src.agents.code_reader import code_reader_node
from src.agents.executor import executor_node
from src.agents.planner import planner_node
from src.agents.reporter import reporter_node
from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
from src.models.agent_state import AgentState
from src.models.enums import TaskPhase
from src.workflow.retry import with_node_retry
from src.workflow.timeout import with_timeout

import structlog

logger = structlog.get_logger(__name__)


def build_workflow(
    llm_client: Any,
    rag_pipeline: Any = None,
    repo_path: str = "",
    project_index: Any = None,
) -> StateGraph:
    """Build the LangGraph StateGraph for the multi-agent research workflow.

    Flow:
        START -> planner -> researcher -> code_reader -> executor -> reviewer
                                                                    ↓ (score >= 0.6)
                                                                  reporter -> END
                                                                    ↑ (score < 0.6 & retries < max)
                                                                  researcher
    """
    graph = StateGraph(AgentState)

    # Add nodes using factory functions so we can inject dependencies
    graph.add_node("planner", _make_planner(llm_client))
    graph.add_node("researcher", _make_researcher(llm_client, rag_pipeline))
    graph.add_node("code_reader", _make_code_reader(llm_client, project_index, repo_path))
    graph.add_node("executor", _make_executor(llm_client, repo_path))
    graph.add_node("reviewer", _make_reviewer(llm_client))
    graph.add_node("reporter", _make_reporter(llm_client))

    # Edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "code_reader")
    graph.add_edge("code_reader", "executor")
    graph.add_edge("executor", "reviewer")

    # Conditional edge from reviewer
    graph.add_conditional_edges(
        "reviewer",
        _route_after_review,
        {
            "researcher": "researcher",
            "reporter": "reporter",
        },
    )
    graph.add_edge("reporter", END)

    return graph


def compile_workflow(
    llm_client: Any,
    rag_pipeline: Any = None,
    repo_path: str = "",
    project_index: Any = None,
) -> Any:
    """Build and compile the workflow with a MemorySaver checkpoint."""
    workflow = build_workflow(llm_client, rag_pipeline, repo_path, project_index)
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# -- Node factory functions (closures over dependencies) --

def _wrap_node(func):
    """Apply retry and timeout wrappers to a node function."""
    return with_node_retry(max_retries=2)(with_timeout()(func))


def _make_planner(llm_client: Any):
    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await planner_node(state, llm_client)
    return node


def _make_researcher(llm_client: Any, rag_pipeline: Any = None):
    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await researcher_node(state, llm_client, rag_pipeline)
    return node


def _make_code_reader(llm_client: Any, project_index: Any = None, repo_path: str = ""):
    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await code_reader_node(state, llm_client, project_index, repo_path)
    return node


def _make_executor(llm_client: Any, repo_path: str = ""):
    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await executor_node(state, llm_client, repo_path)
    return node


def _make_reviewer(llm_client: Any):
    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await reviewer_node(state, llm_client)
    return node


def _make_reporter(llm_client: Any):
    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await reporter_node(state, llm_client)
    return node


def _route_after_review(state: AgentState) -> str:
    """Determine where to route after the reviewer node."""
    phase = state.get("phase", "")
    retries = state.get("review_retries", 0)
    score = state.get("review_score", 0.0)

    if phase == TaskPhase.RESEARCHING and retries <= 2:
        logger.info("review_routing", decision="retry_research", score=score, retry=retries)
        return "researcher"

    logger.info("review_routing", decision="proceed_to_report", score=score)
    return "reporter"
