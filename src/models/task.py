from __future__ import annotations

from datetime import datetime

try:
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum  # type: ignore[import-not-found,no-redef]

from pydantic import BaseModel, Field

from src.models.enums import TaskPhase


class TaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskSpec(BaseModel):
    """User-submitted task specification."""

    query: str = Field(..., description="Research question or analysis goal")
    repo_urls: list[str] = Field(
        default_factory=list, description="GitHub repository URLs to analyze"
    )
    target_files: list[str] = Field(
        default_factory=list, description="Specific files or directories"
    )
    web_urls: list[str] = Field(
        default_factory=list, description="Web pages to scrape for context"
    )
    max_depth: int = Field(default=3, ge=1, le=10, description="Code analysis depth")
    language: str = Field(
        default="auto", description="Target programming language or 'auto'"
    )


class TaskRecord(BaseModel):
    """Full task record persisted in Redis."""

    task_id: str
    spec: TaskSpec
    status: TaskStatus = TaskStatus.PENDING
    phase: TaskPhase | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    error_message: str | None = None
    result_summary: str | None = None
