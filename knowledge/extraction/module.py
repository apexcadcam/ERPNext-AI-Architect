"""The Extractor module — Extraction, Pattern Extraction, and (see below)
Conflict Resolution as a Runtime Module.

Implements docs/runtime/MODULE_SYSTEM.md's contract for the domain module
docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md specifies. Provides
`knowledge.extract` and `knowledge.extract_patterns`, the first two stage
capabilities the `knowledge.graph_build` PipelineDefinition binds to
(knowledge/pipelines/definitions.py).

Also provides `knowledge.resolve_conflicts_batch`, graph_build's third
in-scope stage. `docs/runtime/MODULE_SYSTEM.md §5`'s domain-module table
names no "Conflict Resolution" module — Extraction and Pattern Extraction
already own the first two stages of this same Pipeline Definition, so this
Sprint assigns the third to the same module rather than inventing a new one
for a single stage; this is a Sprint 2 implementation decision, not
something the frozen architecture states explicitly.
"""

from __future__ import annotations

from functools import partial

from knowledge.conflict.providers import PRECEDENCE_PROVIDER_CAPABILITY, PrecedenceProvider
from knowledge.conflict.stage import resolve_conflicts_in_batch
from knowledge.extraction.ids import IdAllocator
from knowledge.extraction.pattern_extraction import extract_patterns
from knowledge.extraction.stage import extract
from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module

#: Registered by whatever assembles the Runtime, not by this module —
#: optional, same convention as knowledge/validation/module.py.
EVENT_BUS_CAPABILITY = "runtime.event_bus"

CAPABILITY_EXTRACT = "knowledge.extract"
CAPABILITY_EXTRACT_PATTERNS = "knowledge.extract_patterns"
CAPABILITY_RESOLVE_CONFLICTS_BATCH = "knowledge.resolve_conflicts_batch"


class ExtractorModule(Module):
    """Provides `knowledge.extract`, `knowledge.extract_patterns`, and
    `knowledge.resolve_conflicts_batch`.
    """

    #: Shared with ValidatorModule — see knowledge/conflict/providers.py.
    PRECEDENCE_PROVIDER_CAPABILITY = PRECEDENCE_PROVIDER_CAPABILITY

    def init(self, container: Container) -> None:
        id_allocator = IdAllocator()
        precedence_provider: PrecedenceProvider = container.resolve(self.PRECEDENCE_PROVIDER_CAPABILITY)
        event_bus = (
            container.resolve(EVENT_BUS_CAPABILITY) if container.is_registered(EVENT_BUS_CAPABILITY) else None
        )

        container.register(
            CAPABILITY_EXTRACT,
            lambda: partial(extract, id_allocator=id_allocator, event_bus=event_bus),
            override=True,
        )
        container.register(
            CAPABILITY_EXTRACT_PATTERNS,
            lambda: partial(extract_patterns, id_allocator=id_allocator, event_bus=event_bus),
            override=True,
        )
        container.register(
            CAPABILITY_RESOLVE_CONFLICTS_BATCH,
            lambda: partial(resolve_conflicts_in_batch, precedence_provider=precedence_provider),
            override=True,
        )

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="extractor ready")
