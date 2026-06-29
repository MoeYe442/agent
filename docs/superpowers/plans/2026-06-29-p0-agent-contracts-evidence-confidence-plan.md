# P0: Agent Contracts + Evidence Confidence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Agent role contracts with runtime validation and evidence confidence scoring with a pure rule engine.

**Architecture:** Add `AgentContract` Pydantic model + `BaseAgent` ABC with template-method validation. Add `ConfidenceCalculator` rule engine. Refactor 6 agent nodes from standalone functions to `BaseAgent` subclasses. Wire confidence scoring into evidence creation and reporting.

**Tech Stack:** Python 3.12+, Pydantic, LangGraph, pytest + pytest-asyncio

## Global Constraints

- Zero infrastructure dependencies (Redis/Milvus must remain optional)
- Existing API interfaces unchanged (data model additions must be backward compatible)
- Agent core LLM logic unchanged (only outer structure changes)
- LangGraph routing unchanged (conditional edges remain identical)
- All existing tests must continue to pass

---

## File Structure

| Operation | File | Responsibility |
|-----------|------|----------------|
| Create | `src/models/contract.py` | `AgentContract` Pydantic model |
| Modify | `src/models/evidence.py` | Add 6 fields to `EvidenceItem`, 1 to `EvidenceChain` |
| Create | `src/evaluation/__init__.py` | Module marker |
| Create | `src/evaluation/confidence.py` | `ConfidenceCalculator` rule engine |
| Modify | `src/agents/base.py` | Add `BaseAgent` ABC + retain existing 3 utility functions |
| Modify | `src/agents/planner.py` | `PlannerAgent(BaseAgent)` |
| Modify | `src/agents/researcher.py` | `ResearcherAgent(BaseAgent)` |
| Modify | `src/agents/code_reader.py` | `CodeReaderAgent(BaseAgent)` |
| Modify | `src/agents/executor.py` | `ExecutorAgent(BaseAgent)` |
| Modify | `src/agents/reviewer.py` | `ReviewerAgent(BaseAgent)` |
| Modify | `src/agents/reporter.py` | `ReporterAgent(BaseAgent)` |
| Modify | `src/workflow/graph.py` | Wire agent instances instead of raw functions |
| Create | `tests/test_contracts.py` | Tests for `AgentContract` + `BaseAgent` validation |
| Create | `tests/test_confidence.py` | Tests for `ConfidenceCalculator` |
| Modify | `tests/test_agents.py` | Update tests for new agent class interface |
| Modify | `tests/conftest.py` | Add `mock_tool_registry` fixture |

---

### Task 1: AgentContract Data Model

**Files:**
- Create: `src/models/contract.py`
- Create: `tests/test_contracts.py`

**Interfaces:**
- Produces: `AgentContract` Pydantic model with fields `agent_role: AgentRole`, `description: str`, `input_schema: list[str]`, `output_schema: list[str]`, `allowed_tools: list[str]`, `forbidden_actions: list[str]`, `failure_conditions: list[str]`, `fallback_behavior: str`, `quality_gate: dict[str, float]`

- [ ] **Step 1: Write failing test for AgentContract model**

```python
# tests/test_contracts.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_contracts.py -v`
Expected: FAIL with "No module named 'src.models.contract'"

- [ ] **Step 3: Create AgentContract model**

```python
# src/models/contract.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_contracts.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/models/contract.py tests/test_contracts.py
git commit -m "feat: add AgentContract data model

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Evidence Model Extensions

**Files:**
- Modify: `src/models/evidence.py`
- Modify: `tests/test_contracts.py` (add evidence model tests)

**Interfaces:**
- Modifies: `EvidenceItem` — adds `line_range`, `confidence_score`, `collected_by`, `corroboration_count`, `cross_references`, `related_claim`
- Modifies: `EvidenceChain` — adds `confidence_summary`

- [ ] **Step 1: Write failing tests for new evidence fields**

Append to `tests/test_contracts.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_contracts.py::TestEvidenceItemExtended -v`
Expected: FAIL (AttributeError on new fields)

- [ ] **Step 3: Modify EvidenceItem and EvidenceChain**

```python
# src/models/evidence.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.enums import AgentRole, SourceType


class EvidenceItem(BaseModel):
    evidence_id: str
    task_id: str
    source_type: SourceType
    source_path: str
    content_hash: str
    excerpt: str
    full_content_ref: str
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
    relationships: list[tuple[str, str]] = Field(default_factory=list)
    confidence_summary: dict | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_contracts.py::TestEvidenceItemExtended -v`
Expected: 3 PASS

- [ ] **Step 5: Run all existing tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: All existing tests continue to pass

- [ ] **Step 6: Commit**

```bash
git add src/models/evidence.py tests/test_contracts.py
git commit -m "feat: extend EvidenceItem and EvidenceChain with confidence fields

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: ConfidenceCalculator Rule Engine

**Files:**
- Create: `src/evaluation/__init__.py`
- Create: `src/evaluation/confidence.py`
- Create: `tests/test_confidence.py`

**Interfaces:**
- Produces: `ConfidenceCalculator.calculate(evidence: EvidenceItem) -> float`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_confidence.py
from __future__ import annotations

import pytest
from src.models.evidence import EvidenceItem
from src.models.enums import SourceType, AgentRole


