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
