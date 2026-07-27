"""Requirement Synthesis's own Pipeline Definition.

Registers Requirement Synthesis's eight stages against the existing, real,
unmodified `runtime.pipeline.engine.PipelineEngine`, mirroring
`discovery.pipeline.register_discovery_pipeline`'s own registration shape
field for field (Requirement Synthesis Engine Specification v1.1 §6).

No `rollback_capability` is set on any stage — every stage is read-only,
so there is nothing to compensate (§7, "Recovery": a deliberate omission,
not an oversight).
"""

from __future__ import annotations

from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition

from synthesis.module import (
    CAPABILITY_ASSEMBLE_FACTS,
    CAPABILITY_EXTRACT_APIS,
    CAPABILITY_EXTRACT_COMPONENTS,
    CAPABILITY_EXTRACT_DEPENDENCIES,
    CAPABILITY_EXTRACT_HOOKS,
    CAPABILITY_IDENTIFY_MODULES,
    CAPABILITY_PARTITION_INVENTORY,
    CAPABILITY_RESOLVE_CONNECTOR,
)

SYNTHESIS_REPOSITORY_FACTS_PIPELINE = PipelineDefinition(
    name="synthesis.repository_facts",
    stages=(
        StageDefinition(name="partition_inventory", capability=CAPABILITY_PARTITION_INVENTORY),
        StageDefinition(name="identify_modules", capability=CAPABILITY_IDENTIFY_MODULES),
        StageDefinition(name="resolve_connector", capability=CAPABILITY_RESOLVE_CONNECTOR),
        StageDefinition(name="extract_hooks", capability=CAPABILITY_EXTRACT_HOOKS),
        StageDefinition(name="extract_components", capability=CAPABILITY_EXTRACT_COMPONENTS),
        StageDefinition(name="extract_apis", capability=CAPABILITY_EXTRACT_APIS),
        StageDefinition(name="extract_dependencies", capability=CAPABILITY_EXTRACT_DEPENDENCIES),
        StageDefinition(name="assemble_facts", capability=CAPABILITY_ASSEMBLE_FACTS),
    ),
)


def register_synthesis_pipeline(engine: PipelineEngine) -> None:
    """Registers Requirement Synthesis's Pipeline Definition against
    `engine`. Must be called only after a `SynthesisModule` has already
    run `init()` against the same engine's own `Container`, mirroring
    `register_discovery_pipeline`'s identical precondition.
    """

    engine.register(SYNTHESIS_REPOSITORY_FACTS_PIPELINE)
