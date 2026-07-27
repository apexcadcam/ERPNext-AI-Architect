"""Recommendation Engine's own contract: the one fixed set of types every
stage produces and consumes, and the final `RecommendationSet` artifact
callers receive.

Implements Recommendation Engine Architecture Specification v1.0 §3 and
§4 in full. Every model is frozen, matching every other contract in this
project (`evaluation.contract.ArchitectureEvaluation`,
`synthesis.contract.RepositoryFacts`, ...).
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field

from evaluation.contract import ArchitectureEvaluation, Evidence


class Priority(str, enum.Enum):
    """§4's closed priority vocabulary. Deliberately shaped like
    `evaluation.contract.Severity` but a distinct concept: `Severity`
    describes a finding's own weight; `Priority` describes this engine's
    computed action-ordering (§6) -- the two can and do diverge.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(BaseModel):
    """§4's final per-recommendation artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    priority: Priority
    priority_score: float
    rationale: str = Field(min_length=1)
    supporting_findings: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    affected_files: tuple[str, ...]
    affected_modules: tuple[str, ...]
    conflicts_with: tuple[str, ...] = ()


class SkippedGrouping(BaseModel):
    """One category whose grouping step failed unexpectedly -- caught and
    recorded rather than aborting the whole run (§7).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RecommendationStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings_considered: int = Field(ge=0)
    recommendations_produced: int = Field(ge=0)
    groupings_skipped: int = Field(ge=0)
    recommendations_by_priority: dict[Priority, int]
    conflicts_detected: int = Field(ge=0)


class RecommendationRequest(BaseModel):
    """§3's Input. Wraps an already-produced `ArchitectureEvaluation` --
    this engine never inspects repositories, parses source, or produces
    new findings.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    architecture_evaluation: ArchitectureEvaluation
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)


class RecommendationSet(BaseModel):
    """§3's final artifact -- the one thing `generate_recommendations()`
    returns. Determinism (§3): two runs against byte-for-byte identical
    `ArchitectureEvaluation` produce an identical `RecommendationSet` in
    every field except `recommendation_set_id`, `generated_at`, and each
    `Recommendation.recommendation_id`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_set_id: str = Field(min_length=1)
    source_evaluation_id: str = Field(min_length=1)
    repository_root: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    recommendations: tuple[Recommendation, ...]
    skipped_groupings: tuple[SkippedGrouping, ...]
    statistics: RecommendationStatistics


class PriorityWeightSpec(BaseModel):
    """One named, documented scoring weight -- the Rule Metadata Registry
    pattern from the Threshold Documentation & Rule Metadata Addendum,
    applied here identically (§6). `recommendation.scoring` reads every
    weight by name from `recommendation.scoring.PRIORITY_WEIGHTS` rather
    than embedding a magic number in its algorithm.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    weight_name: str = Field(min_length=1)
    value: float
    calibration_status: str = Field(min_length=1)  # "empirical" | "heuristic_default"
    justification: str = Field(min_length=1)


class CategoryImpactSpec(BaseModel):
    """One named, documented category-impact weight (§6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str = Field(min_length=1)
    impact_weight: float
    calibration_status: str = Field(min_length=1)
    justification: str = Field(min_length=1)