class TestConfidenceCalculator:
    @pytest.fixture
    def calculator(self):
        from src.evaluation.confidence import ConfidenceCalculator
        return ConfidenceCalculator()

    def test_code_file_gets_high_confidence(self, calculator):
        """CODE_FILE source with line_range gets baseline 0.90 + 0.05 = 0.95."""
        item = EvidenceItem(
            evidence_id="ev_001",
            task_id="task_001",
            source_type=SourceType.CODE_FILE,
            source_path="src/main.py",
            content_hash="abc",
            excerpt="code",
            full_content_ref="src/main.py:24-86",
            line_range=(24, 86),
            collected_by=AgentRole.CODE_READER,
            corroboration_count=2,
        )
        score = calculator.calculate(item)
        assert score == pytest.approx(0.95)

    def test_web_page_gets_low_confidence(self, calculator):
        """WEB_PAGE source with no corroboration gets 0.50 * 0.85 = 0.425."""
        item = EvidenceItem(
            evidence_id="ev_002",
            task_id="task_001",
            source_type=SourceType.WEB_PAGE,
            source_path="https://example.com",
            content_hash="abc",
            excerpt="some text",
            full_content_ref="https://example.com",
        )
        score = calculator.calculate(item)
        assert score == pytest.approx(0.425)

    def test_no_line_range_penalty(self, calculator):
        """CODE_FILE without line_range gets 0.90 * 0.90 = 0.81 (no line) then * 0.85 (no corroboration) = 0.6885."""
        item = EvidenceItem(
            evidence_id="ev_003",
            task_id="task_001",
            source_type=SourceType.CODE_FILE,
            source_path="src/main.py",
            content_hash="abc",
            excerpt="code",
            full_content_ref="src/main.py",
        )
        score = calculator.calculate(item)
        assert score == pytest.approx(0.6885)

    def test_document_baseline(self, calculator):
        """DOCUMENT with line_range + corroboration >= 2 gets 0.85 + 0.10 = 0.95."""
        item = EvidenceItem(
            evidence_id="ev_004",
            task_id="task_001",
            source_type=SourceType.DOCUMENT,
            source_path="docs/api.md",
            content_hash="abc",
            excerpt="docs text",
            full_content_ref="docs/api.md",
            line_range=(12, 40),
            corroboration_count=2,
        )
        score = calculator.calculate(item)
        assert score == pytest.approx(0.95)

    def test_rag_chunk_baseline(self, calculator):
        """RAG_CHUNK with no corroboration, no line_range: 0.60 * 0.90 * 0.85 = 0.459."""
        item = EvidenceItem(
            evidence_id="ev_005",
            task_id="task_001",
            source_type=SourceType.RAG_CHUNK,
            source_path="src/module.py",
            content_hash="abc",
            excerpt="retrieved chunk",
            full_content_ref="chunk_001",
        )
        score = calculator.calculate(item)
        assert score == pytest.approx(0.459)

    def test_score_clamped_to_max(self, calculator):
        """Score cannot exceed 0.95."""
        item = EvidenceItem(
            evidence_id="ev_006",
            task_id="task_001",
            source_type=SourceType.CODE_FILE,
            source_path="src/main.py",
            content_hash="abc",
            excerpt="code",
            full_content_ref="src/main.py:24-86",
            line_range=(24, 86),
            corroboration_count=5,  # Multiple corroboration, but clamp at 0.95
        )
        score = calculator.calculate(item)
        assert score <= 0.95

    def test_score_clamped_to_min(self, calculator):
        """Score cannot go below 0.05."""
        item = EvidenceItem(
            evidence_id="ev_007",
            task_id="task_001",
            source_type=SourceType.WEB_PAGE,
            source_path="https://example.com",
            content_hash="abc",
            excerpt="unreliable text",
            full_content_ref="https://example.com",
        )
        score = calculator.calculate(item)
        assert score >= 0.05

    def test_github_repo_baseline(self, calculator):
        """GITHUB_REPO with line_range and corroboration>=2: 0.80 base, no decay, +0.10 enhancement = 0.90."""
        item = EvidenceItem(
            evidence_id="ev_008",
            task_id="task_001",
            source_type=SourceType.GITHUB_REPO,
            source_path="https://github.com/example/repo",
            content_hash="abc",
            excerpt="commit log",
            full_content_ref="abc123",
            line_range=(1, 10),
            corroboration_count=2,
        )
        score = calculator.calculate(item)
        assert score == pytest.approx(0.90)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_confidence.py -v`
Expected: FAIL "No module named 'src.evaluation.confidence'"

- [ ] **Step 3: Create evaluation module**

```python
# src/evaluation/__init__.py
from __future__ import annotations

from src.evaluation.confidence import ConfidenceCalculator

__all__ = ["ConfidenceCalculator"]
```

```python
# src/evaluation/confidence.py
from __future__ import annotations

import structlog

from src.models.enums import SourceType
from src.models.evidence import EvidenceItem

logger = structlog.get_logger(__name__)


class ConfidenceCalculator:
    """Pure rule-engine for computing evidence confidence scores.

    Confidence = clamp(base_score * decay_factors + enhancement_factors, 0.05, 0.95)
    """

    BASE_SCORES: dict[SourceType, float] = {
        SourceType.CODE_FILE: 0.90,
        SourceType.DOCUMENT: 0.85,
        SourceType.GITHUB_REPO: 0.80,
        SourceType.COMMAND_OUTPUT: 0.75,
        SourceType.RAG_CHUNK: 0.60,
        SourceType.WEB_PAGE: 0.50,
    }

    MIN_SCORE: float = 0.05
    MAX_SCORE: float = 0.95

    # Decay multipliers
    DECAY_NO_LINE_RANGE: float = 0.90
    DECAY_NO_CORROBORATION: float = 0.85

    # Enhancement adders
    ENHANCE_MULTI_CORROBORATION: float = 0.10
    ENHANCE_CODE_WITH_LINE: float = 0.05

    def calculate(self, evidence: EvidenceItem) -> float:
        """Calculate confidence score for an evidence item.

        Args:
            evidence: The evidence item to score.

        Returns:
            Confidence score clamped to [MIN_SCORE, MAX_SCORE].
        """
        base = self.BASE_SCORES.get(evidence.source_type, 0.50)
        score = float(base)

        # Decay factors (multiplicative)
        if evidence.line_range is None:
            score *= self.DECAY_NO_LINE_RANGE

        if evidence.corroboration_count == 0:
            score *= self.DECAY_NO_CORROBORATION

        # Enhancement factors (additive)
        if evidence.corroboration_count >= 2:
            score += self.ENHANCE_MULTI_CORROBORATION

        if evidence.source_type == SourceType.CODE_FILE and evidence.line_range is not None:
            score += self.ENHANCE_CODE_WITH_LINE

        result = max(self.MIN_SCORE, min(self.MAX_SCORE, score))
        logger.debug(
            "confidence_calculated",
            evidence_id=evidence.evidence_id,
            source_type=evidence.source_type.value,
            base=base,
            final=result,
        )
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_confidence.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/__init__.py src/evaluation/confidence.py tests/test_confidence.py
git commit -m "feat: add ConfidenceCalculator rule engine for evidence scoring

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: BaseAgent Abstract Class

**Files:**
- Modify: `src/agents/base.py` (add BaseAgent, retain existing 3 utility functions)
- Modify: `tests/test_contracts.py` (add BaseAgent validation tests)

**Interfaces:**
- Produces: `BaseAgent(ABC)` with `__init__(llm_client, tool_registry=None)`, `contract: AgentContract`, `async execute(state) -> dict`, `async _run(state) -> dict` (abstract)
- Internal: `_validate_input(state)`, `_validate_output(result)`, `_audit_tools(result, state)`, `_check_quality_gate(result)`

- [ ] **Step 1: Write failing tests for BaseAgent**

Append to `tests/test_contracts.py`:

