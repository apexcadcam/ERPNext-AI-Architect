"""The two Pipeline Definitions Sprint 2 registers, per
docs/runtime/PIPELINE_ENGINE.md §4's table.

`knowledge.validation` is registered in full — all eight gates, in their
KNOWLEDGE_VALIDATION_SPEC.md §0 fixed order.

`knowledge.graph_build` is registered with three of its four frozen
stages — Extraction, Pattern Extraction, Conflict Resolution — per
SPRINT2_IMPLEMENTATION_PLAN.md §2's explicit scope decision: Graph
Node/Edge Materialization is deferred to whichever future Sprint builds the
Knowledge Graph module. This is a Sprint 2 deviation from "register the
Pipeline Definition exactly as specified," flagged (not hidden) in that
plan's §8 Risks and repeated here at the point where it's actually visible.

Neither definition is data the Pipeline Engine executes on its own —
`register_knowledge_pipelines()` must be called with a `PipelineEngine`
whose `Container` already has every capability below resolvable (i.e. both
`ExtractorModule` and `ValidatorModule` have already run `init()`).
"""

from __future__ import annotations

from knowledge.extraction.module import (
    CAPABILITY_EXTRACT,
    CAPABILITY_EXTRACT_PATTERNS,
    CAPABILITY_RESOLVE_CONFLICTS_BATCH,
)
from knowledge.validation.module import (
    CAPABILITY_CONFIDENCE_SCORE,
    CAPABILITY_DUPLICATE,
    CAPABILITY_ENGINEERING_REVIEW,
    CAPABILITY_HUMAN_APPROVAL,
    CAPABILITY_SCHEMA,
    CAPABILITY_SOURCE_VERIFY,
    CAPABILITY_TRUST_VERIFY,
    CAPABILITY_VERSION_CONFLICT,
)
from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition

KNOWLEDGE_VALIDATION_PIPELINE = PipelineDefinition(
    name="knowledge.validation",
    stages=(
        StageDefinition(name="schema_validation", capability=CAPABILITY_SCHEMA),
        StageDefinition(name="duplicate_detection", capability=CAPABILITY_DUPLICATE),
        StageDefinition(name="version_conflict_detection", capability=CAPABILITY_VERSION_CONFLICT),
        StageDefinition(name="source_verification", capability=CAPABILITY_SOURCE_VERIFY),
        StageDefinition(name="trust_verification", capability=CAPABILITY_TRUST_VERIFY),
        StageDefinition(name="engineering_review", capability=CAPABILITY_ENGINEERING_REVIEW),
        StageDefinition(name="human_approval_gate", capability=CAPABILITY_HUMAN_APPROVAL),
        StageDefinition(name="confidence_scoring", capability=CAPABILITY_CONFIDENCE_SCORE),
    ),
)

KNOWLEDGE_GRAPH_BUILD_PIPELINE = PipelineDefinition(
    name="knowledge.graph_build",
    stages=(
        StageDefinition(name="extraction", capability=CAPABILITY_EXTRACT),
        StageDefinition(name="pattern_extraction", capability=CAPABILITY_EXTRACT_PATTERNS),
        StageDefinition(name="conflict_resolution", capability=CAPABILITY_RESOLVE_CONFLICTS_BATCH),
    ),
)


def register_knowledge_pipelines(engine: PipelineEngine) -> None:
    """Registers both Pipeline Definitions against `engine`. Idempotent per
    engine instance is not guaranteed — `PipelineEngine.register()` raises
    if a name is already registered, the same discipline every other
    registration in this Runtime already follows.
    """

    engine.register(KNOWLEDGE_VALIDATION_PIPELINE)
    engine.register(KNOWLEDGE_GRAPH_BUILD_PIPELINE)
