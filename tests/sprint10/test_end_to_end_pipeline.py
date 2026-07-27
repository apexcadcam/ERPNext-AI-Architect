"""Sprint 10 — End-to-End Pipeline Validation.

Exercises the complete, real chain Phases 1-4 built, as one unit, for the
first time through a single entry point per stage rather than each
phase's own isolated unit tests:

    AnalysisResult -> Knowledge Builder -> KnowledgeSnapshot
    -> Graph Projection -> Knowledge Query Service

Self-contained, mirroring `tests/sprint7/test_end_to_end_flow.py`'s and
`tests/sprint9/test_end_to_end_pipeline.py`'s own discipline: this
directory does not import fixtures from `tests/knowledge/` (a sibling,
not an ancestor) — every input here is rebuilt directly via the real
constructors, minimally.
"""

from __future__ import annotations

import json

from analysis.contract import AnalysisResult
from analysis.requirements.analyzer import build_analysis_result
from analysis.requirements.raw import (
    RawActorMention,
    RawConstraintMention,
    RawEntityMention,
    RawProcessMention,
    RawRequirement,
    RawRuleMention,
)
from knowledge.artifacts import Workflow
from knowledge.builder.builder import build_knowledge_snapshot
from knowledge.domain import KnowledgeSnapshot
from knowledge.projection.projector import project_snapshot
from knowledge.query.service import KnowledgeQueryService

_CREATED_AT = "2026-01-01T00:00:00Z"


def _structured_requirement() -> RawRequirement:
    return RawRequirement(
        requirement_id="REQ-CLINIC-1",
        description="Track patient identity, appointments, and customer billing.",
        entities=(
            RawEntityMention(name="Patient", excerpt="track patient identity"),
            RawEntityMention(name="Patient", excerpt="a second, duplicate patient mention"),
        ),
        processes=(
            RawProcessMention(
                name="Patient Registration",
                excerpt="register new patients before their first visit",
                steps=("collect identity", "assign medical record number"),
                actors=("Receptionist",),
            ),
        ),
        actors=(RawActorMention(name="Receptionist", excerpt="the receptionist registers patients"),),
        rules=(
            RawRuleMention(
                statement="An invoice requires a confirmed appointment",
                excerpt="an invoice is issued once the appointment is confirmed",
            ),
        ),
        constraints=(
            RawConstraintMention(
                statement="Only one active prescription per patient",
                excerpt="a patient may not hold two active prescriptions",
            ),
        ),
    )


def _run_pipeline() -> tuple[AnalysisResult, KnowledgeSnapshot, KnowledgeSnapshot, KnowledgeQueryService]:
    """Runs the complete, real chain once. Returns every intermediate
    stage's own output, so tests can assert that later stages never
    mutate earlier ones.
    """

    analysis_result = build_analysis_result(_structured_requirement())
    built_snapshot = build_knowledge_snapshot(analysis_result, created_at=_CREATED_AT)
    projected_snapshot = project_snapshot(built_snapshot)
    query_service = KnowledgeQueryService(projected_snapshot)
    return analysis_result, built_snapshot, projected_snapshot, query_service


# -- The pipeline produces a coherent, meaningful result --------------------------------------------


def test_pipeline_produces_the_expected_shape() -> None:
    _, _, projected_snapshot, query_service = _run_pipeline()

    assert len(projected_snapshot.collections) == 1
    # One Workflow (from the one BusinessProcess) -- the only fact kind
    # with a genuine ContentArtifact fit (Sprint 10 Phase 2's own finding).
    artifacts = query_service.list_artifacts()
    assert len(artifacts) == 1
    assert isinstance(artifacts[0], Workflow)

    # One GraphNode projected from that one Workflow artifact.
    nodes = query_service.list_nodes()
    assert len(nodes) == 1
    assert nodes[0].wraps == artifacts[0].id

    # 2 duplicate-entity + 1 process + 1 rule + 1 constraint + 1 actor = 6 references.
    assert len(query_service.list_references()) == 6


# -- Deterministic output, repeated execution --------------------------------------------------------


def test_pipeline_is_fully_deterministic_across_repeated_runs() -> None:
    _, _, first_snapshot, _ = _run_pipeline()
    _, _, second_snapshot, _ = _run_pipeline()
    assert first_snapshot == second_snapshot


def test_pipeline_query_results_are_deterministic_across_repeated_runs() -> None:
    _, _, _, first_service = _run_pipeline()
    _, _, _, second_service = _run_pipeline()
    assert first_service.list_artifacts() == second_service.list_artifacts()
    assert first_service.list_references() == second_service.list_references()
    assert first_service.statistics("collection:analysis:REQ-CLINIC-1") == second_service.statistics(
        "collection:analysis:REQ-CLINIC-1"
    )


# -- Idempotency: re-running Projection on its own output changes nothing --------------------------


def test_reprojecting_the_projected_snapshot_is_idempotent() -> None:
    _, _, projected_snapshot, _ = _run_pipeline()
    reprojected = project_snapshot(projected_snapshot)
    assert reprojected == projected_snapshot


