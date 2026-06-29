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

    # Source types where line_range is semantically meaningful.
    # The no-line-range decay only applies to these.
    _LINE_RANGE_SOURCE_TYPES: set[SourceType] = {
        SourceType.CODE_FILE,
        SourceType.DOCUMENT,
        SourceType.GITHUB_REPO,
        SourceType.RAG_CHUNK,
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
        if evidence.line_range is None and evidence.source_type in self._LINE_RANGE_SOURCE_TYPES:
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