```python
def _make_test_agent(**contract_kwargs):
    """Helper to create a minimal BaseAgent subclass with a specific contract."""
    from src.models.contract import AgentContract
    from src.models.enums import AgentRole

    defaults = {
        "agent_role": AgentRole.PLANNER,
        "description": "test",
        "input_schema": [],
        "output_schema": [],
        "allowed_tools": [],
        "forbidden_actions": [],
        "failure_conditions": [],
        "fallback_behavior": "skip",
    }
    defaults.update(contract_kwargs)

    class _TestAgent(BaseAgent):
        contract = AgentContract(**defaults)

        async def _run(self, state):
            return {"phase": "done"}

    return _TestAgent(llm_client=None)


class TestBaseAgentValidation:
    """Tests for BaseAgent template-method validation logic."""

    def test_validate_input_missing_field(self):
        """_validate_input adds error when input_schema field is missing."""
        from src.models.enums import AgentRole

        agent = _make_test_agent(
            agent_role=AgentRole.PLANNER,
            input_schema=["required_field"],
        )
        state = {"other_field": "value", "errors": []}
        errors = []
        agent._validate_input(state, errors)
        assert len(errors) == 1
        assert "required_field" in errors[0]

    def test_validate_input_field_present(self):
        """_validate_input adds no error when input_schema field is present."""
        from src.models.enums import AgentRole

        agent = _make_test_agent(
            agent_role=AgentRole.PLANNER,
            input_schema=["required_field"],
        )
        state = {"required_field": "hello", "errors": []}
        errors = []
        agent._validate_input(state, errors)
        assert len(errors) == 0

    def test_validate_output_missing_field(self):
        """_validate_output adds error when output_schema field is missing."""
        from src.models.enums import AgentRole

        agent = _make_test_agent(
            agent_role=AgentRole.PLANNER,
            output_schema=["plan"],
        )
        result = {"other": "value"}
        errors = []
        agent._validate_output(result, errors)
        assert len(errors) == 1
        assert "plan" in errors[0]

    def test_validate_output_field_present(self):
        """_validate_output adds no error when output_schema field is present."""
        from src.models.enums import AgentRole

        agent = _make_test_agent(
            agent_role=AgentRole.PLANNER,
            output_schema=["plan"],
        )
        result = {"plan": [{"step": 1}]}
        errors = []
        agent._validate_output(result, errors)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_calls_validate_and_run(self):
        """execute() calls _validate_input, _run, _validate_output, _audit_tools, _check_quality_gate in order."""
        from src.agents.base import BaseAgent
        from src.models.contract import AgentContract
        from src.models.enums import AgentRole

        call_order = []

        class OrderedAgent(BaseAgent):
            contract = AgentContract(
                agent_role=AgentRole.PLANNER,
                description="test",
                input_schema=[],
                output_schema=[],
                allowed_tools=[],
                forbidden_actions=[],
                failure_conditions=[],
                fallback_behavior="skip",
            )

            def _validate_input(self, state, errors):
                call_order.append("validate_input")

            async def _run(self, state):
                call_order.append("run")
                return {"plan": []}

            def _validate_output(self, result, errors):
                call_order.append("validate_output")

            def _audit_tools(self, result, state, errors):
                call_order.append("audit_tools")

            def _check_quality_gate(self, result):
                call_order.append("quality_gate")

        agent = OrderedAgent(llm_client=None)
        result = await agent.execute({"errors": []})
        assert call_order == ["validate_input", "run", "validate_output", "audit_tools", "quality_gate"]

    def test_check_quality_gate_passes(self):
        """_check_quality_gate returns True when result meets thresholds."""
        from src.models.enums import AgentRole

        agent = _make_test_agent(
            agent_role=AgentRole.PLANNER,
            quality_gate={"min_plan_steps": 3},
        )
        result = {"plan": [1, 2, 3, 4]}  # len 4 >= 3
        gate_result = agent._check_quality_gate(result)
        assert gate_result is True

    def test_check_quality_gate_fails(self):
        """_check_quality_gate returns False when result fails threshold."""
        from src.models.enums import AgentRole

        agent = _make_test_agent(
            agent_role=AgentRole.PLANNER,
            quality_gate={"min_plan_steps": 3},
        )
        result = {"plan": [1]}  # len 1 < 3
        gate_result = agent._check_quality_gate(result)
        assert gate_result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_contracts.py::TestBaseAgentValidation -v`
Expected: FAIL "cannot import BaseAgent"

- [ ] **Step 3: Add BaseAgent to src/agents/base.py**

Insert after the existing utility functions (after line 183 in current base.py, keeping all existing code):

```python
# Add to imports at top of src/agents/base.py:
from abc import ABC, abstractmethod

# Add after the existing call_llm_with_tools function:
class BaseAgent(ABC):
    """Abstract base class for all agents with contract-driven validation.

    Subclasses define their contract and implement _run(). The execute()
    method is a template method that validates input/output, audits tool
    usage, and checks quality gates around the agent's core logic.
    """

    contract: AgentContract

    def __init__(self, llm_client: Any, tool_registry: Any = None) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry

    async def execute(self, state: AgentState) -> dict:
        """Template method: validate, run, validate, audit, quality-gate."""
        errors: list[str] = list(state.get("errors", []))

        self._validate_input(state, errors)

        result = await self._run(state)

        self._validate_output(result, errors)
        self._audit_tools(result, state, errors)
        quality_passed = self._check_quality_gate(result)

        if not quality_passed:
            errors.append(
                f"Quality gate not passed for {self.contract.agent_role.value}: "
                f"{self.contract.quality_gate}"
            )

        if errors:
            result["errors"] = errors
        result["current_agent"] = self.contract.agent_role.value
        return result

    @abstractmethod
    async def _run(self, state: AgentState) -> dict:
        """Core agent logic. Subclasses must implement this."""
        ...

    def _validate_input(self, state: AgentState, errors: list[str]) -> None:
        """Check that required input_schema fields exist in state."""
        for field in self.contract.input_schema:
            if field not in state or state.get(field) is None:
                msg = (
                    f"Agent '{self.contract.agent_role.value}': "
                    f"required input field '{field}' missing or None in state"
                )
                logger.warning("contract_input_validation_failed", field=field, agent=self.contract.agent_role.value)
                errors.append(msg)

    def _validate_output(self, result: dict, errors: list[str]) -> None:
        """Check that required output_schema fields exist in result."""
        for field in self.contract.output_schema:
            if field not in result:
                msg = (
                    f"Agent '{self.contract.agent_role.value}': "
                    f"required output field '{field}' missing from result"
                )
                logger.warning("contract_output_validation_failed", field=field, agent=self.contract.agent_role.value)
                errors.append(msg)

    def _audit_tools(self, result: dict, state: AgentState, errors: list[str]) -> None:
        """Check that any tools used are in the allowed_tools whitelist.

        Scans tool_log for entries that appeared during this agent's run.
        """
        if not self.contract.allowed_tools:
            return

        allowed = set(self.contract.allowed_tools)
        # Check tool_log from state - we scan recent entries
        tool_log = state.get("tool_log", [])
        for tc in tool_log[-20:]:
            tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
            tool_name = tc_dict.get("tool_name", "")
            if tool_name and tool_name not in allowed:
                msg = (
                    f"Agent '{self.contract.agent_role.value}': "
                    f"tool '{tool_name}' not in allowed_tools whitelist"
                )
                logger.warning("contract_tool_violation", tool=tool_name, agent=self.contract.agent_role.value)
                if msg not in errors:
                    errors.append(msg)

    def _check_quality_gate(self, result: dict) -> bool:
        """Check if result passes quality gate thresholds.

        Quality gates use simple comparisons:
        - "min_<field>": result[field] must have len() >= value
        - "<field>_gte": result[field] must be >= value
        """
        if not self.contract.quality_gate:
            return True

        for key, threshold in self.contract.quality_gate.items():
            if key.startswith("min_"):
                field_name = key[4:]  # strip "min_" prefix
                actual = result.get(field_name)
                if actual is None:
                    return False
                if isinstance(actual, (list, str, dict)):
                    if len(actual) < threshold:
                        return False
                else:
                    if actual < threshold:
                        return False
            elif key.endswith("_gte"):
                field_name = key[:-4]  # strip "_gte" suffix
                actual = result.get(field_name)
                if actual is None:
                    return False
                if isinstance(actual, (int, float)):
                    if actual < threshold:
                        return False

        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_contracts.py::TestBaseAgentValidation -v`
Expected: 7 PASS

- [ ] **Step 5: Run all existing tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: All existing tests continue to pass (BaseAgent is added but no agent uses it yet)

- [ ] **Step 6: Commit**

```bash
git add src/agents/base.py tests/test_contracts.py
git commit -m "feat: add BaseAgent ABC with contract-driven validation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: PlannerAgent Refactor

**Files:**
- Modify: `src/agents/planner.py`

**Interfaces:**
- Consumes: `BaseAgent` from `src.agents.base`, `AgentContract` from `src.models.contract`
- Produces: `PlannerAgent(BaseAgent)` with contract, `planner_node` retained as backward-compat wrapper

- [ ] **Step 1: Refactor planner.py**

```python
# src/agents/planner.py
from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.base import BaseAgent, call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.models.enums import AgentRole, TaskPhase

