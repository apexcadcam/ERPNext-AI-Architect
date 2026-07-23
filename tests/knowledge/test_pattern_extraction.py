"""Tests for Pattern Extraction (KNOWLEDGE_EXTRACTION_SPEC.md §9)."""

from __future__ import annotations

from collections.abc import Callable

from knowledge.artifacts import ArtifactType, ContentArtifact, KnowledgeAPI, ProvenanceLink
from knowledge.extraction import IdAllocator, extract_patterns
from knowledge.extraction.pattern_extraction import (
    ANTI_PATTERN_CANDIDATE_TAG_PREFIX,
    PATTERN_CANDIDATE_TAG_PREFIX,
)
from runtime.pipeline.engine import PipelineContext, StageOutcome


def _tagged_api(
    make_knowledge_api: Callable[..., KnowledgeAPI],
    api_id: str,
    source_doc_id: str,
    tag_prefix: str,
    shape_key: str,
) -> KnowledgeAPI:
    return make_knowledge_api(
        api_id=api_id,
        provenance=(ProvenanceLink(id=source_doc_id, artifact_type="knowledge_document"),),
        tags=(f"{tag_prefix}{shape_key}",),
    )


def test_a_shape_observed_once_is_never_promoted_to_a_pattern(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    single = _tagged_api(make_knowledge_api, "KA-0001", "KD-0001", PATTERN_CANDIDATE_TAG_PREFIX, "thin-hooks")

    produced, outcome = extract_patterns([single], pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    assert produced == [single]  # unchanged — no Pattern manufactured from one anecdote


def test_a_shape_from_two_independent_sources_is_promoted_to_a_pattern(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    first = _tagged_api(make_knowledge_api, "KA-0001", "KD-0001", PATTERN_CANDIDATE_TAG_PREFIX, "thin-hooks")
    second = _tagged_api(make_knowledge_api, "KA-0002", "KD-0002", PATTERN_CANDIDATE_TAG_PREFIX, "thin-hooks")

    produced, outcome = extract_patterns([first, second], pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    assert len(produced) == 3  # the two originals plus one promoted Pattern
    pattern = next(a for a in produced if a.type is ArtifactType.PATTERN)
    assert pattern.content.solution_shape == "thin-hooks"
    referenced_ids = {edge.target_id for edge in pattern.relationships}
    assert referenced_ids == {"KA-0001", "KA-0002"}


def test_a_shape_repeated_within_one_source_document_is_not_promoted(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    # Two artifacts, same shape key, but from the SAME Knowledge Document —
    # not independent corroboration, per §9's own bar.
    first = _tagged_api(make_knowledge_api, "KA-0001", "KD-0001", PATTERN_CANDIDATE_TAG_PREFIX, "thin-hooks")
    second = _tagged_api(make_knowledge_api, "KA-0002", "KD-0001", PATTERN_CANDIDATE_TAG_PREFIX, "thin-hooks")

    produced, outcome = extract_patterns([first, second], pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    assert produced == [first, second]  # no Pattern promoted


def test_anti_pattern_promotion_uses_its_own_tag_prefix(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    first = _tagged_api(
        make_knowledge_api, "KA-0001", "KD-0001", ANTI_PATTERN_CANDIDATE_TAG_PREFIX, "god-hook"
    )
    second = _tagged_api(
        make_knowledge_api, "KA-0002", "KD-0002", ANTI_PATTERN_CANDIDATE_TAG_PREFIX, "god-hook"
    )

    produced, outcome = extract_patterns([first, second], pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    anti_pattern = next(a for a in produced if a.type is ArtifactType.ANTI_PATTERN)
    assert anti_pattern.content.solution_shape == "god-hook"


def test_untagged_artifacts_are_passed_through_unaffected(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    plain: ContentArtifact = make_knowledge_api()

    produced, outcome = extract_patterns([plain], pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    assert produced == [plain]


def test_promoted_pattern_confidence_starts_at_zero_pending_validation(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    first = _tagged_api(make_knowledge_api, "KA-0001", "KD-0001", PATTERN_CANDIDATE_TAG_PREFIX, "thin-hooks")
    second = _tagged_api(make_knowledge_api, "KA-0002", "KD-0002", PATTERN_CANDIDATE_TAG_PREFIX, "thin-hooks")

    produced, _ = extract_patterns([first, second], pipeline_context, id_allocator=IdAllocator())

    pattern = next(a for a in produced if a.type is ArtifactType.PATTERN)
    assert pattern.confidence == 0.0  # never hand-set — KNOWLEDGE_ARTIFACTS.md §1's invariant
