"""The `knowledge.extract` Pipeline Engine stage: dispatches a `Knowledge
Document` to the extraction rule set matching its `metadata.extraction_method`
(rules.py), per KNOWLEDGE_EXTRACTION_SPEC.md's per-source-type rules.

A source type with no in-scope rule set (anything other than
`official_documentation`/`source_code` — see rules.py's module docstring
for why only these two are implemented this Sprint) produces no artifacts
and is not an error: an unsupported source type is a scope boundary, not a
failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.artifacts import ContentArtifact, KnowledgeDocument
from knowledge.extraction.ids import IdAllocator
from knowledge.extraction.rules import extract_from_official_documentation, extract_from_official_source_code
from runtime.events.bus import Event, EventBus
from runtime.pipeline.engine import StageOutcome

if TYPE_CHECKING:
    from runtime.pipeline.engine import PipelineContext

_RULES_BY_EXTRACTION_METHOD = {
    "official_documentation": extract_from_official_documentation,
    "source_code": extract_from_official_source_code,
}


def extract(
    document: KnowledgeDocument,
    context: PipelineContext,
    *,
    id_allocator: IdAllocator,
    event_bus: EventBus | None = None,
) -> tuple[list[ContentArtifact], StageOutcome]:
    del context
    rule = _RULES_BY_EXTRACTION_METHOD.get(document.metadata.extraction_method)
    produced: list[ContentArtifact] = rule(document, id_allocator=id_allocator) if rule is not None else []

    if event_bus is not None:
        for artifact in produced:
            event_bus.publish(
                Event(
                    event_type="ArtifactCreated",
                    payload={"artifact_id": artifact.id, "artifact_type": artifact.type.value},
                    emitted_by="extractor",
                )
            )
    return produced, StageOutcome.SUCCESS
