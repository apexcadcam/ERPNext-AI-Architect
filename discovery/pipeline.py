"""Repository Discovery's own Pipeline Definition.

Registers Repository Discovery's four stages against the existing, real,
unmodified `runtime.pipeline.engine.PipelineEngine`, mirroring
`knowledge/pipelines/definitions.py:register_knowledge_pipelines` field
for field (Repository Discovery Engine Specification v1.1 §5).

No `rollback_capability` is set on any stage — every stage is read-only,
so there is nothing to compensate (§6, "Recovery behavior": a deliberate
omission, not an oversight).
"""

from __future__ import annotations

from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition

from discovery.module import (
    CAPABILITY_ASSEMBLE_INVENTORY,
    CAPABILITY_CLASSIFY_ENTRIES,
    CAPABILITY_RESOLVE_ROOT,
    CAPABILITY_WALK_TREE,
)

DISCOVERY_REPOSITORY_PIPELINE = PipelineDefinition(
    name="discovery.repository",
    stages=(
        StageDefinition(name="resolve_root", capability=CAPABILITY_RESOLVE_ROOT),
        StageDefinition(name="walk_tree", capability=CAPABILITY_WALK_TREE),
        StageDefinition(name="classify_entries", capability=CAPABILITY_CLASSIFY_ENTRIES),
        StageDefinition(name="assemble_inventory", capability=CAPABILITY_ASSEMBLE_INVENTORY),
    ),
)


def register_discovery_pipeline(engine: PipelineEngine) -> None:
    """Registers Repository Discovery's Pipeline Definition against
    `engine`. Must be called only after a `DiscoveryModule` has already
    run `init()` against the same engine's own `Container`, mirroring
    `register_knowledge_pipelines`'s identical precondition.
    """

    engine.register(DISCOVERY_REPOSITORY_PIPELINE)
