"""Recommendation Engine's own Pipeline Definition.

Registers Recommendation Engine's three stages against the existing, real,
unmodified `runtime.pipeline.engine.PipelineEngine`, mirroring
`evaluation.pipeline.register_evaluation_pipeline`'s own registration shape
field for field (Recommendation Engine Architecture Specification v1.0
§7, §8, §9).

No `rollback_capability` is set on any stage — every stage is read-only
and touches no filesystem, so there is nothing to compensate.
"""

from __future__ import annotations

from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition

from recommendation.module import (
    CAPABILITY_ASSEMBLE_RECOMMENDATION_SET,
    CAPABILITY_BUILD_RECOMMENDATIONS,
    CAPABILITY_GROUP_FINDINGS,
)

RECOMMENDATION_ENGINE_PIPELINE = PipelineDefinition(
    name="recommendation.engine",
    stages=(
        StageDefinition(name="group_findings", capability=CAPABILITY_GROUP_FINDINGS),
        StageDefinition(name="build_recommendations", capability=CAPABILITY_BUILD_RECOMMENDATIONS),
        StageDefinition(
            name="assemble_recommendation_set", capability=CAPABILITY_ASSEMBLE_RECOMMENDATION_SET
        ),
    ),
)


def register_recommendation_pipeline(engine: PipelineEngine) -> None:
    """Registers Recommendation Engine's Pipeline Definition against
    `engine`. Must be called only after a `RecommendationModule` has
    already run `init()` against the same engine's own `Container`,
    mirroring `register_evaluation_pipeline`'s identical precondition.
    """

    engine.register(RECOMMENDATION_ENGINE_PIPELINE)
