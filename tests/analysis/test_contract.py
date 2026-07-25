"""Tests for `analysis/contract.py` (Sprint 9, Phase 1). Contracts only —
no extraction/similarity/ERPNext-parsing/LLM tests; those are later
phases' own scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis.contract import (
    Actor,
    AnalysisContext,
    AnalysisResult,
    BusinessConstraint,
    BusinessEntity,
    BusinessProcess,
    BusinessRule,
    GapAnalysis,
    Requirement,
    RequirementAnalysis,
    SimilarityResult,
    SupportingEvidence,
)

ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "analysis"


def _evidence(source_reference: str = "R-1") -> SupportingEvidence:
    return SupportingEvidence(
        source_reference=source_reference, excerpt="patients need tracking", rationale="x"
    )


# -- Requirement --------------------------------------------------------------------------------


def test_requirement_constructs_with_valid_data() -> None:
    requirement = Requirement(requirement_id="R-1", description="track patients")
    assert requirement.requirement_id == "R-1"
    assert requirement.description == "track patients"


def test_requirement_is_frozen() -> None:
    requirement = Requirement(requirement_id="R-1", description="x")
    with pytest.raises(ValidationError):
        requirement.description = "y"


def test_requirement_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Requirement(requirement_id="R-1", description="x", extra="y")  # type: ignore[call-arg]


def test_requirement_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        Requirement(requirement_id="", description="x")
    with pytest.raises(ValidationError):
        Requirement(requirement_id="R-1", description="")


# -- AnalysisContext ------------------------------------------------------------------------------


def test_analysis_context_constructs_with_valid_data() -> None:
    context = AnalysisContext(correlation_id="corr-1", requested_by="test-suite", environment="Development")
    assert context.correlation_id == "corr-1"
    assert context.requested_by == "test-suite"
    assert context.environment == "Development"


def test_analysis_context_is_frozen() -> None:
    context = AnalysisContext(correlation_id="corr-1", requested_by="x", environment="y")
    with pytest.raises(ValidationError):
        context.correlation_id = "corr-2"


def test_analysis_context_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnalysisContext(
            correlation_id="corr-1",
            requested_by="x",
            environment="y",
            extra="z",  # type: ignore[call-arg]
        )


def test_analysis_context_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        AnalysisContext(correlation_id="", requested_by="x", environment="y")
    with pytest.raises(ValidationError):
        AnalysisContext(correlation_id="corr-1", requested_by="", environment="y")
    with pytest.raises(ValidationError):
        AnalysisContext(correlation_id="corr-1", requested_by="x", environment="")


# -- SupportingEvidence ---------------------------------------------------------------------------


def test_supporting_evidence_constructs_with_valid_data() -> None:
    evidence = SupportingEvidence(source_reference="R-1", excerpt="patients need tracking", rationale="x")
    assert evidence.source_reference == "R-1"
    assert evidence.excerpt == "patients need tracking"
    assert evidence.rationale == "x"


def test_supporting_evidence_is_frozen() -> None:
    evidence = _evidence()
    with pytest.raises(ValidationError):
        evidence.excerpt = "y"


def test_supporting_evidence_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SupportingEvidence(
            source_reference="R-1",
            excerpt="x",
            rationale="y",
            extra="z",  # type: ignore[call-arg]
        )


def test_supporting_evidence_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        SupportingEvidence(source_reference="", excerpt="x", rationale="y")
    with pytest.raises(ValidationError):
        SupportingEvidence(source_reference="R-1", excerpt="", rationale="y")
    with pytest.raises(ValidationError):
        SupportingEvidence(source_reference="R-1", excerpt="x", rationale="")


# -- Actor ------------------------------------------------------------------------------------------


def test_actor_constructs_with_valid_data() -> None:
    actor = Actor(
        actor_id="A-1", name="Patient", description="the clinic patient", supporting_evidence=(_evidence(),)
    )
    assert actor.actor_id == "A-1"
    assert actor.name == "Patient"
    assert len(actor.supporting_evidence) == 1


def test_actor_defaults_are_empty() -> None:
    actor = Actor(actor_id="A-1", name="Patient")
    assert actor.description == ""
    assert actor.supporting_evidence == ()


def test_actor_is_frozen() -> None:
    actor = Actor(actor_id="A-1", name="Patient")
    with pytest.raises(ValidationError):
        actor.name = "Receptionist"


def test_actor_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Actor(actor_id="A-1", name="Patient", extra="x")  # type: ignore[call-arg]


def test_actor_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        Actor(actor_id="", name="Patient")
    with pytest.raises(ValidationError):
        Actor(actor_id="A-1", name="")


# -- BusinessEntity -----------------------------------------------------------------------------


def test_business_entity_constructs_with_valid_data() -> None:
    entity = BusinessEntity(
        entity_id="E-1",
        name="Patient",
        description="a clinic patient",
        attributes=("date_of_birth", "medical_record_number"),
        supporting_evidence=(_evidence(),),
    )
    assert entity.name == "Patient"
    assert entity.attributes == ("date_of_birth", "medical_record_number")


def test_business_entity_defaults_are_empty() -> None:
    entity = BusinessEntity(entity_id="E-1", name="Patient")
    assert entity.description == ""
    assert entity.attributes == ()
    assert entity.supporting_evidence == ()


def test_business_entity_is_frozen() -> None:
    entity = BusinessEntity(entity_id="E-1", name="Patient")
    with pytest.raises(ValidationError):
        entity.name = "Customer"


def test_business_entity_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BusinessEntity(entity_id="E-1", name="Patient", extra="x")  # type: ignore[call-arg]


def test_business_entity_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        BusinessEntity(entity_id="", name="Patient")
    with pytest.raises(ValidationError):
        BusinessEntity(entity_id="E-1", name="")


# -- BusinessProcess ----------------------------------------------------------------------------


def test_business_process_constructs_with_valid_data() -> None:
    process = BusinessProcess(
        process_id="P-1",
        name="Patient Registration",
        description="x",
        actor_ids=("A-1",),
        steps=("collect identity", "assign medical record number"),
        supporting_evidence=(_evidence(),),
    )
    assert process.name == "Patient Registration"
    assert process.actor_ids == ("A-1",)
    assert process.steps == ("collect identity", "assign medical record number")


def test_business_process_defaults_are_empty() -> None:
    process = BusinessProcess(process_id="P-1", name="Patient Registration")
    assert process.description == ""
    assert process.actor_ids == ()
    assert process.steps == ()
    assert process.supporting_evidence == ()


def test_business_process_is_frozen() -> None:
    process = BusinessProcess(process_id="P-1", name="x")
    with pytest.raises(ValidationError):
        process.name = "y"


def test_business_process_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BusinessProcess(process_id="P-1", name="x", extra="y")  # type: ignore[call-arg]


def test_business_process_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        BusinessProcess(process_id="", name="x")
    with pytest.raises(ValidationError):
        BusinessProcess(process_id="P-1", name="")


# -- BusinessRule -------------------------------------------------------------------------------


def test_business_rule_constructs_with_valid_data() -> None:
    rule = BusinessRule(
        rule_id="BR-1",
        statement="An invoice cannot be issued without a confirmed appointment",
        supporting_evidence=(_evidence(),),
    )
    assert rule.statement == "An invoice cannot be issued without a confirmed appointment"
    assert len(rule.supporting_evidence) == 1


def test_business_rule_defaults_are_empty() -> None:
    rule = BusinessRule(rule_id="BR-1", statement="x")
    assert rule.supporting_evidence == ()


def test_business_rule_is_frozen() -> None:
    rule = BusinessRule(rule_id="BR-1", statement="x")
    with pytest.raises(ValidationError):
        rule.statement = "y"


def test_business_rule_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BusinessRule(rule_id="BR-1", statement="x", extra="y")  # type: ignore[call-arg]


def test_business_rule_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        BusinessRule(rule_id="", statement="x")
    with pytest.raises(ValidationError):
        BusinessRule(rule_id="BR-1", statement="")


# -- BusinessConstraint --------------------------------------------------------------------------


def test_business_constraint_constructs_with_valid_data() -> None:
    constraint = BusinessConstraint(
        constraint_id="BC-1",
        statement="Only one active prescription per patient at a time",
        supporting_evidence=(_evidence(),),
    )
    assert constraint.statement == "Only one active prescription per patient at a time"


def test_business_constraint_defaults_are_empty() -> None:
    constraint = BusinessConstraint(constraint_id="BC-1", statement="x")
    assert constraint.supporting_evidence == ()


def test_business_constraint_is_frozen() -> None:
    constraint = BusinessConstraint(constraint_id="BC-1", statement="x")
    with pytest.raises(ValidationError):
        constraint.statement = "y"


def test_business_constraint_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BusinessConstraint(constraint_id="BC-1", statement="x", extra="y")  # type: ignore[call-arg]


def test_business_constraint_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        BusinessConstraint(constraint_id="", statement="x")
    with pytest.raises(ValidationError):
        BusinessConstraint(constraint_id="BC-1", statement="")


def test_business_rule_and_business_constraint_are_distinct_types() -> None:
    # Same content shape, deliberately distinct types -- see contract.py's
    # own docstring (mirrors Pattern/AntiPattern's established precedent).
    rule = BusinessRule(rule_id="X-1", statement="x")
    assert not isinstance(rule, BusinessConstraint)


# -- RequirementAnalysis -------------------------------------------------------------------------


def _requirement_analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        requirement_id="R-1",
        entities=(BusinessEntity(entity_id="E-1", name="Patient"),),
        processes=(BusinessProcess(process_id="P-1", name="Registration"),),
        rules=(BusinessRule(rule_id="BR-1", statement="x"),),
        constraints=(BusinessConstraint(constraint_id="BC-1", statement="y"),),
        actors=(Actor(actor_id="A-1", name="Patient"),),
    )


def test_requirement_analysis_constructs_with_valid_data() -> None:
    analysis = _requirement_analysis()
    assert analysis.requirement_id == "R-1"
    assert len(analysis.entities) == 1
    assert len(analysis.processes) == 1
    assert len(analysis.rules) == 1
    assert len(analysis.constraints) == 1
    assert len(analysis.actors) == 1


def test_requirement_analysis_defaults_are_empty() -> None:
    analysis = RequirementAnalysis(requirement_id="R-1")
    assert analysis.entities == ()
    assert analysis.processes == ()
    assert analysis.rules == ()
    assert analysis.constraints == ()
    assert analysis.actors == ()


def test_requirement_analysis_is_frozen() -> None:
    analysis = RequirementAnalysis(requirement_id="R-1")
    with pytest.raises(ValidationError):
        analysis.requirement_id = "R-2"


def test_requirement_analysis_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RequirementAnalysis(requirement_id="R-1", extra="x")  # type: ignore[call-arg]


def test_requirement_analysis_rejects_empty_requirement_id() -> None:
    with pytest.raises(ValidationError):
        RequirementAnalysis(requirement_id="")


# -- SimilarityResult -----------------------------------------------------------------------------


def test_similarity_result_constructs_with_valid_data() -> None:
    result = SimilarityResult(
        subject_id="E-1", candidate_reference="KA-0091", similarity_score=0.87, rationale="x"
    )
    assert result.similarity_score == 0.87


def test_similarity_result_is_frozen() -> None:
    result = SimilarityResult(
        subject_id="E-1", candidate_reference="KA-1", similarity_score=0.5, rationale="x"
    )
    with pytest.raises(ValidationError):
        result.similarity_score = 0.9


def test_similarity_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SimilarityResult(
            subject_id="E-1",
            candidate_reference="KA-1",
            similarity_score=0.5,
            rationale="x",
            extra="y",  # type: ignore[call-arg]
        )


def test_similarity_result_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        SimilarityResult(subject_id="", candidate_reference="KA-1", similarity_score=0.5, rationale="x")
    with pytest.raises(ValidationError):
        SimilarityResult(subject_id="E-1", candidate_reference="", similarity_score=0.5, rationale="x")
    with pytest.raises(ValidationError):
        SimilarityResult(subject_id="E-1", candidate_reference="KA-1", similarity_score=0.5, rationale="")


def test_similarity_score_out_of_bounds_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SimilarityResult(subject_id="E-1", candidate_reference="KA-1", similarity_score=1.1, rationale="x")
    with pytest.raises(ValidationError):
        SimilarityResult(subject_id="E-1", candidate_reference="KA-1", similarity_score=-0.1, rationale="x")


def test_similarity_score_boundary_values_are_accepted() -> None:
    SimilarityResult(subject_id="E-1", candidate_reference="KA-1", similarity_score=0.0, rationale="x")
    SimilarityResult(subject_id="E-1", candidate_reference="KA-1", similarity_score=1.0, rationale="x")


# -- GapAnalysis ----------------------------------------------------------------------------------


def test_gap_analysis_constructs_with_valid_data() -> None:
    gap = GapAnalysis(
        subject_id="E-2", description="no ERPNext-native equivalent found", supporting_evidence=(_evidence(),)
    )
    assert gap.description == "no ERPNext-native equivalent found"


def test_gap_analysis_defaults_are_empty() -> None:
    gap = GapAnalysis(subject_id="E-2", description="x")
    assert gap.supporting_evidence == ()


def test_gap_analysis_is_frozen() -> None:
    gap = GapAnalysis(subject_id="E-2", description="x")
    with pytest.raises(ValidationError):
        gap.description = "y"


def test_gap_analysis_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        GapAnalysis(subject_id="E-2", description="x", extra="y")  # type: ignore[call-arg]


def test_gap_analysis_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        GapAnalysis(subject_id="", description="x")
    with pytest.raises(ValidationError):
        GapAnalysis(subject_id="E-2", description="")


# -- AnalysisResult -------------------------------------------------------------------------------


def _analysis_result() -> AnalysisResult:
    return AnalysisResult(
        analysis_id="AN-1",
        requirement_id="R-1",
        requirement_analysis=_requirement_analysis(),
        similarity_results=(
            SimilarityResult(
                subject_id="E-1", candidate_reference="KA-0091", similarity_score=0.96, rationale="x"
            ),
        ),
        gaps=(GapAnalysis(subject_id="E-2", description="no native equivalent"),),
    )


def test_analysis_result_constructs_with_valid_data() -> None:
    result = _analysis_result()
    assert result.analysis_id == "AN-1"
    assert result.requirement_analysis.requirement_id == "R-1"
    assert len(result.similarity_results) == 1
    assert len(result.gaps) == 1


def test_analysis_result_defaults_are_empty() -> None:
    result = AnalysisResult(
        analysis_id="AN-1",
        requirement_id="R-1",
        requirement_analysis=RequirementAnalysis(requirement_id="R-1"),
    )
    assert result.similarity_results == ()
    assert result.gaps == ()


def test_analysis_result_is_frozen() -> None:
    result = _analysis_result()
    with pytest.raises(ValidationError):
        result.analysis_id = "AN-2"


def test_analysis_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult(
            analysis_id="AN-1",
            requirement_id="R-1",
            requirement_analysis=RequirementAnalysis(requirement_id="R-1"),
            extra="y",  # type: ignore[call-arg]
        )


def test_analysis_result_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult(
            analysis_id="",
            requirement_id="R-1",
            requirement_analysis=RequirementAnalysis(requirement_id="R-1"),
        )
    with pytest.raises(ValidationError):
        AnalysisResult(
            analysis_id="AN-1",
            requirement_id="",
            requirement_analysis=RequirementAnalysis(requirement_id="R-1"),
        )


def test_analysis_result_requires_a_requirement_analysis() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult(analysis_id="AN-1", requirement_id="R-1")  # type: ignore[call-arg]


# -- Equality and serialization ---------------------------------------------------------------------


def test_two_independently_constructed_equal_instances_compare_equal() -> None:
    assert _evidence() == _evidence()
    assert _requirement_analysis() == _requirement_analysis()
    assert _analysis_result() == _analysis_result()


def test_analysis_result_round_trips_through_dict() -> None:
    result = _analysis_result()
    restored = AnalysisResult.model_validate(result.model_dump())
    assert restored == result


def test_analysis_result_round_trips_through_json() -> None:
    result = _analysis_result()
    restored = AnalysisResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_repeated_construction_from_identical_input_is_deterministic() -> None:
    # No field on any type in this module derives from a clock, a random
    # source, or process-local state -- the same input always produces an
    # equal, never merely similar, result.
    first = _analysis_result()
    second = _analysis_result()
    assert first == second
    assert first.model_dump() == second.model_dump()


# -- No hidden nondeterminism: no clock/random/uuid import anywhere in this module ------------------


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


def test_contract_module_has_no_nondeterministic_import() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "contract.py")
    assert imports.isdisjoint({"datetime", "uuid", "random", "time"})


# -- Import boundary (light check; mirrors intelligence/contract.py's own Phase 1 check) -------------


def test_contract_module_imports_only_stdlib_and_pydantic() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "contract.py")
    assert imports <= {"__future__", "pydantic"}


def test_contract_module_imports_none_of_the_forbidden_packages() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "contract.py")
    forbidden = {
        "planning",
        "execution",
        "runtime",
        "knowledge",
        "intelligence",
        "orchestration",
        "integration",
    }
    assert imports.isdisjoint(forbidden)