logger = structlog.get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a research planner. Given a user's research question and context about a code repository, create a structured research plan.

Your task:
1. Analyze the research question
2. Break it into concrete, sequential sub-tasks
3. For each sub-task, specify which agent role should handle it and what information to gather

Output a JSON array of plan items. Each item must have:
- "step": integer (1-based)
- "title": short description
- "agent": one of "researcher", "code_reader", "executor"
- "goal": what this step should accomplish
- "tools": list of tool names that may be useful

Return ONLY valid JSON (no markdown code fences)."""

PLANNER_CONTRACT = AgentContract(
    agent_role=AgentRole.PLANNER,
    description="Parse research questions and produce step-by-step plans. Do not analyze code or draw conclusions.",
    input_schema=["task_spec"],
    output_schema=["plan", "phase"],
    allowed_tools=["read_file", "list_directory"],
    forbidden_actions=["analyze source code logic", "infer architecture conclusions", "search the web"],
    failure_conditions=["plan is empty", "plan step is not executable"],
    fallback_behavior="Produce a default single-step plan",
    quality_gate={"min_plan": 1},
)


class PlannerAgent(BaseAgent):
    contract = PLANNER_CONTRACT

    async def _run(self, state: AgentState) -> dict:
        query = state.get("task_spec", {}).get("query", "") if isinstance(state.get("task_spec"), dict) else getattr(state.get("task_spec", ""), "query", "")
        repo_urls = []
        if isinstance(state.get("task_spec"), dict):
            repo_urls = state["task_spec"].get("repo_urls", [])
        elif hasattr(state.get("task_spec"), "repo_urls"):
            repo_urls = getattr(state["task_spec"], "repo_urls", [])

        findings_summary = ""
        if state.get("findings"):
            findings_summary = json.dumps(state["findings"][-5:], default=str)

        user_msg = f"""Research Question: {query}
Repository URLs: {', '.join(repo_urls) if repo_urls else 'none'}
Previous findings (if any): {findings_summary}

Create a research plan for this question."""

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        response = await call_llm_with_tools(self.llm_client, messages, tool_schemas=None, temperature=0.2)
        content = response.get("content", "")

        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            plan = json.loads(cleaned)
            if not isinstance(plan, list):
                plan = [plan]
        except (json.JSONDecodeError, AttributeError):
            logger.warning("plan_parse_failed", content=content[:200])
            plan = [{"step": 1, "title": "Analyze and research", "agent": "researcher", "goal": query, "tools": []}]

        logger.info("plan_created", steps=len(plan))
        return {
            "plan": plan,
            "phase": TaskPhase.RESEARCHING,
        }


# Backward-compatible wrapper for existing callers
async def planner_node(state: AgentState, llm_client: Any) -> dict:
    agent = PlannerAgent(llm_client)
    return await agent.execute(state)
```

- [ ] **Step 2: Run planner tests**

Run: `pytest tests/test_agents.py::TestPlanner -v`
Expected: PASS (planner_node still works via backward-compat wrapper)

- [ ] **Step 3: Commit**

```bash
git add src/agents/planner.py
git commit -m "refactor: PlannerAgent extends BaseAgent with contract

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: ResearcherAgent Refactor

**Files:**
- Modify: `src/agents/researcher.py`

**Interfaces:**
- Consumes: `BaseAgent`, `AgentContract`, `ConfidenceCalculator`
- Produces: `ResearcherAgent(BaseAgent)` with contract

- [ ] **Step 1: Refactor researcher.py**

```python
# src/agents/researcher.py
from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from src.agents.base import BaseAgent, call_llm_with_tools
from src.evaluation.confidence import ConfidenceCalculator
from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.models.enums import AgentRole, SourceType, TaskPhase
from src.models.evidence import EvidenceItem
from src.tools.registry import get_tool_schemas

logger = structlog.get_logger(__name__)

RESEARCHER_SYSTEM_PROMPT = """You are a code researcher. Your job is to gather information about a software project by:
1. Scraping relevant web pages for documentation and context
2. Reading key project files (README, config files, setup scripts)
3. Searching for information relevant to the research question

Available tools: read_file, list_directory, search_code, scrape_page, get_repo_info.

For each piece of information you find, note:
- Where it came from (URL, file path)
- Why it's relevant to the research question
- A confidence level (high/medium/low)

Be thorough but focused on the research question."""

RESEARCHER_CONTRACT = AgentContract(
    agent_role=AgentRole.RESEARCHER,
    description="Gather external information: web docs, GitHub Issues, official docs. Do not analyze private code logic.",
    input_schema=["task_spec", "plan"],
    output_schema=["findings", "evidence", "phase"],
    allowed_tools=["read_file", "list_directory", "search_code", "scrape_page", "get_repo_info"],
    forbidden_actions=["analyze source code internals", "make architectural conclusions"],
    failure_conditions=["all external sources unavailable"],
    fallback_behavior="Output findings with low-confidence markers",
    quality_gate={"min_findings": 1},
)


class ResearcherAgent(BaseAgent):
    contract = RESEARCHER_CONTRACT

    def __init__(self, llm_client: Any, tool_registry: Any = None, rag_pipeline: Any = None) -> None:
        super().__init__(llm_client, tool_registry)
        self.rag_pipeline = rag_pipeline
        self.confidence_calc = ConfidenceCalculator()

    async def _run(self, state: AgentState) -> dict:
        query = ""
        if isinstance(state.get("task_spec"), dict):
            query = state["task_spec"].get("query", "")
        elif hasattr(state.get("task_spec"), "query"):
            query = getattr(state["task_spec"], "query", "")

        plan = state.get("plan", [])
        researcher_steps = [p for p in plan if isinstance(p, dict) and p.get("agent") == "researcher"]
        step_text = json.dumps(researcher_steps[:3], default=str) if researcher_steps else "Gather general project information"

        user_msg = f"""Research Question: {query}
Plan steps for you: {step_text}

Current findings so far: {json.dumps(state.get('findings', [])[-5:], default=str)}

Please gather information to address these research steps. Use available tools to:
1. Read key project files (README, config, setup.py, pyproject.toml, etc.)
2. Search for relevant code patterns
3. Scrape documentation pages if URLs are available

