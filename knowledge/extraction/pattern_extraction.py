"""Pattern Extraction: the distinguished second pass over already-extracted
artifacts, per KNOWLEDGE_EXTRACTION_SPEC.md §9.

A recurring solution shape needs a similarity judgment Sprint 2 has no
semantic/embedding capability to make (Embedding is explicitly out of
scope, per SPRINT2_IMPLEMENTATION_PLAN.md §3). Rather than fake that
judgment with an ad hoc text-similarity heuristic that would silently claim
more sophistication than it has, this Sprint uses an explicit, deterministic
signal: an extraction rule (rules.py, or a future one) tags a candidate
artifact `pattern-candidate:<shape-key>` / `anti-pattern-candidate:<shape-key>`
— the same tag-facet convention KNOWLEDGE_EXTRACTION_SPEC.md itself already
uses for `verified-fixed`, `interim-workaround`, `third-party-observed`, etc.
Two or more independently-provenanced artifacts sharing a shape-key are
promoted to a `Pattern`/`AntiPattern`; a shape observed in only one artifact,
or from only one source, is left as-is — never promoted from a single
anecdote, per §9's own "when to create" bar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.artifacts import (
    AntiPattern,
    ArtifactType,
    ContentArtifact,
    Pattern,
    PatternContent,
    RelationshipEdge,
    RelationshipType,
)
from knowledge.extraction.ids import IdAllocator
from runtime.events.bus import Event, EventBus
from runtime.pipeline.engine import StageOutcome

if TYPE_CHECKING:
    from runtime.pipeline.engine import PipelineContext

PATTERN_CANDIDATE_TAG_PREFIX = "pattern-candidate:"
ANTI_PATTERN_CANDIDATE_TAG_PREFIX = "anti-pattern-candidate:"

#: §9: "observed successfully more than once" — the minimum independent
#: corroboration bar before a candidate shape is promoted.
_MINIMUM_INDEPENDENT_ARTIFACTS = 2


def extract_patterns(
    artifacts: list[ContentArtifact],
    context: PipelineContext,
    *,
    id_allocator: IdAllocator,
    event_bus: EventBus | None = None,
) -> tuple[list[ContentArtifact], StageOutcome]:
    """Appends any newly-promoted `Pattern`/`AntiPattern` artifacts to the
    incoming list; every already-extracted artifact is passed through
    unchanged (Pattern Extraction never removes or rewrites what Extraction
    already produced). Publishes `ArtifactCreated` (STUDIO_EVENT_MODEL.md §2)
    for each newly-promoted artifact.
    """

    del context
    promoted: list[ContentArtifact] = []
    promoted.extend(
        _promote_recurring_shapes(
            artifacts,
            tag_prefix=PATTERN_CANDIDATE_TAG_PREFIX,
            artifact_type=ArtifactType.PATTERN,
            id_allocator=id_allocator,
        )
    )
    promoted.extend(
        _promote_recurring_shapes(
            artifacts,
            tag_prefix=ANTI_PATTERN_CANDIDATE_TAG_PREFIX,
            artifact_type=ArtifactType.ANTI_PATTERN,
            id_allocator=id_allocator,
        )
    )

    if event_bus is not None:
        for artifact in promoted:
            event_bus.publish(
                Event(
                    event_type="ArtifactCreated",
                    payload={"artifact_id": artifact.id, "artifact_type": artifact.type.value},
                    emitted_by="extractor",
                )
            )

    return [*artifacts, *promoted], StageOutcome.SUCCESS


def _promote_recurring_shapes(
    artifacts: list[ContentArtifact],
    *,
    tag_prefix: str,
    artifact_type: ArtifactType,
    id_allocator: IdAllocator,
) -> list[ContentArtifact]:
    groups: dict[str, list[ContentArtifact]] = {}
    for artifact in artifacts:
        shape_key = _shape_key(artifact, tag_prefix)
        if shape_key is not None:
            groups.setdefault(shape_key, []).append(artifact)

    promoted: list[ContentArtifact] = []
    for shape_key, group in groups.items():
        independent_sources = {link.id for artifact in group for link in artifact.provenance}
        if (
            len(group) >= _MINIMUM_INDEPENDENT_ARTIFACTS
            and len(independent_sources) >= _MINIMUM_INDEPENDENT_ARTIFACTS
        ):
            promoted.append(_build_pattern(shape_key, group, artifact_type, id_allocator))
    return promoted


def _shape_key(artifact: ContentArtifact, tag_prefix: str) -> str | None:
    for tag in artifact.tags:
        if tag.startswith(tag_prefix):
            return tag[len(tag_prefix) :]
    return None


def _build_pattern(
    shape_key: str, group: list[ContentArtifact], artifact_type: ArtifactType, id_allocator: IdAllocator
) -> ContentArtifact:
    references = tuple(
        RelationshipEdge(target_id=member.id, relationship=RelationshipType.REFERENCES) for member in group
    )
    content = PatternContent(
        title=shape_key,
        problem=f"a recurring shape observed across {len(group)} independently-sourced artifacts",
        solution_shape=shape_key,
    )
    # Confidence is computed later by Validation's Confidence Scoring — never
    # hand-set here, per KNOWLEDGE_ARTIFACTS.md §1's invariant.
    metadata = group[0].metadata.model_copy(update={"extraction_method": "pattern_extraction"})
    source_references = tuple(ref for member in group for ref in member.source_references)

    if artifact_type is ArtifactType.ANTI_PATTERN:
        return AntiPattern(
            id=id_allocator.next_id(artifact_type),
            metadata=metadata,
            version=group[0].version,
            source_references=source_references,
            relationships=references,
            content=content,
        )
    return Pattern(
        id=id_allocator.next_id(artifact_type),
        metadata=metadata,
        version=group[0].version,
        source_references=source_references,
        relationships=references,
        content=content,
    )
