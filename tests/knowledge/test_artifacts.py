"""Tests for the artifact envelope and type schemas (KNOWLEDGE_ARTIFACTS.md)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from knowledge.artifacts import (
    AntiPattern,
    ArtifactMetadata,
    ArtifactStatus,
    ArtifactType,
    ArtifactVersionInfo,
    BestPractice,
    BestPracticeContent,
    DependencyEdge,
    Example,
    ExampleContent,
    KnowledgeAPI,
    KnowledgeConflict,
    KnowledgeConflictContent,
    KnowledgeDocument,
    Pattern,
    PatternContent,
    RelationshipEdge,
    RelationshipType,
    Workflow,
    WorkflowContent,
    WorkflowStep,
)


def _metadata() -> ArtifactMetadata:
    return ArtifactMetadata(
        extracted_at="2026-01-01T00:00:00Z", extraction_method="fixture", extractor_version="0.1.0"
    )


def test_knowledge_document_constructs_with_no_source_references_required(
    make_knowledge_document: Callable[..., KnowledgeDocument],
) -> None:
    # Schema construction is permissive — "source_references must be
    # non-empty" is Validation's Schema Validation gate's job, not this
    # layer's, per KNOWLEDGE_ARTIFACTS.md §1's "retained, not deleted" rule.
    doc = make_knowledge_document(source_references=())
    assert doc.source_references == ()
    assert doc.status is ArtifactStatus.DRAFT


def test_knowledge_document_type_is_fixed(make_knowledge_document: Callable[..., KnowledgeDocument]) -> None:
    doc = make_knowledge_document()
    assert doc.type is ArtifactType.KNOWLEDGE_DOCUMENT


def test_id_must_match_the_type_prefix(make_knowledge_document: Callable[..., KnowledgeDocument]) -> None:
    with pytest.raises(ValidationError, match="KD-"):
        make_knowledge_document(doc_id="KA-0001")


def test_confidence_out_of_range_is_rejected(make_knowledge_api: Callable[..., KnowledgeAPI]) -> None:
    with pytest.raises(ValidationError):
        make_knowledge_api(confidence=1.5)


def test_artifact_envelope_is_frozen(make_knowledge_api: Callable[..., KnowledgeAPI]) -> None:
    api = make_knowledge_api()
    with pytest.raises(ValidationError):
        api.status = ArtifactStatus.VALIDATED


def test_status_transition_via_model_copy_produces_a_new_instance(
    make_knowledge_api: Callable[..., KnowledgeAPI],
) -> None:
    api = make_knowledge_api()
    validated = api.model_copy(update={"status": ArtifactStatus.VALIDATED})

    assert api.status is ArtifactStatus.DRAFT  # original untouched
    assert validated.status is ArtifactStatus.VALIDATED
    assert validated.id == api.id


def test_pattern_and_anti_pattern_share_content_shape_but_differ_in_type() -> None:
    content = PatternContent(title="Thin Hooks", problem="fat hooks", solution_shape="service layer")
    pattern = Pattern(id="PAT-0001", metadata=_metadata(), version=ArtifactVersionInfo(), content=content)
    anti_pattern = AntiPattern(
        id="AP-0001", metadata=_metadata(), version=ArtifactVersionInfo(), content=content
    )

    assert pattern.type is ArtifactType.PATTERN
    assert anti_pattern.type is ArtifactType.ANTI_PATTERN
    assert pattern.content.title == anti_pattern.content.title == "Thin Hooks"


def test_best_practice_example_and_workflow_construct() -> None:
    bp = BestPractice(
        id="BP-0001",
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=BestPracticeContent(
            title="Prefer Workflow over Client Script", recommendation="use Workflow"
        ),
    )
    ex = Example(
        id="EX-0001",
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=ExampleContent(title="Register a hook", demonstrates="doc_events", code_or_steps="..."),
    )
    wf = Workflow(
        id="WF-0001",
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=WorkflowContent(
            title="Add a Workflow state",
            steps=(WorkflowStep(order=1, description="Open Workflow doctype"),),
        ),
    )
    assert bp.type is ArtifactType.BEST_PRACTICE
    assert ex.type is ArtifactType.EXAMPLE
    assert wf.content.steps[0].order == 1


def test_knowledge_conflict_links_two_claims() -> None:
    conflict = KnowledgeConflict(
        id="KC-0001",
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=KnowledgeConflictContent(claim_a_id="KA-0001", claim_b_id="KA-0002", scope="v15"),
    )
    assert conflict.content.claim_a_id == "KA-0001"
    assert conflict.content.conflict_status.value == "open"


def test_relationship_and_dependency_edges_round_trip(
    make_knowledge_api: Callable[..., KnowledgeAPI],
) -> None:
    api = make_knowledge_api(
        relationships=(RelationshipEdge(target_id="KD-0001", relationship=RelationshipType.IMPLEMENTS),),
        dependencies=(DependencyEdge(target_id="KA-0002", reason="shares the same DocType scope"),),
    )
    assert api.relationships[0].relationship is RelationshipType.IMPLEMENTS
    assert api.dependencies[0].target_id == "KA-0002"