Important: Record each finding with its source."""

        messages = [
            {"role": "system", "content": RESEARCHER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        tool_schemas = get_tool_schemas()
        response = await call_llm_with_tools(self.llm_client, messages, tool_schemas, temperature=0.3)
        content = response.get("content", "")

        findings = list(state.get("findings", []))
        findings.append({
            "agent": "researcher",
            "content": content,
            "timestamp": str(uuid.uuid4()),
        })

        # RAG search
        rag_results = []
        if self.rag_pipeline is not None:
            try:
                rag_results = await self.rag_pipeline.search(query, top_k=5, alpha=0.5, rerank=True)
            except Exception as exc:
                logger.warning("rag_search_failed", error=str(exc))

        # Build evidence with confidence scoring
        evidence = list(state.get("evidence", []))
        tool_log = state.get("tool_log", [])
        task_id = state.get("task_id", "")

        for tc in tool_log[-10:]:
            tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
            item = EvidenceItem(
                evidence_id=uuid.uuid4().hex,
                task_id=task_id,
                source_type=SourceType.COMMAND_OUTPUT,
                source_path=tc_dict.get("params_json", ""),
                content_hash=str(hash(tc_dict.get("result_summary", ""))),
                excerpt=tc_dict.get("result_summary", "")[:500],
                full_content_ref=tc_dict.get("params_json", ""),
                agent_role="researcher",
                collected_by=AgentRole.RESEARCHER,
            )
            item.confidence_score = self.confidence_calc.calculate(item)
            evidence.append(item.model_dump())

        for rr in rag_results:
            item = EvidenceItem(
                evidence_id=uuid.uuid4().hex,
                task_id=task_id,
                source_type=SourceType.RAG_CHUNK,
                source_path=rr.chunk.source_path,
                content_hash=str(hash(rr.chunk.content)),
                excerpt=rr.chunk.content[:500],
                full_content_ref=rr.chunk.chunk_id,
                agent_role="researcher",
                relevance_score=rr.score,
                collected_by=AgentRole.RESEARCHER,
            )
            item.confidence_score = self.confidence_calc.calculate(item)
            evidence.append(item.model_dump())

        return {
            "findings": findings + [{"rag_results": [r.model_dump() for r in rag_results] if rag_results else []}],
            "evidence": evidence,
            "phase": TaskPhase.READING,
        }


# Backward-compatible wrapper
async def researcher_node(state: AgentState, llm_client: Any, rag_pipeline: Any = None) -> dict:
    agent = ResearcherAgent(llm_client, rag_pipeline=rag_pipeline)
    return await agent.execute(state)
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add src/agents/researcher.py
git commit -m "refactor: ResearcherAgent extends BaseAgent with confidence scoring

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: CodeReaderAgent Refactor

**Files:**
- Modify: `src/agents/code_reader.py`

**Interfaces:**
- Consumes: `BaseAgent`, `AgentContract`, `ConfidenceCalculator`
- Produces: `CodeReaderAgent(BaseAgent)` with contract

- [ ] **Step 1: Refactor code_reader.py**

```python
# src/agents/code_reader.py
from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from src.agents.base import BaseAgent, call_llm_with_tools
from src.evaluation.confidence import ConfidenceCalculator
from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.models.enums import AgentRole, SourceType, TaskPhase
from src.models.evidence import EvidenceItem

logger = structlog.get_logger(__name__)

CODE_READER_SYSTEM_PROMPT = """You are a code analysis specialist. Your job is to deeply analyze source code:
1. Read source files to understand architecture and design patterns
2. Trace function call chains and data flow
3. Identify key abstractions, classes, and modules
4. Build a mental model of how the codebase is structured

Available tools: read_file, list_directory, search_code.

For each file you analyze, note:
- The purpose of the file/module
- Key functions/classes and their responsibilities
- Dependencies and imports
- How it connects to the rest of the codebase"""

CODE_READER_CONTRACT = AgentContract(
    agent_role=AgentRole.CODE_READER,
    description="Deep code analysis: entry paths, module structure, call chains, design patterns. Core analysis engine.",
    input_schema=["task_spec", "findings"],
    output_schema=["findings", "evidence", "phase"],
    allowed_tools=["read_file", "list_directory", "search_code"],
    forbidden_actions=["guess nonexistent code paths", "execute commands", "browse web pages"],
    failure_conditions=["symbol resolution failure rate > 30%", "cannot locate core entry module"],
    fallback_behavior="Mark unconfirmed runtime behavior as speculative for Executor verification",
    quality_gate={"min_findings": 1},
)


class CodeReaderAgent(BaseAgent):
    contract = CODE_READER_CONTRACT

    def __init__(self, llm_client: Any, tool_registry: Any = None, project_index: Any = None, repo_path: str = "") -> None:
        super().__init__(llm_client, tool_registry)
        self.project_index = project_index
        self.repo_path = repo_path
        self.confidence_calc = ConfidenceCalculator()

    async def _run(self, state: AgentState) -> dict:
        query = ""
        if isinstance(state.get("task_spec"), dict):
            query = state["task_spec"].get("query", "")
        elif hasattr(state.get("task_spec"), "query"):
            query = getattr(state["task_spec"], "query", "")

        findings = state.get("findings", [])
        findings_summary = json.dumps(findings[-5:], default=str) if findings else "None"

        index_info = ""
        pi = self.project_index
        if pi is not None:
            if hasattr(pi, "model_dump"):
                pi = pi.model_dump()
            elif not isinstance(pi, dict):
                pi = {}
            index_info = f"""
Project Index:
- Files: {len(pi.get('files', []))}
- Symbols: {len(pi.get('symbols', []))}
- Key symbols: {json.dumps([s.get('name', '') for s in pi.get('symbols', [])[:30]], default=str)}
"""

        user_msg = f"""Research Question: {query}
Repository path: {self.repo_path}
Previous findings: {findings_summary}
{index_info}

Please analyze the codebase deeply. Focus on:
1. Core architecture and module organization
2. Key functions and classes and their relationships
3. Data flow and business logic
4. How the code relates to the research question

Use available tools to read and search files."""

        messages = [
            {"role": "system", "content": CODE_READER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        from src.tools.registry import get_tool_schemas

        response = await call_llm_with_tools(self.llm_client, messages, get_tool_schemas(), temperature=0.2)
        content = response.get("content", "")

        new_findings = list(findings)
        new_findings.append({
            "agent": "code_reader",
            "content": content,
            "timestamp": str(uuid.uuid4()),
        })

        evidence = list(state.get("evidence", []))
        tool_log = state.get("tool_log", [])
        task_id = state.get("task_id", "")

        for tc in tool_log[-15:]:
            tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
            if tc_dict.get("tool_name") in ("read_file", "search_code"):
                item = EvidenceItem(
                    evidence_id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.CODE_FILE,
                    source_path=tc_dict.get("params_json", ""),
                    content_hash=str(hash(tc_dict.get("result_summary", ""))),
                    excerpt=tc_dict.get("result_summary", "")[:500],
                    full_content_ref=tc_dict.get("params_json", ""),
                    agent_role="code_reader",
                    collected_by=AgentRole.CODE_READER,
                )
                item.confidence_score = self.confidence_calc.calculate(item)
                evidence.append(item.model_dump())

        result: dict = {
            "findings": new_findings,
            "evidence": evidence,
            "phase": TaskPhase.EXECUTING,
        }

        if self.project_index is not None:
            if hasattr(self.project_index, "model_dump"):
                result["project_index"] = self.project_index.model_dump()
            else:
                result["project_index"] = self.project_index

        return result


# Backward-compatible wrapper
async def code_reader_node(
    state: AgentState,
    llm_client: Any,
    project_index: Any = None,
    repo_path: str = "",
) -> dict:
    agent = CodeReaderAgent(llm_client, project_index=project_index, repo_path=repo_path)
    return await agent.execute(state)
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add src/agents/code_reader.py
git commit -m "refactor: CodeReaderAgent extends BaseAgent with confidence scoring

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: ExecutorAgent Refactor

**Files:**
- Modify: `src/agents/executor.py`

- [ ] **Step 1: Refactor executor.py**

```python
# src/agents/executor.py
from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from src.agents.base import BaseAgent, call_llm_with_tools
from src.evaluation.confidence import ConfidenceCalculator
from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.models.enums import AgentRole, SourceType, TaskPhase
from src.models.evidence import EvidenceItem
from src.tools.registry import get_tool_schemas

logger = structlog.get_logger(__name__)

EXECUTOR_SYSTEM_PROMPT = """You are a code executor and validator. Your job:
1. Run commands to verify hypotheses about the codebase
2. Execute Python snippets to test code behavior
3. Validate findings from the researcher and code reader

