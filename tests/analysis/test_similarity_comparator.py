"""Tests for `analysis/similarity/` (Sprint 9, Phase 4). Deterministic
comparison only — no recommendations/knowledge-graph/runtime/AI/
embeddings tests; those are later phases' own scope (or explicitly out of
scope entirely).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from analysis.contract import (
    Actor,
    AnalysisResult,
    BusinessConstraint,
    BusinessEntity,
    BusinessProcess,
    BusinessRule,
    GapAnalysis,
    SimilarityResult,
)
from analysis.erpnext.extractor import extract_doctype
from analysis.erpnext.metadata import RawDocType
from analysis.requirements.analyzer import build_analysis_result
from analysis.requirements.raw import RawEntityMention, RawRequirement
from analysis.similarity.comparator import (
    compare_actors,
    compare_analysis_result,
    compare_business_constraints,
    compare_business_entities,
    compare_business_processes,
    compare_business_rules,
    detect_actor_gaps,
    detect_business_constraint_gaps,
    detect_business_entity_gaps,
    detect_business_process_gaps,
    detect_business_rule_gaps,
)

ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "analysis"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "similarity"


def _load_fixture(name: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return result


def _subject_entities() -> tuple[BusinessEntity, ...]:
    return tuple(BusinessEntity.model_validate(item) for item in _load_fixture("subject_entities.json"))


def _candidate_entities() -> tuple[BusinessEntity, ...]:
    return tuple(BusinessEntity.model_validate(item) for item in _load_fixture("candidate_entities.json"))


# -- Business Entities: identical / partial / zero overlap, from real fixtures ----------------------


def test_identical_names_produce_maximum_similarity() -> None:
    results = compare_business_entities(_subject_entities(), _candidate_entities())
    by_pair = {(r.subject_id, r.candidate_reference): r for r in results}
    result = by_pair[("req:entity:Customer", "doctype:Customer")]
    assert result.similarity_score == 1.0


def test_partial_overlap_produces_a_deterministic_intermediate_score() -> None:
    results = compare_business_entities(_subject_entities(), _candidate_entities())
    by_pair = {(r.subject_id, r.candidate_reference): r for r in results}
    result = by_pair[("req:entity:Customer Account", "doctype:Customer")]
    # tokens {"customer", "account"} vs {"customer"} -> 1/2
    assert result.similarity_score == 0.5


def test_unrelated_structures_produce_minimum_similarity() -> None:
    results = compare_business_entities(_subject_entities(), _candidate_entities())
    by_pair = {(r.subject_id, r.candidate_reference): r for r in results}
    assert by_pair[("req:entity:Patient Record", "doctype:Customer")].similarity_score == 0.0
    assert by_pair[("req:entity:Patient Record", "doctype:Contact")].similarity_score == 0.0
    assert by_pair[("req:entity:Customer Account", "doctype:Contact")].similarity_score == 0.0
    assert by_pair[("req:entity:Customer", "doctype:Contact")].similarity_score == 0.0


def test_every_similarity_result_has_a_non_empty_rationale() -> None:
    results = compare_business_entities(_subject_entities(), _candidate_entities())
    assert all(result.rationale for result in results)


def test_comparison_ordering_is_deterministic_subject_major_candidate_minor() -> None:
    results = compare_business_entities(_subject_entities(), _candidate_entities())
    subjects = _subject_entities()
    candidates = _candidate_entities()
    expected_pairs = [
        (subject.entity_id, candidate.entity_id) for subject in subjects for candidate in candidates
    ]
    assert [(r.subject_id, r.candidate_reference) for r in results] == expected_pairs


def test_repeated_comparison_of_identical_input_is_deterministic() -> None:
    first = compare_business_entities(_subject_entities(), _candidate_entities())
    second = compare_business_entities(_subject_entities(), _candidate_entities())
    assert first == second


# -- Gap detection: deterministic, evidence-traceable ------------------------------------------------


def test_gap_analysis_is_deterministic_and_flags_only_zero_max_score_subjects() -> None:
    subjects = _subject_entities()
    results = compare_business_entities(subjects, _candidate_entities())
    gaps = detect_business_entity_gaps(subjects, results)
    assert {gap.subject_id for gap in gaps} == {"req:entity:Patient Record"}


def test_gap_analysis_reuses_the_subjects_own_evidence_never_fabricates_it() -> None:
    subjects = _subject_entities()
    results = compare_business_entities(subjects, _candidate_entities())
    gaps = detect_business_entity_gaps(subjects, results)
    patient_record = next(subject for subject in subjects if subject.entity_id == "req:entity:Patient Record")
    assert gaps[0].supporting_evidence == patient_record.supporting_evidence


def test_gap_analysis_with_no_candidates_at_all_flags_every_subject() -> None:
    subjects = _subject_entities()
    results = compare_business_entities(subjects, ())
    assert results == ()
    gaps = detect_business_entity_gaps(subjects, results)
    assert {gap.subject_id for gap in gaps} == {subject.entity_id for subject in subjects}


def test_gap_analysis_is_repeatable() -> None:
    subjects = _subject_entities()
    results = compare_business_entities(subjects, _candidate_entities())
    first = detect_business_entity_gaps(subjects, results)
    second = detect_business_entity_gaps(subjects, results)
    assert first == second


# -- Stable identifiers ---------------------------------------------------------------------------------


def test_subject_id_and_candidate_reference_are_the_originals_own_ids() -> None:
    results = compare_business_entities(_subject_entities(), _candidate_entities())
    subject_ids = {subject.entity_id for subject in _subject_entities()}
    candidate_ids = {candidate.entity_id for candidate in _candidate_entities()}
    assert {r.subject_id for r in results} <= subject_ids
    assert {r.candidate_reference for r in results} <= candidate_ids


# -- Edge cases -------------------------------------------------------------------------------------------


def test_whitespace_only_name_produces_zero_similarity_without_error() -> None:
    subject = BusinessEntity(entity_id="E-1", name=" ")
    candidate = BusinessEntity(entity_id="E-2", name=" ")
    results = compare_business_entities((subject,), (candidate,))
    assert results[0].similarity_score == 0.0


def test_empty_subjects_produce_no_results_and_no_gaps() -> None:
    assert compare_business_entities((), _candidate_entities()) == ()
    assert detect_business_entity_gaps((), ()) == ()


# -- Business Processes / Actors / Business Rules / Business Constraints ----------------------------


def test_compare_business_processes_identical_partial_and_zero() -> None:
    subjects = (
        BusinessProcess(process_id="P-1", name="Patient Registration"),
        BusinessProcess(process_id="P-2", name="Registration Workflow"),
    )
    candidates = (BusinessProcess(process_id="P-3", name="Registration Workflow"),)
    results = compare_business_processes(subjects, candidates)
    by_subject = {r.subject_id: r.similarity_score for r in results}
    assert by_subject["P-2"] == 1.0  # identical
    assert 0.0 < by_subject["P-1"] < 1.0  # shares "registration" only -> partial
    gaps = detect_business_process_gaps(subjects, results)
    assert gaps == ()  # both subjects share at least one term


def test_compare_actors_identical_and_gap() -> None:
    subjects = (Actor(actor_id="A-1", name="Receptionist"), Actor(actor_id="A-2", name="Ward Nurse"))
    candidates = (Actor(actor_id="A-3", name="Receptionist"),)
    results = compare_actors(subjects, candidates)
    by_subject = {r.subject_id: r.similarity_score for r in results}
    assert by_subject["A-1"] == 1.0
    assert by_subject["A-2"] == 0.0
    gaps = detect_actor_gaps(subjects, results)
    assert {gap.subject_id for gap in gaps} == {"A-2"}


def test_compare_business_rules_identical_and_gap() -> None:
    subjects = (
        BusinessRule(rule_id="R-1", statement="An invoice requires a confirmed appointment"),
        BusinessRule(rule_id="R-2", statement="Completely unrelated statement text"),
    )
    candidates = (BusinessRule(rule_id="R-3", statement="An invoice requires a confirmed appointment"),)
    results = compare_business_rules(subjects, candidates)
    by_subject = {r.subject_id: r.similarity_score for r in results}
    assert by_subject["R-1"] == 1.0
    assert by_subject["R-2"] == 0.0
    gaps = detect_business_rule_gaps(subjects, results)
    assert {gap.subject_id for gap in gaps} == {"R-2"}


def test_compare_business_constraints_identical_and_gap() -> None:
    subjects = (
        BusinessConstraint(constraint_id="C-1", statement="Only one active prescription per patient"),
        BusinessConstraint(constraint_id="C-2", statement="Zero overlap with anything else here"),
    )
    candidates = (
        BusinessConstraint(constraint_id="C-3", statement="Only one active prescription per patient"),
    )
    results = compare_business_constraints(subjects, candidates)
    by_subject = {r.subject_id: r.similarity_score for r in results}
    assert by_subject["C-1"] == 1.0
    assert by_subject["C-2"] == 0.0
    gaps = detect_business_constraint_gaps(subjects, results)
    assert {gap.subject_id for gap in gaps} == {"C-2"}


# -- compare_analysis_result: the Phase 2/3/4 end-to-end integration --------------------------------


def _requirement_with_a_customer_entity() -> AnalysisResult:
    raw = RawRequirement(
        requirement_id="REQ-1",
        description="Track patients and customers.",
        entities=(
            RawEntityMention(name="Patient Record", excerpt="track patient records"),
            RawEntityMention(name="Customer", excerpt="track customers"),
        ),
    )
    return build_analysis_result(raw)


def _erpnext_customer_entity() -> BusinessEntity:
    raw = RawDocType(name="Customer", module="Selling", description="A party that buys goods or services.")
    return extract_doctype(raw)


def test_compare_analysis_result_populates_previously_empty_fields() -> None:
    analysis_result = _requirement_with_a_customer_entity()
    assert analysis_result.similarity_results == ()
    assert analysis_result.gaps == ()

    compared = compare_analysis_result(analysis_result, erpnext_entities=(_erpnext_customer_entity(),))

    assert len(compared.similarity_results) == 2  # 2 subject entities x 1 candidate
    assert len(compared.gaps) == 1  # "Patient Record" shares nothing with "Customer"
    assert compared.gaps[0].subject_id == "REQ-1:entity:Patient Record"


def test_compare_analysis_result_returns_a_new_object_original_unmodified() -> None:
    analysis_result = _requirement_with_a_customer_entity()
    compare_analysis_result(analysis_result, erpnext_entities=(_erpnext_customer_entity(),))
    # The original, frozen AnalysisResult is never mutated in place.
    assert analysis_result.similarity_results == ()
    assert analysis_result.gaps == ()


def test_compare_analysis_result_preserves_the_requirement_analysis_unchanged() -> None:
    analysis_result = _requirement_with_a_customer_entity()
    compared = compare_analysis_result(analysis_result, erpnext_entities=(_erpnext_customer_entity(),))
    assert compared.requirement_analysis == analysis_result.requirement_analysis
    assert compared.analysis_id == analysis_result.analysis_id
    assert compared.requirement_id == analysis_result.requirement_id


def test_compare_analysis_result_with_no_erpnext_candidates_flags_every_subject_as_a_gap() -> None:
    analysis_result = _requirement_with_a_customer_entity()
    compared = compare_analysis_result(analysis_result)
    assert compared.similarity_results == ()
    assert len(compared.gaps) == 2


# -- Serialization ------------------------------------------------------------------------------------


def test_similarity_result_and_gap_analysis_round_trip_through_json() -> None:
    results = compare_business_entities(_subject_entities(), _candidate_entities())
    for result in results:
        assert SimilarityResult.model_validate_json(result.model_dump_json()) == result

    gaps = detect_business_entity_gaps(_subject_entities(), results)
    for gap in gaps:
        assert GapAnalysis.model_validate_json(gap.model_dump_json()) == gap


# -- Import boundary --------------------------------------------------------------------------------


def _direct_imports(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


_FORBIDDEN = {"intelligence", "planning", "execution", "runtime", "knowledge", "orchestration", "integration"}


def test_similarity_package_imports_none_of_the_forbidden_packages() -> None:
    violations = {
        str(py_file.relative_to(ANALYSIS_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN)
        for py_file in (ANALYSIS_DIR / "similarity").rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & _FORBIDDEN)
    }
    assert violations == {}


def test_similarity_package_has_no_network_or_ai_import() -> None:
    forbidden_extra = {"httpx", "requests", "urllib", "aiohttp", "anthropic", "openai"}
    violations = {
        str(py_file.relative_to(ANALYSIS_DIR)): sorted(_direct_imports(py_file) & forbidden_extra)
        for py_file in (ANALYSIS_DIR / "similarity").rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & forbidden_extra)
    }
    assert violations == {}


def test_comparator_module_imports_only_its_own_sibling_and_stdlib() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "similarity" / "comparator.py")
    assert imports <= {"__future__", "re", "analysis"}
