"""Pattern Aggregation's own Pipeline Definition.

Registers Pattern Aggregation against the existing, real, unmodified
`runtime.pipeline.engine.PipelineEngine`, mirroring
`evidence.pipeline.register_evidence_pipeline`'s own registration shape
field for field (Pattern Aggregation Engine Architecture Specification
v1.0 §12).

One stage, bound to `aggregation.module`'s one registered capability. The
Pipeline Engine resolves that capability through the Container rather
than calling `aggregation.engine.aggregate_patterns` directly -- see
`tests/aggregation/test_pipeline.py`'s own sentinel test, which replaces
the registered stage and asserts the run's output changes accordingly.

No `rollback_capability` is set. Aggregation is read-only: it consumes an
already-persisted `EvidenceSet` held in memory, writes nothing, and
mutates nothing -- so there is no side effect to compensate. A deliberate
omission, matching every sibling engine's identical decision.
"""

from __future__ import annotations

from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition

from aggregation.module import CAPABILITY_AGGREGATE_PATTERNS

AGGREGATION_PATTERN_PIPELINE = PipelineDefinition(
    name="aggregation.patterns",
    stages=(StageDefinition(name="aggregate_patterns", capability=CAPABILITY_AGGREGATE_PATTERNS),),
)


def register_aggregation_pipeline(engine: PipelineEngine) -> None:
    """Registers Pattern Aggregation's Pipeline Definition against
    `engine`. Must be called only after an `AggregationModule` has already
    run `init()` against the same engine's own `Container`, mirroring
    `register_evidence_pipeline`'s identical precondition.
    """

    engine.register(AGGREGATION_PATTERN_PIPELINE)