# -- No stage mutates a previous stage's output -------------------------------------------------------


def test_projection_never_mutates_the_builders_output() -> None:
    analysis_result, built_snapshot, _, _ = _run_pipeline()
    # built_snapshot was captured before projection ran; re-derive it
    # independently and confirm it still matches -- proving project_snapshot
    # returned a new object rather than mutating built_snapshot in place.
    rebuilt = build_knowledge_snapshot(analysis_result, created_at=_CREATED_AT)
    assert built_snapshot == rebuilt
    assert built_snapshot.collections[0].nodes == ()
    assert built_snapshot.collections[0].edges == ()


def test_builder_never_mutates_the_analysis_result() -> None:
    analysis_result, _, _, _ = _run_pipeline()
    assert analysis_result.similarity_results == ()
    assert analysis_result.gaps == ()


def test_query_service_never_mutates_the_projected_snapshot() -> None:
    _, _, projected_snapshot, query_service = _run_pipeline()
    before = projected_snapshot.model_dump()

    query_service.list_collections()
    query_service.list_artifacts()
    query_service.list_nodes()
    query_service.list_edges()
    query_service.list_references()
    query_service.list_statistics()

    assert projected_snapshot.model_dump() == before


# -- Each stage remains independently testable ----------------------------------------------------


def test_each_stage_can_be_exercised_independently_of_the_others() -> None:
    analysis_result = build_analysis_result(_structured_requirement())
    assert isinstance(analysis_result, AnalysisResult)

    built_snapshot = build_knowledge_snapshot(analysis_result, created_at=_CREATED_AT)
    assert built_snapshot.collections[0].nodes == ()  # Builder alone never projects

    projected_snapshot = project_snapshot(built_snapshot)
    assert len(projected_snapshot.collections[0].nodes) == 1  # Projection alone adds nodes

    query_service = KnowledgeQueryService(projected_snapshot)
    assert len(query_service.list_artifacts()) == 1  # Query alone reads what's there


# -- Provenance, identifier, and relationship preservation, end to end ------------------------------


def test_every_reference_traces_back_to_the_real_analysis_id() -> None:
    _, _, _, query_service = _run_pipeline()
    for reference in query_service.list_references():
        assert reference.analysis_id == "analysis:REQ-CLINIC-1"


def test_node_identifiers_trace_back_to_the_real_artifact_ids() -> None:
    _, _, _, query_service = _run_pipeline()
    for node in query_service.list_nodes():
        artifact = query_service.find_artifact(node.wraps)
        assert artifact is not None
        assert node.node_id == f"KG-{artifact.id}"


def test_duplicate_entity_mentions_survive_the_entire_pipeline_unmerged() -> None:
    _, _, _, query_service = _run_pipeline()
    patient_references = query_service.list_references(subject_id="REQ-CLINIC-1:entity:Patient")
    # Two identical mentions in the raw requirement -- both survive,
    # through Analysis, the Builder, Projection, and Query, unmerged.
    assert len(patient_references) == 2


# -- Serialization --------------------------------------------------------------------------------


def test_final_pipeline_output_round_trips_through_json() -> None:
    _, _, projected_snapshot, _ = _run_pipeline()
    restored = KnowledgeSnapshot.model_validate_json(projected_snapshot.model_dump_json())
    assert restored == projected_snapshot


def test_final_pipeline_output_round_trips_through_plain_json_dumps() -> None:
    _, _, projected_snapshot, _ = _run_pipeline()
    as_dict = projected_snapshot.model_dump(mode="json")
    reserialized = json.loads(json.dumps(as_dict))
    assert KnowledgeSnapshot.model_validate(reserialized) == projected_snapshot


# -- No hidden global/shared mutable state, no caching --------------------------------------------


def test_two_independent_query_services_over_the_same_snapshot_behave_identically() -> None:
    _, _, projected_snapshot, _ = _run_pipeline()
    service_a = KnowledgeQueryService(projected_snapshot)
    service_b = KnowledgeQueryService(projected_snapshot)
    assert service_a.list_artifacts() == service_b.list_artifacts()
    assert service_a.list_references() == service_b.list_references()


def test_repeated_calls_on_one_service_are_not_served_from_a_cache() -> None:
    # Value-equal every time (deterministic), but never the *same* tuple
    # object -- proves each call is a fresh computation, not a cached
    # return, which is what "no caching" means structurally.
    _, _, _, query_service = _run_pipeline()
    first_call = query_service.list_artifacts()
    second_call = query_service.list_artifacts()
    assert first_call == second_call
    assert first_call is not second_call


def test_two_pipeline_runs_do_not_share_any_mutable_state() -> None:
    _, built_snapshot_a, _, _ = _run_pipeline()
    _, built_snapshot_b, _, _ = _run_pipeline()
    # Equal in value, but independently constructed objects -- confirms
    # no module-level cache or shared container is silently reused.
    assert built_snapshot_a == built_snapshot_b
    assert built_snapshot_a is not built_snapshot_b
    assert built_snapshot_a.collections is not built_snapshot_b.collections