Available tools: run_command, run_python, read_file.

For each execution, note:
- The command/code that was run
- The output and what it means
- Whether it confirms or contradicts previous findings"""

EXECUTOR_CONTRACT = AgentContract(
    agent_role=AgentRole.EXECUTOR,
    description="Read-only verification: run static checks, execute analysis scripts, collect results. Do not modify repo.",
    input_schema=["task_spec", "findings"],
    output_schema=["findings", "evidence", "phase"],
    allowed_tools=["run_command", "run_python", "read_file"],
    forbidden_actions=["modify repository files", "install dependencies", "run unreviewed code"],
    failure_conditions=["command timeout > 30s", "non-zero exit code", "command not in whitelist"],
    fallback_behavior="Output raw command output without inference",
    quality_gate={},
)


class ExecutorAgent(BaseAgent):
    contract = EXECUTOR_CONTRACT

    def __init__(self, llm_client: Any, tool_registry: Any = None, repo_path: str = "") -> None:
        super().__init__(llm_client, tool_registry)
        self.repo_path = repo_path
        self.confidence_calc = ConfidenceCalculator()

    async def _run(self, state: AgentState) -> dict:
        query = ""
        if isinstance(state.get("task_spec"), dict):
            query = state["task_spec"].get("query", "")
        elif hasattr(state.get("task_spec"), "query"):
            query = getattr(state["task_spec"], "query", "")

        findings = state.get("findings", [])
        all_findings_text = json.dumps(findings[-8:], default=str) if findings else "None"

        user_msg = f"""Research Question: {query}
Repository path: {self.repo_path}
Accumulated findings: {all_findings_text}

Your job is to validate and verify the findings. Run commands or Python snippets to:
1. Verify project structure (e.g., list files, check dependencies)
2. Confirm API/function behavior
3. Validate any claims made by previous agents

