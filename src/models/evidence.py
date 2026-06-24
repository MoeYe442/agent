from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.enums import SourceType


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


class EvidenceChain(BaseModel):
    task_id: str
    items: list[EvidenceItem]
    relationships: list[tuple[str, str]] = Field(
        default_factory=list
    )  # (parent_id, child_id)
