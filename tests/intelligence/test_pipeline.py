"""Tests for `intelligence/pipeline/` (Sprint 11, Phase 2). Orchestration
only -- exercises the real `intelligence.bridge` translators and real
`IntelligenceEngine` implementations (`NullIntelligenceEngine`,
`ValidatingIntelligenceEngine`) end to end; no mocks for Knowledge or
Intelligence types. Sprint-level, whole-package import-boundary tests for
`intelligence/pipeline/` live in `tests/sprint11/test_architecture_boundaries.py`
(extended in Phase 2 alongside its existing Phase 1 `bridge/` checks);
this file covers functional behavior only.
"""

from __future__ import annotations

import pytest

from analysis.requirements.analyzer import build_analysis_result
from analysis.requirements.raw import RawEntityMention, RawProcessMention, RawRequirement
from knowledge.artifacts import RelationshipType
from knowledge.builder.builder import build_knowledge_snapshot
from knowledge.domain import KnowledgeCollection, KnowledgeSnapshot
from knowledge.graph import GraphEdge
from knowledge.projection.projector import project_snapshot

from intelligence.bridge import (
    translate_artifact_to_candidate,
    translate_reference_to_evidence,
)
from intelligence.contract import (
    ArchitectureCritique,
    AssumptionChallenge,
    Candidate,
    EvidenceItem,
    IntelligenceEngine,
    ProposedArchitecture,
    Requirement,
    RequirementUnderstanding,
    TradeoffAssessment,
)
from intelligence.null_engine import NullIntelligenceEngine
from intelligence.pipeline import collect_candidates, collect_evidence, evaluate_knowledge_snapshot
from intelligence.validating import ValidatingIntelligenceEngine

_CREATED_AT = "2026-01-01T00:00:00Z"


def _realistic_snapshot() -> KnowledgeSnapshot:
    requirement = RawRequirement(
        requirement_id="REQ-1",
        description="Track patient registration.",
        entities=(RawEntityMention(name="Patient", excerpt="a patient record"),),
        processes=(
            RawProcessMention(
                name="Patient Registration",
                excerpt="register new patients",
                steps=("collect identity", "assign medical record number"),
                actors=(),
            ),
        ),
    )
    analysis_result = build_analysis_result(requirement)
    built = build_knowledge_snapshot(analysis_result, created_at=_CREATED_AT)
    return project_snapshot(built)


def _unprojected_snapshot() -> KnowledgeSnapshot:
    """Built but never projected -- every collection's `.nodes`/`.edges`
    are empty, exercising the "missing optional Knowledge objects" case.
    """

    requirement = RawRequirement(
        requirement_id="REQ-2",
        description="Track invoicing.",
        entities=(RawEntityMention(name="Invoice", excerpt="an invoice record"),),
    )
    analysis_result = build_analysis_result(requirement)
    return build_knowledge_snapshot(analysis_result, created_at=_CREATED_AT)


def _snapshot_with_edge() -> KnowledgeSnapshot:
    """A manually-assembled snapshot carrying one real `GraphEdge`. The
    real `build_knowledge_snapshot` -> `project_snapshot` chain never
    populates `Workflow.dependencies`/`.relationships` (`knowledge.
    builder.builder`'s own disclosed scope), so no edge can be produced
    by going through that real pipeline today -- this fixture exercises
    `translate_edge_to_evidence` directly against a real `GraphEdge`
    instead, still using only real, frozen Knowledge types, no mocks.
    """

    requirement = RawRequirement(requirement_id="REQ-EDGE", description="Two related workflows.")
    analysis_result = build_analysis_result(requirement)
    collection = KnowledgeCollection(
        collection_id="collection:manual",
        name="manual",
        edges=(
            GraphEdge(
                source_node_id="KG-WF-1",
                relationship=RelationshipType.DEPENDS_ON,
                target_node_id="KG-WF-2",
            ),
        ),
    )
    return KnowledgeSnapshot(
        snapshot_id="snapshot:manual",
        created_at=_CREATED_AT,
        source=analysis_result,
        collections=(collection,),
    )


def _empty_snapshot() -> KnowledgeSnapshot:
    requirement = RawRequirement(requirement_id="REQ-EMPTY", description="Nothing to extract.")
    analysis_result = build_analysis_result(requirement)
    return build_knowledge_snapshot(analysis_result, created_at=_CREATED_AT)