Be specific about what you're testing and what the results mean."""

        messages = [
            {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        response = await call_llm_with_tools(self.llm_client, messages, get_tool_schemas(), temperature=0.1)
        content = response.get("content", "")

        new_findings = list(findings)
        new_findings.append({
            "agent": "executor",
            "content": content,
            "timestamp": str(uuid.uuid4()),
        })

        evidence = list(state.get("evidence", []))
        tool_log = state.get("tool_log", [])
        task_id = state.get("task_id", "")

        for tc in tool_log[-10:]:
            tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else tc
            if tc_dict.get("tool_name") in ("run_command", "run_python"):
                item = EvidenceItem(
                    evidence_id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.COMMAND_OUTPUT,
                    source_path=tc_dict.get("params_json", ""),
                    content_hash=str(hash(tc_dict.get("result_summary", ""))),
                    excerpt=tc_dict.get("result_summary", "")[:500],
                    full_content_ref=tc_dict.get("params_json", ""),
                    agent_role="executor",
                    collected_by=AgentRole.EXECUTOR,
                )
                item.confidence_score = self.confidence_calc.calculate(item)
                evidence.append(item.model_dump())

        return {
            "findings": new_findings,
            "evidence": evidence,
            "phase": TaskPhase.REVIEWING,
        }


# Backward-compatible wrapper
async def executor_node(state: AgentState, llm_client: Any, repo_path: str = "") -> dict:
    agent = ExecutorAgent(llm_client, repo_path=repo_path)
    return await agent.execute(state)
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add src/agents/executor.py
git commit -m "refactor: ExecutorAgent extends BaseAgent with confidence scoring

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: ReviewerAgent Refactor

**Files:**
- Modify: `src/agents/reviewer.py`

- [ ] **Step 1: Refactor reviewer.py**

```python
# src/agents/reviewer.py
from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.base import BaseAgent, call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.models.enums import AgentRole, TaskPhase

logger = structlog.get_logger(__name__)

REVIEWER_SYSTEM_PROMPT = """You are a quality reviewer for research analysis. Your job:
1. Review all findings, evidence, and analysis from previous agents
2. Assess completeness and accuracy
3. Assign a quality score from 0 to 1
4. Identify gaps or issues that need more investigation

Output a JSON object with:
- "score": float between 0 and 1 (0.6 = minimum acceptable quality)
- "summary": brief assessment
- "strengths": list of what was done well
- "gaps": list of issues or missing information
- "needs_retry": boolean (true if score < 0.6 and should retry)
- "suggestions": what the researcher should do on retry (if applicable)

Return ONLY valid JSON (no markdown code fences)."""

REVIEWER_CONTRACT = AgentContract(
    agent_role=AgentRole.REVIEWER,
    description="Quality auditor: detect hallucinations, check evidence coverage, identify logic conflicts, verify section completeness.",
    input_schema=["task_spec", "plan", "findings", "evidence"],
    output_schema=["review_score", "review_retries", "phase"],
    allowed_tools=["read_file", "search_code", "list_directory"],
    forbidden_actions=["generate new analysis conclusions", "modify upstream agent outputs"],
    failure_conditions=[],
    fallback_behavior="Always output review result; never fail silently",
    quality_gate={"min_review_score": 0.0},
)


class ReviewerAgent(BaseAgent):
    contract = REVIEWER_CONTRACT

    async def _run(self, state: AgentState) -> dict:
        query = ""
        if isinstance(state.get("task_spec"), dict):
            query = state["task_spec"].get("query", "")
        elif hasattr(state.get("task_spec"), "query"):
            query = getattr(state["task_spec"], "query", "")

        plan = state.get("plan", [])
        findings = state.get("findings", [])
        evidence = state.get("evidence", [])
        retries = state.get("review_retries", 0)

        # Include confidence summary in review input
        confidence_breakdown = {}
        for e in evidence[-30:]:
            if isinstance(e, dict):
                st = e.get("source_type", "unknown")
                cs = e.get("confidence_score")
                if st not in confidence_breakdown:
                    confidence_breakdown[st] = []
                if cs is not None:
                    confidence_breakdown[st].append(cs)

        confidence_summary = {}
        for st, scores in confidence_breakdown.items():
            if scores:
                confidence_summary[st] = {
                    "count": len(scores),
                    "avg": sum(scores) / len(scores),
                    "min": min(scores),
                    "low_confidence_count": sum(1 for s in scores if s < 0.5),
                }

        review_input = {
            "query": query,
            "plan": plan,
            "findings_count": len(findings),
            "evidence_count": len(evidence),
            "findings_summary": [f.get("content", "")[:300] for f in findings[-5:] if isinstance(f, dict)],
            "confidence_summary": confidence_summary,
            "max_retries": 2,
            "current_retry": retries,
        }

        user_msg = f"""Review Request:
{json.dumps(review_input, default=str, indent=2)}

Assess the quality of this research. Consider:
- Is the research question adequately answered?
- Is there enough evidence to support conclusions?
- Are there gaps in analysis?
- Is the code analysis thorough enough?
- Are there low-confidence evidence items requiring cross-validation?"""

        messages = [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        response = await call_llm_with_tools(self.llm_client, messages, tool_schemas=None, temperature=0.1)
        content = response.get("content", "")

        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            review = json.loads(cleaned)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("review_parse_failed", content=content[:200])
            review = {"score": 0.7, "summary": "Could not parse review", "strengths": [], "gaps": [], "needs_retry": False, "suggestions": ""}

        score = float(review.get("score", 0.7))
        score = max(0.0, min(1.0, score))
        needs_retry = review.get("needs_retry", False) or (score < 0.6 and retries < 2)
        new_retries = retries + 1

        logger.info("review_complete", score=score, needs_retry=needs_retry, retry=new_retries)

        new_findings = list(findings)
        new_findings.append({
            "agent": "reviewer",
            "content": json.dumps(review),
            "score": score,
            "timestamp": "",
        })

        result: dict = {
            "review_score": score,
            "review_retries": new_retries,
            "findings": new_findings,
        }

        if needs_retry and new_retries <= 2:
            result["phase"] = TaskPhase.RESEARCHING
        else:
            result["phase"] = TaskPhase.REPORTING

        return result


# Backward-compatible wrapper
async def reviewer_node(state: AgentState, llm_client: Any) -> dict:
    agent = ReviewerAgent(llm_client)
    return await agent.execute(state)
```

- [ ] **Step 2: Run reviewer tests**

Run: `pytest tests/test_agents.py::TestReviewer -v`
Expected: 2 PASS

- [ ] **Step 3: Commit**

```bash
git add src/agents/reviewer.py
git commit -m "refactor: ReviewerAgent extends BaseAgent with confidence-aware review

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: ReporterAgent Refactor

**Files:**
- Modify: `src/agents/reporter.py`

- [ ] **Step 1: Refactor reporter.py**

```python
# src/agents/reporter.py
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import structlog

from src.agents.base import BaseAgent, call_llm_with_tools
from src.models.agent_state import AgentState
from src.models.contract import AgentContract
from src.models.enums import AgentRole, TaskPhase
from src.models.report import AnalysisReport, Citation, ReportSection

logger = structlog.get_logger(__name__)

REPORTER_SYSTEM_PROMPT = """You are a technical report writer. Your job is to synthesize all research findings into a comprehensive analysis report.

The report must have at least 3 sections. Recommended sections include:
- Project Overview - summary from README and directory structure
- Tech Stack Identification - languages, frameworks, and tools discovered
- Core Architecture - module organization and key abstractions
- Key Code Paths - critical functions and call chains
- Business Logic / Data Flow - how data moves through the system
- Dependencies and Risks - external dependencies and potential issues
- Evidence Citations - all evidence items with source references

For every claim you make, cite the evidence by its evidence_id.

Output a JSON object with:
- "title": report title
- "summary": executive summary
- "sections": array of objects with "title", "content" (markdown), "order", "citations" (array of {"evidence_id": "...", "text": "..."})

Return ONLY valid JSON (no markdown code fences)."""

REPORTER_CONTRACT = AgentContract(
    agent_role=AgentRole.REPORTER,
    description="Report assembler: convert reviewed AgentState into structured report. No unsupported conclusions.",
    input_schema=["task_spec", "findings", "evidence"],
    output_schema=["final_report", "phase"],
    allowed_tools=["render_markdown", "export_html"],
    forbidden_actions=["generate conclusions without evidence citation", "omit reviewer-flagged issues"],
    failure_conditions=["fewer than 1 section"],
    fallback_behavior="Generate partial report with raw findings",
    quality_gate={"min_sections_gte": 1},
)


class ReporterAgent(BaseAgent):
    contract = REPORTER_CONTRACT

    async def _run(self, state: AgentState) -> dict:
        query = ""
        if isinstance(state.get("task_spec"), dict):
            query = state["task_spec"].get("query", "")
        elif hasattr(state.get("task_spec"), "query"):
            query = getattr(state["task_spec"], "query", "")

        findings = state.get("findings", [])
        evidence = state.get("evidence", [])
        project_index = state.get("project_index")
        score = state.get("review_score", 0.0)

        findings_text = ""
        for f in findings[-15:]:
            if isinstance(f, dict):
                agent = f.get("agent", "unknown")
                content = f.get("content", "")
                findings_text += f"\n[{agent}]: {content[:1000]}\n"

        # Sort evidence by confidence_score descending for the prompt
        evidence_summary = []
        sorted_evidence = sorted(
            evidence,
            key=lambda e: e.get("confidence_score", 0) if isinstance(e, dict) else 0,
            reverse=True,
        )
        for e in sorted_evidence[-20:]:
            if isinstance(e, dict):
                evidence_summary.append({
                    "id": e.get("evidence_id", ""),
                    "source": e.get("source_path", ""),
                    "type": str(e.get("source_type", "")),
                    "confidence": e.get("confidence_score"),
                })

        pi_summary = {}
        if project_index:
            if hasattr(project_index, "model_dump"):
                pi_summary = project_index.model_dump()
            elif isinstance(project_index, dict):
                pi_summary = project_index
            pi_summary = {
                "project": pi_summary.get("project_name", ""),
                "files": len(pi_summary.get("files", [])),
                "symbols": len(pi_summary.get("symbols", [])),
                "key_symbols": [s.get("name", "") for s in pi_summary.get("symbols", [])[:20]] if isinstance(pi_summary.get("symbols"), list) else [],
            }

        user_msg = f"""Research Question: {query}
Review Score: {score}

Project Index Summary: {json.dumps(pi_summary, default=str)}

All Findings:
{findings_text[:8000]}

Evidence Items ({len(evidence_summary)} total, sorted by confidence):
{json.dumps(evidence_summary, default=str, indent=2)[:4000]}

Please produce the final analysis report with at least 3 sections. Cite evidence items by their ID. Mark low-confidence conclusions (confidence < 0.5) with a warning prefix."""

        messages = [
            {"role": "system", "content": REPORTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        response = await call_llm_with_tools(self.llm_client, messages, tool_schemas=None, temperature=0.3)
        content = response.get("content", "")

        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            report_data = json.loads(cleaned)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("report_parse_failed", content=content[:300])
            report_data = {
                "title": f"Analysis: {query[:100]}",
                "summary": "Report generation encountered issues. See findings for raw analysis.",
                "sections": [
                    {"title": "Project Overview", "content": findings_text[:2000], "order": 1, "citations": []},
                ],
            }

        sections: list[ReportSection] = []
        for i, sec in enumerate(report_data.get("sections", []), 1):
            citations: list[Citation] = []
            for c in sec.get("citations", []):
                citations.append(Citation(
                    evidence_id=c.get("evidence_id", ""),
                    text=c.get("text", ""),
                    source_path=c.get("source_path", ""),
                ))
            sections.append(ReportSection(
                section_id=f"sec_{i}",
                title=sec.get("title", f"Section {i}"),
                content=sec.get("content", ""),
                order=sec.get("order", i),
                citations=citations,
            ))

        report = AnalysisReport(
            report_id=uuid.uuid4().hex,
            task_id=state.get("task_id", ""),
            title=report_data.get("title", f"Analysis Report"),
            summary=report_data.get("summary", ""),
            sections=sections,
            generated_at=datetime.utcnow(),
            review_score=score,
            total_evidence_items=len(evidence),
        )

        logger.info("report_generated", report_id=report.report_id, sections=len(sections))

        return {
            "final_report": report.model_dump(),
            "phase": TaskPhase.COMPLETED,
        }


# Backward-compatible wrapper
async def reporter_node(state: AgentState, llm_client: Any) -> dict:
    agent = ReporterAgent(llm_client)
    return await agent.execute(state)
```

- [ ] **Step 2: Run reporter tests**

Run: `pytest tests/test_agents.py::TestReporter -v`
Expected: 1 PASS

- [ ] **Step 3: Commit**

```bash
git add src/agents/reporter.py
git commit -m "refactor: ReporterAgent extends BaseAgent with confidence-sorted evidence

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 11: Workflow Graph + Executor Adaptation

**Files:**
- Modify: `src/workflow/graph.py`
- Modify: `src/workflow/executor.py`

- [ ] **Step 1: Update graph.py to use agent instances**

The key change: factory functions now create agent instances and use `agent.execute` as the node function. This is a minimal, surgical change:

```python
# src/workflow/graph.py — replace the factory functions section (lines 82-128)

def _make_planner(llm_client: Any):
    from src.agents.planner import PlannerAgent
    agent = PlannerAgent(llm_client)

    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await agent.execute(state)
    return node


def _make_researcher(llm_client: Any, rag_pipeline: Any = None):
    from src.agents.researcher import ResearcherAgent
    agent = ResearcherAgent(llm_client, rag_pipeline=rag_pipeline)

    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await agent.execute(state)
    return node


def _make_code_reader(llm_client: Any, project_index: Any = None, repo_path: str = ""):
    from src.agents.code_reader import CodeReaderAgent
    agent = CodeReaderAgent(llm_client, project_index=project_index, repo_path=repo_path)

    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await agent.execute(state)
    return node


def _make_executor(llm_client: Any, repo_path: str = ""):
    from src.agents.executor import ExecutorAgent
    agent = ExecutorAgent(llm_client, repo_path=repo_path)

    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await agent.execute(state)
    return node


def _make_reviewer(llm_client: Any):
    from src.agents.reviewer import ReviewerAgent
    agent = ReviewerAgent(llm_client)

    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await agent.execute(state)
    return node


def _make_reporter(llm_client: Any):
    from src.agents.reporter import ReporterAgent
    agent = ReporterAgent(llm_client)

    @_wrap_node
    async def node(state: AgentState) -> dict:
        return await agent.execute(state)
    return node
```

Also remove the old imports at the top of graph.py:
```python
# Remove these lines:
from src.agents.code_reader import code_reader_node
from src.agents.executor import executor_node
from src.agents.planner import planner_node
from src.agents.reporter import reporter_node
from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
```

- [ ] **Step 2: Run workflow tests**

Run: `pytest tests/test_workflow.py -v`
Expected: All workflow tests pass (graph construction is tested, compilation works)

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/workflow/graph.py
git commit -m "refactor: wire graph.py to use BaseAgent.execute instead of raw node functions

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 12: Update Conftest and Test Compatibility

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add mock_tool_registry fixture to conftest.py**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def mock_tool_registry():
    """Mock tool registry returning common tool schemas."""
    registry = MagicMock()
    registry.get_schemas.return_value = [
        {"type": "function", "function": {"name": "read_file", "description": "Read a file"}},
        {"type": "function", "function": {"name": "search_code", "description": "Search code"}},
        {"type": "function", "function": {"name": "run_command", "description": "Run a command"}},
    ]
    return registry
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add mock_tool_registry fixture for agent tests

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 13: Demo End-to-End Validation

**Files:**
- None modified (verification only)

- [ ] **Step 1: Run demo with mock LLM (verify startup path works)**

Run: `python -c "from src.agents.planner import PlannerAgent; from src.models.contract import AgentContract; print('Import OK'); print('PlannerAgent contract:', PlannerAgent.contract.agent_role.value)"`
Expected: Import OK + "PlannerAgent contract: planner"

- [ ] **Step 2: Run full test suite one final time**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Verify all contracts are defined for each agent**

Run: `python -c "
from src.agents.planner import PlannerAgent
from src.agents.researcher import ResearcherAgent
from src.agents.code_reader import CodeReaderAgent
from src.agents.executor import ExecutorAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.reporter import ReporterAgent
agents = [PlannerAgent, ResearcherAgent, CodeReaderAgent, ExecutorAgent, ReviewerAgent, ReporterAgent]
for a in agents:
    c = a.contract
    print(f'{c.agent_role.value}: tools={c.allowed_tools}, input={c.input_schema}, output={c.output_schema}')
print('All contracts defined.')
"`

Expected: Prints contracts for all 6 agents

- [ ] **Step 4: Verify ConfidenceCalculator with all source types**

Run: `python -c "
from src.evaluation.confidence import ConfidenceCalculator
from src.models.evidence import EvidenceItem
from src.models.enums import SourceType
calc = ConfidenceCalculator()
for st in SourceType:
    item = EvidenceItem(
        evidence_id='test', task_id='t1', source_type=st,
        source_path='test', content_hash='abc', excerpt='test',
        full_content_ref='test', line_range=(1,5), corroboration_count=2)
    score = calc.calculate(item)
    print(f'{st.value}: {score:.4f}')
print('All source types scored.')
"`

Expected: Prints scores for all 6 source types

- [ ] **Step 5: Final commit (if any documentation or fixups needed)**

```bash
git add -A
git diff --cached --stat
# Only commit if there are actual changes
```
```

---

### Task 14: Contracts File for Each Agent (Clean JSON Definitions)

**Files:**
- Create: `src/agents/contracts/__init__.py`
- Create: `src/agents/contracts/planner.json`
- Create: `src/agents/contracts/researcher.json`
- Create: `src/agents/contracts/code_reader.json`
- Create: `src/agents/contracts/executor.json`
- Create: `src/agents/contracts/reviewer.json`
- Create: `src/agents/contracts/reporter.json`

Each JSON file is optional — contracts are already defined in Python. These JSON files serve as human-readable documentation and could be used for dynamic loading later.

- [ ] **Step 1: Create contracts directory and files**

```bash
mkdir -p src/agents/contracts
```

Create `src/agents/contracts/__init__.py`:
```python
# Agent contract definitions (human-readable JSON + Python model)
```

Create `src/agents/contracts/planner.json`:
```json
{
  "agent_role": "planner",
  "description": "Parse research questions and produce step-by-step plans. Do not analyze code or draw conclusions.",
  "input_schema": ["task_spec"],
  "output_schema": ["plan", "phase"],
  "allowed_tools": ["read_file", "list_directory"],
  "forbidden_actions": ["analyze source code logic", "infer architecture conclusions", "search the web"],
  "failure_conditions": ["plan is empty", "plan step is not executable"],
  "fallback_behavior": "Produce a default single-step plan",
  "quality_gate": {"min_plan": 1}
}
```

Create the remaining 5 JSON files with corresponding contract data (same content as the Python CONTRACT objects in each agent file).

- [ ] **Step 2: Commit**

```bash
git add src/agents/contracts/
git commit -m "feat: add human-readable contract JSON definitions for all 6 agents

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Verification Checklist

After all tasks complete, verify:

- [ ] `pytest tests/ -v` — all tests pass
- [ ] Every agent has an `AgentContract` as a class attribute
- [ ] `ConfidenceCalculator.calculate()` returns values in [0.05, 0.95] for all SourceType values
- [ ] `EvidenceItem` has all 6 new fields with correct defaults
- [ ] `BaseAgent.execute()` runs validation pipeline without blocking
- [ ] Backward-compatible `*_node()` wrappers work for all 6 agents
- [ ] Workflow graph compiles and routes correctly
