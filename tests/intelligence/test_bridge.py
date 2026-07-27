"""Tests for `intelligence/bridge/` (Sprint 11, Phase 1). Deterministic
translation only — no `IntelligenceEngine` invocation, no reasoning, no
ranking; those are explicitly out of this phase's own scope. Sprint-level,
whole-package import-boundary tests live in
`tests/sprint11/test_architecture_boundaries.py`; this file's own single
import-boundary test below checks only `translator.py` in isolation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge.artifacts import (
    ArtifactMetadata,
    ArtifactType,
    ArtifactVersionInfo,
    DependencyEdge,
    KnowledgeAPI,
    KnowledgeAPIContent,
    RelationshipEdge,
    RelationshipType,
    Workflow,
    WorkflowContent,
    WorkflowStep,
)
from knowledge.domain import KnowledgeReference
from knowledge.graph import GraphEdge, GraphNode

from intelligence.bridge import (
    translate_artifact_to_candidate,
    translate_artifact_to_evidence,
    translate_edge_to_evidence,
    translate_node_to_evidence,
    translate_reference_to_evidence,
)
from intelligence.contract import Candidate, EvidenceItem

TRANSLATOR_FILE = Path(__file__).resolve().parents[2] / "intelligence" / "bridge" / "translator.py"


def _workflow(
    *,
    dependencies: tuple[DependencyEdge, ...] = (),
    relationships: tuple[RelationshipEdge, ...] = (),
    confidence: float = 0.75,
) -> Workflow:
    return Workflow(
        id="WF-REQ-1:process:Registration",
        metadata=ArtifactMetadata(
            extracted_at="2026-01-01T00:00:00Z",
            extraction_method="test",
            extractor_version="0.1.0",
        ),
        version=ArtifactVersionInfo(),
        confidence=confidence,
        dependencies=dependencies,
        relationships=relationships,
        content=WorkflowContent(
            title="Patient Registration",
            steps=(WorkflowStep(order=0, description="collect identity"),),
        ),
    )


def _knowledge_api() -> KnowledgeAPI:
    return KnowledgeAPI(
        id="KA-patient-name-field",
        metadata=ArtifactMetadata(
            extracted_at="2026-01-01T00:00:00Z",
            extraction_method="test",
            extractor_version="0.1.0",
        ),
        version=ArtifactVersionInfo(),
        confidence=0.5,
        content=KnowledgeAPIContent(interface_kind="doctype-field", name="Patient.patient_name"),
    )


def _knowledge_reference() -> KnowledgeReference:
    return KnowledgeReference(
        analysis_id="analysis:REQ-1",
        subject_id="REQ-1:entity:Patient",
        subject_kind="business_entity",
    )


def _graph_node(*, node_id: str = "KG-WF-REQ-1:process:Registration") -> GraphNode:
    return GraphNode(node_id=node_id, wraps="WF-REQ-1:process:Registration", wraps_type=ArtifactType.WORKFLOW)


def _graph_edge(*, confidence_of_edge: float | None = None) -> GraphEdge:
    return GraphEdge(
        source_node_id="KG-WF-1",
        relationship=RelationshipType.DEPENDS_ON,
        target_node_id="KG-WF-2",
        confidence_of_edge=confidence_of_edge,
    )


# -- ContentArtifact -> EvidenceItem ----------------------------------------------------------------


def test_translate_artifact_to_evidence_uses_title_for_title_bearing_artifacts() -> None:
    evidence = translate_artifact_to_evidence(_workflow())
    assert evidence == EvidenceItem(
        reference_id="WF-REQ-1:process:Registration",
        summary="Patient Registration",
        weight=0.75,
    )


def test_translate_artifact_to_evidence_uses_name_for_knowledge_api() -> None:
    evidence = translate_artifact_to_evidence(_knowledge_api())
    assert evidence.reference_id == "KA-patient-name-field"
    assert evidence.summary == "Patient.patient_name"
    assert evidence.weight == 0.5


def test_translate_artifact_to_evidence_passes_confidence_through_verbatim() -> None:
    assert translate_artifact_to_evidence(_workflow(confidence=0.0)).weight == 0.0
    assert translate_artifact_to_evidence(_workflow(confidence=1.0)).weight == 1.0


# -- ContentArtifact -> Candidate --------------------------------------------------------------------


def test_translate_artifact_to_candidate_with_no_dependencies_or_relationships() -> None:
    candidate = translate_artifact_to_candidate(_workflow())
    assert candidate == Candidate(
        candidate_id="WF-REQ-1:process:Registration",
        description="Patient Registration",
        supporting_evidence_ids=(),
    )


def test_translate_artifact_to_candidate_collects_dependency_and_relationship_target_ids() -> None:
    artifact = _workflow(
        dependencies=(DependencyEdge(target_id="WF-A"),),
        relationships=(RelationshipEdge(target_id="WF-B", relationship=RelationshipType.RELATED_TO),),
    )
    candidate = translate_artifact_to_candidate(artifact)
    assert candidate.supporting_evidence_ids == ("WF-A", "WF-B")


def test_translate_artifact_to_candidate_deduplicates_preserving_first_occurrence_order() -> None:
    artifact = _workflow(
        dependencies=(
            DependencyEdge(target_id="WF-A"),
            DependencyEdge(target_id="WF-B"),
        ),
        relationships=(
            RelationshipEdge(target_id="WF-B", relationship=RelationshipType.RELATED_TO),
            RelationshipEdge(target_id="WF-C", relationship=RelationshipType.RELATED_TO),
        ),
    )
    candidate = translate_artifact_to_candidate(artifact)
    assert candidate.supporting_evidence_ids == ("WF-A", "WF-B", "WF-C")


def test_translate_artifact_to_candidate_uses_name_for_knowledge_api() -> None:
    candidate = translate_artifact_to_candidate(_knowledge_api())
    assert candidate.candidate_id == "KA-patient-name-field"
    assert candidate.description == "Patient.patient_name"


# -- KnowledgeReference -> EvidenceItem ---------------------------------------------------------------


def test_translate_reference_to_evidence() -> None:
    evidence = translate_reference_to_evidence(_knowledge_reference())
    assert evidence == EvidenceItem(
        reference_id="analysis:REQ-1:business_entity:REQ-1:entity:Patient",
        summary="Knowledge reference to business_entity 'REQ-1:entity:Patient' from analysis 'analysis:REQ-1'.",
        weight=1.0,
    )


# -- GraphNode -> EvidenceItem ------------------------------------------------------------------------


def test_translate_node_to_evidence() -> None:
    evidence = translate_node_to_evidence(_graph_node())
    assert evidence == EvidenceItem(
        reference_id="KG-WF-REQ-1:process:Registration",
        summary="Graph node wrapping workflow artifact 'WF-REQ-1:process:Registration'.",
        weight=1.0,
    )


def test_translate_node_to_evidence_propagates_a_pydantic_validation_error_on_an_empty_node_id() -> None:
    # GraphNode.node_id has no min_length constraint of its own, so an
    # empty node_id is constructible -- proving this translator does not
    # swallow or repair the resulting invalid EvidenceItem, only lets
    # EvidenceItem's own min_length=1 validation reject it.
    empty_node = GraphNode(node_id="", wraps="WF-1", wraps_type=ArtifactType.WORKFLOW)
    with pytest.raises(ValidationError):
        translate_node_to_evidence(empty_node)


# -- GraphEdge -> EvidenceItem ------------------------------------------------------------------------


def test_translate_edge_to_evidence_uses_default_weight_when_confidence_of_edge_is_none() -> None:
    evidence = translate_edge_to_evidence(_graph_edge(confidence_of_edge=None))
    assert evidence == EvidenceItem(
        reference_id="KG-WF-1:depends_on:KG-WF-2",
        summary="Graph edge: 'KG-WF-1' depends_on 'KG-WF-2'.",
        weight=1.0,
    )


def test_translate_edge_to_evidence_uses_confidence_of_edge_when_present() -> None:
    evidence = translate_edge_to_evidence(_graph_edge(confidence_of_edge=0.3))
    assert evidence.weight == 0.3


# -- Determinism / repeated-translation equality -------------------------------------------------------


def test_every_translator_is_deterministic_across_repeated_calls() -> None:
    workflow = _workflow(dependencies=(DependencyEdge(target_id="WF-A"),))
    reference = _knowledge_reference()
    node = _graph_node()
    edge = _graph_edge(confidence_of_edge=0.4)

    assert translate_artifact_to_evidence(workflow) == translate_artifact_to_evidence(workflow)
    assert translate_artifact_to_candidate(workflow) == translate_artifact_to_candidate(workflow)
    assert translate_reference_to_evidence(reference) == translate_reference_to_evidence(reference)
    assert translate_node_to_evidence(node) == translate_node_to_evidence(node)
    assert translate_edge_to_evidence(edge) == translate_edge_to_evidence(edge)


# -- Import boundaries (this file only -- see tests/sprint11/ for the whole-package scan) --------------


def test_translator_module_imports_only_knowledge_and_intelligence_contract() -> None:
    tree = ast.parse(TRANSLATOR_FILE.read_text(encoding="utf-8"), filename=str(TRANSLATOR_FILE))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    assert modules - {"__future__"} == {"knowledge", "intelligence"}
