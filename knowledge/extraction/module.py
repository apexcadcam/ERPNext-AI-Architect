"""The Extractor module — Extraction and Pattern Extraction as a Runtime
Module.

Implements docs/runtime/MODULE_SYSTEM.md's contract for the domain module
docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md specifies. Provides
`knowledge.extract` and `knowledge.extract_patterns`, the two stage
capabilities the `knowledge.graph_build` PipelineDefinition's first two
stages bind to (knowledge/pipelines/definitions.py).
"""

from __future__ import annotations

from functools import partial

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


class ExtractorModule(Module):
    """Provides `knowledge.extract` and `knowledge.extract_patterns`."""

    def init(self, container: Container) -> None:
        id_allocator = IdAllocator()
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

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="extractor ready")
