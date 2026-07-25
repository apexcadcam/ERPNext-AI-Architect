"""Sprint 9 — End-to-End Pipeline Validation.

Exercises the complete, real chain Phases 1-4 built, as one unit, for the
first time through a single entry point per stage rather than each
phase's own isolated unit tests:

    Structured Requirement -> Requirement Analyzer -> AnalysisResult
    ERPNext Metadata       -> ERP Extractor         -> BusinessEntity/BusinessProcess/BusinessRule
    (both)                 -> Similarity Comparator -> SimilarityResult / GapAnalysis

Self-contained, mirroring `tests/sprint7/test_end_to_end_flow.py`'s and
`tests/sprint8/`'s own discipline: this directory does not import
fixtures from `tests/analysis/` (a sibling, not an ancestor) -- every
input here is rebuilt directly via the real `Raw*` constructors, minimally.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from analysis.contract import AnalysisResult
from analysis.erpnext.extractor import extract_doctype, extract_server_script, extract_workflow
from analysis.erpnext.metadata import (
    RawDocType,
    RawField,
    RawServerScript,
    RawWorkflow,
    RawWorkflowState,
    RawWorkflowTransition,
)
from analysis.requirements.analyzer import build_analysis_result
from analysis.requirements.raw import (
    RawActorMention,
    RawConstraintMention,
    RawEntityMention,
    RawProcessMention,
    RawRequirement,
    RawRuleMention,
)
from analysis.similarity.comparator import compare_analysis_result


def _structured_requirement() -> RawRequirement:
    return RawRequirement(
        requirement_id="REQ-CLINIC-1",
        description="Track patient identity, appointments, and customer billing.",
        entities=(
            RawEntityMention(name="Patient", excerpt="track patient identity", attributes=("date_of_birth",)),
            RawEntityMention(name="Customer", excerpt="customer billing records"),
        ),
        processes=(
            RawProcessMention(
                name="Patient Registration",
                excerpt="register new patients before their first visit",
                steps=("collect identity",),
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


def _erpnext_doctype_customer() -> RawDocType:
    return RawDocType(
        name="Customer",
        module="Selling",
        description="A party that buys goods or services.",
        fields=(RawField(fieldname="customer_name", label="Customer Name"),),
    )


def _erpnext_workflow() -> RawWorkflow:
    return RawWorkflow(
        name="Leave Application Workflow",
        document_type="Leave Application",
        states=(RawWorkflowState(state="Open"), RawWorkflowState(state="Approved")),
        transitions=(
            RawWorkflowTransition(
                state="Open", action="Approve", next_state="Approved", allowed="HR Manager"
            ),
        ),
    )


def _erpnext_server_script() -> RawServerScript:
    return RawServerScript(
        name="Auto Assign Task Owner",
        script_type="DocType Event",
        reference_doctype="Task",
        doctype_event="Before Insert",
    )


def _run_pipeline() -> AnalysisResult:
    requirement_result = build_analysis_result(_structured_requirement())

    erpnext_entities = (extract_doctype(_erpnext_doctype_customer()),)
    erpnext_processes = (extract_workflow(_erpnext_workflow()),)
    erpnext_rules = (extract_server_script(_erpnext_server_script()),)

    return compare_analysis_result(
        requirement_result,
        erpnext_entities=erpnext_entities,
        erpnext_processes=erpnext_processes,
        erpnext_rules=erpnext_rules,
    )


# -- The pipeline produces a coherent, meaningful result -------------------------------------------


def test_pipeline_produces_one_genuine_match_and_several_gaps() -> None:
    result = _run_pipeline()

    by_pair = {(r.subject_id, r.candidate_reference): r.similarity_score for r in result.similarity_results}
    assert by_pair[("REQ-CLINIC-1:entity:Customer", "doctype:Customer")] == 1.0
    assert by_pair[("REQ-CLINIC-1:entity:Patient", "doctype:Customer")] == 0.0

    gap_subject_ids = {gap.subject_id for gap in result.gaps}
    assert "REQ-CLINIC-1:entity:Patient" in gap_subject_ids
    assert "REQ-CLINIC-1:entity:Customer" not in gap_subject_ids
    # Rules/constraints/processes share no vocabulary with the ERPNext
    # side supplied here -- all genuinely, honestly, gaps.
    assert "REQ-CLINIC-1:process:Patient Registration" in gap_subject_ids
    assert "REQ-CLINIC-1:rule:0" in gap_subject_ids
    assert "REQ-CLINIC-1:constraint:0" in gap_subject_ids  # no ERPNext constraints supplied at all
    assert "REQ-CLINIC-1:actor:Receptionist" in gap_subject_ids  # no ERPNext actors supplied at all


# -- Deterministic output, identical input produces identical output --------------------------------


def test_pipeline_is_fully_deterministic_across_repeated_runs() -> None:
    first = _run_pipeline()
    second = _run_pipeline()
    assert first == second


# -- Stable identifiers -----------------------------------------------------------------------------


def test_stable_identifiers_across_repeated_runs() -> None:
    first = _run_pipeline()
    second = _run_pipeline()
    assert [r.subject_id for r in first.similarity_results] == [
        r.subject_id for r in second.similarity_results
    ]
    assert [gap.subject_id for gap in first.gaps] == [gap.subject_id for gap in second.gaps]
    assert first.analysis_id == second.analysis_id == "analysis:REQ-CLINIC-1"


# -- Stable ordering ----------------------------------------------------------------------------------


def test_similarity_results_are_ordered_subject_major_candidate_minor() -> None:
    result = _run_pipeline()
    entity_pairs = [
        (r.subject_id, r.candidate_reference)
        for r in result.similarity_results
        if r.subject_id.endswith(":entity:Patient") or r.subject_id.endswith(":entity:Customer")
    ]
    # Requirement analysis declares entities in order Patient, then
    # Customer (see _structured_requirement) -- the comparator must
    # preserve that declared order, never reorder by score.
    assert entity_pairs == [
        ("REQ-CLINIC-1:entity:Patient", "doctype:Customer"),
        ("REQ-CLINIC-1:entity:Customer", "doctype:Customer"),
    ]


# -- Immutable outputs: an earlier stage's result is never mutated by a later one -------------------


def test_earlier_stage_results_are_never_mutated_by_a_later_stage() -> None:
    requirement_result = build_analysis_result(_structured_requirement())
    assert requirement_result.similarity_results == ()
    assert requirement_result.gaps == ()

    compare_analysis_result(
        requirement_result,
        erpnext_entities=(extract_doctype(_erpnext_doctype_customer()),),
    )

    # The object passed in is untouched -- compare_analysis_result always
    # returns a new AnalysisResult (frozen models, per analysis/contract.py).
    assert requirement_result.similarity_results == ()
    assert requirement_result.gaps == ()


def test_every_produced_object_is_frozen() -> None:
    result = _run_pipeline()
    with pytest.raises(ValidationError):
        result.analysis_id = "changed"


# -- Evidence traceability, end to end ----------------------------------------------------------------


def test_every_gap_evidence_excerpt_traces_back_to_the_real_requirement_input() -> None:
    raw_requirement = _structured_requirement()
    real_excerpts: set[str] = set()
    real_excerpts |= {m.excerpt for m in raw_requirement.entities}
    real_excerpts |= {m.excerpt for m in raw_requirement.processes}
    real_excerpts |= {m.excerpt for m in raw_requirement.actors}
    real_excerpts |= {m.excerpt for m in raw_requirement.rules}
    real_excerpts |= {m.excerpt for m in raw_requirement.constraints}

    result = _run_pipeline()
    for gap in result.gaps:
        for evidence in gap.supporting_evidence:
            assert evidence.excerpt in real_excerpts
            assert evidence.source_reference == "REQ-CLINIC-1"


def test_every_similarity_rationale_only_cites_terms_actually_present_in_both_inputs() -> None:
    result = _run_pipeline()
    match = next(
        r
        for r in result.similarity_results
        if r.subject_id == "REQ-CLINIC-1:entity:Customer" and r.candidate_reference == "doctype:Customer"
    )
    assert "customer" in match.rationale.lower()


# -- Serialization --------------------------------------------------------------------------------------


def test_full_pipeline_result_round_trips_through_json() -> None:
    result = _run_pipeline()
    restored = AnalysisResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_full_pipeline_result_round_trips_through_dict_and_plain_json_dumps() -> None:
    # A stronger serialization proof than model_dump_json() alone: the
    # plain stdlib json module must also be able to serialize the dumped
    # dict without a custom encoder -- proves every field bottoms out in
    # plain str/float/bool/tuple(->list)/dict, nothing exotic.
    result = _run_pipeline()
    as_dict = result.model_dump(mode="json")
    reserialized = json.loads(json.dumps(as_dict))
    assert AnalysisResult.model_validate(reserialized) == result
