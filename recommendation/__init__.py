"""Recommendation Engine — implements the Recommendation Engine
Architecture Specification v1.0 in full: given an already-produced
`evaluation.contract.ArchitectureEvaluation`, groups related findings,
computes a deterministic priority, and produces one self-contained
`RecommendationSet` artifact. Zero Reasoning Engine calls anywhere in this
package -- see `recommendation.scoring`'s own module docstring for why
none are needed.

This package touches no filesystem and imports no connector -- every
computation operates on `ArchitectureEvaluation` already in memory.
Depends only on `evaluation.contract` (for `ArchitectureEvaluation` and
its `Finding`/`Severity`/`Confidence`/`Evidence` types) and
`runtime.pipeline.engine`/`runtime.modules.base`/`runtime.modules.manifest`/
`runtime.container.di`. Nothing in this package imports `discovery/`,
`synthesis/`, `analysis/`, `knowledge/`, `intelligence/`, `planning/`,
`execution/`, `orchestration/`, or `composition_root/`.
"""

from __future__ import annotations

from recommendation.contract import (
    CategoryImpactSpec,
    Priority,
    PriorityWeightSpec,
    Recommendation,
    RecommendationRequest,
    RecommendationSet,
    RecommendationStatistics,
    SkippedGrouping,
)
from recommendation.engine import generate_recommendations
from recommendation.errors import RecommendationError_

__all__ = [
    "CategoryImpactSpec",
    "Priority",
    "PriorityWeightSpec",
    "Recommendation",
    "RecommendationError_",
    "RecommendationRequest",
    "RecommendationSet",
    "RecommendationStatistics",
    "SkippedGrouping",
    "generate_recommendations",
]
