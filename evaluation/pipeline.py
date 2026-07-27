"""Architecture Evaluation's own Pipeline Definition.

Registers Architecture Evaluation's three stages against the existing,
real, unmodified `runtime.pipeline.engine.PipelineEngine`, mirroring
`synthesis.pipeline.register_synthesis_pipeline`'s own registration shape
field for field (Architecture Evaluation Engine Specification v1.0 §6).

No `rollback_capability` is set on any stage — every stage is read-only
(and, unlike Discovery/Synthesis, touches no filesystem at all), so there
is nothing to compensate.
"""

from __future__ import annotations

from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition

from evaluation.module import (
    CAPABILITY_ASSEMBLE_EVALUATION,
    CAPABILITY_EXECUTE_RULES,
    CAPABILITY_INDEX_FACTS,
)

EVALUATION_ARCHITECTURE_PIPELINE = PipelineDefinition(
    name="evaluation.architecture",
    stages=(
        StageDefinition(name="index_facts", capability=CAPABILITY_INDEX_FACTS),
        StageDefinition(name="execute_rules", capability=CAPABILITY_EXECUTE_RULES),
        StageDefinition(name="assemble_evaluation", capability=CAPABILITY_ASSEMBLE_EVALUATION),
    ),
)


def register_evaluation_pipeline(engine: PipelineEngine) -> None:
    """Registers Architecture Evaluation's Pipeline Definition against
    `engine`. Must be called only after an `EvaluationModule` has already
    run `init()` against the same engine's own `Container`, mirroring
    `register_synthesis_pipeline`'s identical precondition.
    """

    engine.register(EVALUATION_ARCHITECTURE_PIPELINE)
