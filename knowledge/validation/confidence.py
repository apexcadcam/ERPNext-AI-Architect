"""Confidence Scoring: KNOWLEDGE_VALIDATION_SPEC.md §8's formula.

Split out from gates.py because both the Confidence Scoring gate itself
(§8, last in the fixed order) and the Human Approval Gate (§7, condition 4:
"confidence score falls in the ambiguous band (0.4-0.6)") need the identical
computation — §7 runs before §8 in the fixed stage order, so a shared, pure
function is what lets §7 preview the score §8 will later persist, without
either gate duplicating the formula or violating the fixed ordering.
"""

from __future__ import annotations

from knowledge.artifacts import ContentArtifact
from knowledge.validation.providers import TrustScoreProvider

#: KNOWLEDGE_VALIDATION_SPEC.md §8's worked examples: a Knowledge API parsed
#: directly from source is mechanically certain; less structured extraction
#: methods are progressively less certain.
_EXTRACTION_CONFIDENCE_BY_METHOD: dict[str, float] = {
    "source_code": 1.0,
    "official_documentation": 0.85,
    "merged_pull_request": 0.9,
    "video_transcript": 0.6,
    "forum_reply": 0.65,
}
_DEFAULT_EXTRACTION_CONFIDENCE = 0.75

#: KNOWLEDGE_VALIDATION_SPEC.md §8: capped at 1.3, increasing with each
#: additional independent corroborating source.
_MAX_CORROBORATION_MULTIPLIER = 1.3
_CORROBORATION_STEP = 0.1


def extraction_confidence(artifact: ContentArtifact) -> float:
    """How mechanically certain the extraction method was, per §8."""

    return _EXTRACTION_CONFIDENCE_BY_METHOD.get(
        artifact.metadata.extraction_method, _DEFAULT_EXTRACTION_CONFIDENCE
    )


def corroboration_multiplier(artifact: ContentArtifact) -> float:
    """1.0 for a single source, increasing (capped at 1.3) per additional
    independent `source_references` entry.
    """

    independent_sources = max(1, len(artifact.source_references))
    return min(_MAX_CORROBORATION_MULTIPLIER, 1.0 + _CORROBORATION_STEP * (independent_sources - 1))


def compute_confidence(
    trust_score: int,
    extraction_confidence_value: float,
    corroboration_multiplier_value: float,
    recency_factor: float = 1.0,
) -> float:
    """KNOWLEDGE_VALIDATION_SPEC.md §8's formula, clamped to [0.0, 1.0]."""

    source_trust_normalized = trust_score / 100
    raw = (
        source_trust_normalized
        * extraction_confidence_value
        * corroboration_multiplier_value
        * recency_factor
    )
    return max(0.0, min(1.0, raw))


def compute_confidence_for_artifact(
    artifact: ContentArtifact, trust_score_provider: TrustScoreProvider
) -> float:
    """Convenience wrapper deriving every §8 factor from `artifact` itself,
    plus the injected Trust Score. `recency_factor` defaults to 1.0 — Sprint
    2 has no live current-version registry to compare `version.applies_to`
    against, per SPRINT2_IMPLEMENTATION_PLAN.md §8's Source/Trust Verification
    risk note applied identically here.
    """

    return compute_confidence(
        trust_score=trust_score_provider.trust_score(artifact),
        extraction_confidence_value=extraction_confidence(artifact),
        corroboration_multiplier_value=corroboration_multiplier(artifact),
        recency_factor=1.0,
    )
