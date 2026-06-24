from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from src.models.code_index import ProjectIndex
from src.models.evidence import EvidenceItem
from src.models.report import AnalysisReport
from src.models.task import TaskSpec
from src.models.tool_call import ToolCallRecord


class AgentState(TypedDict, total=False):
    task_id: str
    task_spec: TaskSpec
    messages: Annotated[list, add_messages]
    current_agent: str
    phase: str  # planning|researching|reading|executing|reviewing|reporting
    plan: list[dict]  # ResearchPlan subtask list
    findings: list[dict]  # Accumulated findings
    tool_log: list[ToolCallRecord]  # Append-only log
    evidence: list[EvidenceItem]  # Append-only evidence
    project_index: ProjectIndex | None
    review_score: float | None
    review_retries: int
    final_report: AnalysisReport | None
    errors: list[str]
    checkpoint_data: dict
    compressed_context: str | None
    human_approval_required: bool
