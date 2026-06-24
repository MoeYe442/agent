from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Citation(BaseModel):
    evidence_id: str
    text: str
    source_path: str


class ReportSection(BaseModel):
    section_id: str
    title: str
    content: str  # Markdown content
    order: int = 0
    subsections: list[ReportSection] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    report_id: str
    task_id: str
    title: str
    summary: str
    sections: list[ReportSection]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    review_score: float | None = None
    total_evidence_items: int = 0
    metadata: dict = Field(default_factory=dict)
