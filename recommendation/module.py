"""The Recommendation module — Runtime-facing host for Recommendation
Engine's three pipeline stages.

Implements Recommendation Engine Architecture Specification v1.0 §7, §8,
§9's three-stage shape as a `runtime.modules.base.Module`. Like
`DiscoveryModule`/`SynthesisModule`/`EvaluationModule`, `init()` calls zero
`container.resolve(...)`: every stage function is pure and self-contained
(`recommendation.scoring` / `recommendation.engine`), operating only on the
`ArchitectureEvaluation` already present in its own input —
`capabilities_required` is empty.

Each stage wrapper below delegates to the exact same package-internal
functions `recommendation.engine.generate_recommendations()` itself
composes — no duplicated stage logic between the plain-function interface
and the Pipeline-Engine-driven one.
"""

from __future__ import annotations

from typing import Any

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.pipeline.engine import PipelineContext, StageOutcome

from recommendation.contract import RecommendationRequest
from recommendation.engine import assemble_recommendation_set, build_recommendations
from recommendation.scoring import group_findings

#: The three Container capabilities this module provides — one per
#: Recommendation Engine stage, matching `recommendation.pipeline`'s own
#: `StageDefinition.capability` bindings exactly.
CAPABILITY_GROUP_FINDINGS = "recommendation.group_findings"
CAPABILITY_BUILD_RECOMMENDATIONS = "recommendation.build_recommendations"
CAPABILITY_ASSEMBLE_RECOMMENDATION_SET = "recommendation.assemble_recommendation_set"


def _group_findings_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request: RecommendationRequest = data
    groups, skipped_groupings = group_findings(request.architecture_evaluation.findings)
    return (request, groups, skipped_groupings), StageOutcome.SUCCESS


def _build_recommendations_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, groups, skipped_groupings = data
    recommendations = build_recommendations(groups)
    return (request, recommendations, skipped_groupings), StageOutcome.SUCCESS


def _assemble_recommendation_set_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, recommendations, skipped_groupings = data
    recommendation_set = assemble_recommendation_set(request, recommendations, skipped_groupings)
    return recommendation_set, StageOutcome.SUCCESS


class RecommendationModule(Module):
    """Provides the three Recommendation Engine stage capabilities.
    Requires nothing — see this module's own docstring.
    """

    def init(self, container: Container) -> None:
        container.register(CAPABILITY_GROUP_FINDINGS, lambda: _group_findings_stage)
        container.register(CAPABILITY_BUILD_RECOMMENDATIONS, lambda: _build_recommendations_stage)
        container.register(CAPABILITY_ASSEMBLE_RECOMMENDATION_SET, lambda: _assemble_recommendation_set_stage)

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="Recommendation stages ready")
