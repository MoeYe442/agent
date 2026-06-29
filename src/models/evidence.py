from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.enums import AgentRole, SourceType


class EvidenceItem(BaseModel):
    evidence_id: str
    task_id: str
    source_type: SourceType
    source_path: str  # URL, file path, or repo reference
    content_hash: str
    excerpt: str  # Relevant snippet
    full_content_ref: str  # Reference to full content
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    agent_role: str = ""
    relevance_score: float = 0.0
    metadata: dict = Field(default_factory=dict)
    # New fields for evidence confidence
    line_range: tuple[int, int] | None = None
    confidence_score: float | None = None
    collected_by: AgentRole | None = None
    corroboration_count: int = 0
    cross_references: list[str] = Field(default_factory=list)
    related_claim: str | None = None


class EvidenceChain(BaseModel):
    task_id: str
    items: list[EvidenceItem]
    relationships: list[tuple[str, str]] = Field(
        default_factory=list
    )  # (parent_id, child_id)
    confidence_summary: dict | None = None
