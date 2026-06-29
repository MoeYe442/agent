from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.enums import AgentRole


class AgentContract(BaseModel):
    """Structured contract defining an agent's responsibilities and constraints.

    Each contract specifies what an agent is allowed to do, what it must
    produce, and what constitutes failure. Used by BaseAgent for runtime
    validation.
    """

    agent_role: AgentRole
    description: str = ""
    input_schema: list[str] = Field(default_factory=list)
    output_schema: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    fallback_behavior: str = "skip"
    quality_gate: dict[str, float] = Field(default_factory=dict)
