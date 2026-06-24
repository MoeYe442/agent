from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    tool_name: str
    params_json: str = ""
    result_summary: str = ""
    exception: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    success: bool = True
    agent_role: str = ""