class _CapturingEngine(IntelligenceEngine):
    """A minimal, non-`Null`/non-`Validating` `IntelligenceEngine` used
    only to prove exactly what this pipeline passes to `evaluate_tradeoff`
    -- a distinct concern from whether `NullIntelligenceEngine`'s own
    ranking behavior is correct (already Sprint 8's own responsibility).
    """

    def __init__(self) -> None:
        self.received_evidence: tuple[EvidenceItem, ...] | None = None
        self.received_candidates: tuple[Candidate, ...] | None = None

    def interpret_requirement(self, requirement: Requirement) -> RequirementUnderstanding:
        raise NotImplementedError

    def evaluate_tradeoff(
        self, evidence: tuple[EvidenceItem, ...], candidates: tuple[Candidate, ...]
    ) -> TradeoffAssessment:
        self.received_evidence = evidence
        self.received_candidates = candidates
        return TradeoffAssessment(rationale="captured")

    def critique_architecture(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> ArchitectureCritique:
        raise NotImplementedError

    def challenge_assumptions(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> AssumptionChallenge:
        raise NotImplementedError


# -- collect_evidence / collect_candidates -- translation invocation --------------------------------


def test_collect_evidence_matches_direct_bridge_translation_of_every_reference() -> None:
    snapshot = _realistic_snapshot()
    collection = snapshot.collections[0]
    expected = tuple(translate_reference_to_evidence(reference) for reference in collection.references)
    evidence = collect_evidence(snapshot)
    for item in expected:
        assert item in evidence


def test_collect_candidates_matches_direct_bridge_translation_of_every_artifact() -> None:
    snapshot = _realistic_snapshot()
    collection = snapshot.collections[0]
    expected = tuple(translate_artifact_to_candidate(artifact) for artifact in collection.artifacts)
    assert collect_candidates(snapshot) == expected


def test_collect_evidence_includes_nodes_and_edges_once_projected() -> None:
    snapshot = _realistic_snapshot()
    collection = snapshot.collections[0]
    assert collection.nodes  # sanity: this fixture really is projected
    evidence_ids = {item.reference_id for item in collect_evidence(snapshot)}
    for node in collection.nodes:
        assert node.node_id in evidence_ids


def test_collect_evidence_translates_edges() -> None:
    evidence = collect_evidence(_snapshot_with_edge())
    assert evidence == (
        EvidenceItem(
            reference_id="KG-WF-1:depends_on:KG-WF-2",
            summary="Graph edge: 'KG-WF-1' depends_on 'KG-WF-2'.",
        ),
    )


# -- missing optional Knowledge objects ----------------------------------------------------------------


def test_collect_evidence_without_projection_has_no_node_or_edge_evidence() -> None:
    snapshot = _unprojected_snapshot()
    collection = snapshot.collections[0]
    assert collection.nodes == ()
    assert collection.edges == ()
    # References still translate fine even with no graph structure yet.
    assert collect_evidence(snapshot) != ()


# -- empty KnowledgeSnapshot ----------------------------------------------------------------------------


def test_collect_evidence_and_candidates_are_empty_for_an_empty_snapshot() -> None:
    snapshot = _empty_snapshot()
    assert collect_evidence(snapshot) == ()
    assert collect_candidates(snapshot) == ()


def test_evaluate_knowledge_snapshot_handles_an_empty_snapshot_gracefully() -> None:
    result = evaluate_knowledge_snapshot(_empty_snapshot(), NullIntelligenceEngine())
    assert result == TradeoffAssessment(
        ranked_candidate_ids=(), rationale="no candidates supplied to rank", cited_evidence_ids=()
    )


# -- Successful end-to-end flow / NullIntelligenceEngine integration --------------------------------


def test_evaluate_knowledge_snapshot_end_to_end_with_null_engine() -> None:
    snapshot = _realistic_snapshot()
    result = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    assert isinstance(result, TradeoffAssessment)
    candidate_ids = {candidate.candidate_id for candidate in collect_candidates(snapshot)}
    assert set(result.ranked_candidate_ids) == candidate_ids


# -- ValidatingIntelligenceEngine integration ---------------------------------------------------------


def test_evaluate_knowledge_snapshot_with_validating_engine_passes_through_cleanly() -> None:
    snapshot = _realistic_snapshot()
    engine = ValidatingIntelligenceEngine(NullIntelligenceEngine())
    result = evaluate_knowledge_snapshot(snapshot, engine)
    # No CitationError raised means every id the Null engine echoed back
    # really was present in this pipeline's own translated input.
    assert isinstance(result, TradeoffAssessment)


# -- Engine invocation: prove exactly what the pipeline hands the engine ----------------------------


def test_evaluate_knowledge_snapshot_invokes_the_engine_with_the_collected_tuples() -> None:
    snapshot = _realistic_snapshot()
    engine = _CapturingEngine()
    evaluate_knowledge_snapshot(snapshot, engine)
    assert engine.received_evidence == collect_evidence(snapshot)
    assert engine.received_candidates == collect_candidates(snapshot)


# -- Determinism across repeated execution -------------------------------------------------------------


def test_evaluate_knowledge_snapshot_is_deterministic_across_repeated_calls() -> None:
    snapshot = _realistic_snapshot()
    first = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    second = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    assert first == second


def test_collect_evidence_and_candidates_are_deterministic_across_repeated_calls() -> None:
    snapshot = _realistic_snapshot()
    assert collect_evidence(snapshot) == collect_evidence(snapshot)
    assert collect_candidates(snapshot) == collect_candidates(snapshot)


# -- Invalid inputs -------------------------------------------------------------------------------------


def test_evaluate_knowledge_snapshot_does_not_swallow_an_invalid_snapshot() -> None:
    # `snapshot` is typed `Any` (see orchestrator.py's own docstring) --
    # this proves the pipeline does not defensively catch or repair a
    # malformed input, only lets the real `AttributeError` propagate.
    with pytest.raises(AttributeError):
        evaluate_knowledge_snapshot(None, NullIntelligenceEngine())
