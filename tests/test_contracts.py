from __future__ import annotations

import pytest
from src.models.contract import AgentContract
from src.models.enums import AgentRole


class TestAgentContract:
    def test_contract_creation_minimal(self):
        """AgentContract can be created with required fields."""
        contract = AgentContract(
            agent_role=AgentRole.PLANNER,
            description="Plans research tasks",
            input_schema=["task_spec"],
            output_schema=["plan"],
            allowed_tools=["read_file"],
            forbidden_actions=[],
            failure_conditions=[],
            fallback_behavior="skip",
            quality_gate={"min_plan_steps": 3},
        )
        assert contract.agent_role == AgentRole.PLANNER
        assert contract.description == "Plans research tasks"
        assert contract.input_schema == ["task_spec"]
        assert contract.output_schema == ["plan"]
        assert contract.allowed_tools == ["read_file"]
        assert contract.quality_gate["min_plan_steps"] == 3

    def test_contract_defaults(self):
        """AgentContract provides sensible defaults for list fields."""
        contract = AgentContract(
            agent_role=AgentRole.RESEARCHER,
            description="Researches information",
            input_schema=[],
            output_schema=[],
            allowed_tools=[],
            forbidden_actions=[],
            failure_conditions=[],
            fallback_behavior="skip",
        )
        assert contract.quality_gate == {}
        assert contract.forbidden_actions == []

    def test_all_agent_roles_supported(self):
        """Every AgentRole can have a contract."""
        for role in AgentRole:
            contract = AgentContract(
                agent_role=role,
                description=f"Contract for {role.value}",
                input_schema=[],
                output_schema=[],
                allowed_tools=[],
                forbidden_actions=[],
                failure_conditions=[],
                fallback_behavior="skip",
            )
            assert contract.agent_role == role
