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


class TestEvidenceItemExtended:
    def test_evidence_item_new_fields_defaults(self):
        """New fields on EvidenceItem have correct defaults."""
        from src.models.evidence import EvidenceItem
        from src.models.enums import SourceType

        item = EvidenceItem(
            evidence_id="ev_001",
            task_id="task_001",
            source_type=SourceType.CODE_FILE,
            source_path="src/main.py",
            content_hash="abc123",
            excerpt="app = FastAPI()",
            full_content_ref="src/main.py:24-86",
        )
        assert item.line_range is None
        assert item.confidence_score is None
        assert item.collected_by is None
        assert item.corroboration_count == 0
        assert item.cross_references == []
        assert item.related_claim is None

    def test_evidence_item_with_confidence(self):
        """EvidenceItem accepts confidence-related fields."""
        from src.models.evidence import EvidenceItem
        from src.models.enums import SourceType, AgentRole

        item = EvidenceItem(
            evidence_id="ev_002",
            task_id="task_001",
            source_type=SourceType.CODE_FILE,
            source_path="src/main.py",
            content_hash="abc123",
            excerpt="app = FastAPI()",
            full_content_ref="src/main.py:24-86",
            line_range=(24, 86),
            confidence_score=0.90,
            collected_by=AgentRole.CODE_READER,
            corroboration_count=2,
            cross_references=["ev_005", "ev_012"],
            related_claim="FastAPI entry point",
        )
        assert item.line_range == (24, 86)
        assert item.confidence_score == 0.90
        assert item.collected_by == AgentRole.CODE_READER
        assert item.corroboration_count == 2
        assert item.cross_references == ["ev_005", "ev_012"]
        assert item.related_claim == "FastAPI entry point"

    def test_evidence_chain_confidence_summary(self):
        """EvidenceChain has confidence_summary field with default None."""
        from src.models.evidence import EvidenceChain

        chain = EvidenceChain(task_id="task_001", items=[])
        assert chain.confidence_summary is None

        chain_with_summary = EvidenceChain(
            task_id="task_001",
            items=[],
            confidence_summary={"code_file": 0.90, "web_page": 0.45},
        )
        assert chain_with_summary.confidence_summary == {"code_file": 0.90, "web_page": 0.45}
