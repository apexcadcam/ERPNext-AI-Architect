"""Tests for `analysis/requirements/` (Sprint 9, Phase 3). Deterministic
requirement analysis only — no similarity/ERP-comparison/recommendation/
pipeline/runtime/AI tests; those are later phases' own scope.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from analysis.contract import (
    Actor,
    AnalysisResult,
    BusinessConstraint,
    BusinessEntity,
    BusinessProcess,
    BusinessRule,
    Requirement,
    RequirementAnalysis,
)
from analysis.requirements.analyzer import (
    analyze_actors,
    analyze_business_constraints,
    analyze_business_entities,
    analyze_business_processes,
    analyze_business_rules,
    analyze_requirement_statement,
    build_analysis_result,
    build_requirement_analysis,
)
from analysis.requirements.raw import (
    RawActorMention,
    RawConstraintMention,
    RawEntityMention,
    RawProcessMention,
    RawRequirement,
    RawRuleMention,
)

ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "analysis"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "requirements"


def _load_fixture(name: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return result


def _patient_tracking() -> RawRequirement:
    return RawRequirement.model_validate(_load_fixture("patient_tracking.json"))


def _bare() -> RawRequirement:
    return RawRequirement.model_validate(_load_fixture("bare_requirement.json"))


# -- analyze_requirement_statement -----------------------------------------------------------------


def test_analyze_requirement_statement_from_a_real_fixture() -> None:
    requirement = analyze_requirement_statement(_patient_tracking())
    assert requirement == Requirement(
        requirement_id="REQ-1",
        description="Track patient identity, appointments, and billing for the clinic.",
    )


def test_requirement_rejects_missing_description() -> None:
    with pytest.raises(ValidationError):
        RawRequirement.model_validate({"requirement_id": "REQ-1"})


def test_requirement_rejects_missing_requirement_id() -> None:
    with pytest.raises(ValidationError):
        RawRequirement.model_validate({"description": "x"})


# -- analyze_business_entities ----------------------------------------------------------------------


def test_analyze_business_entities_from_a_real_fixture() -> None:
    entities = analyze_business_entities(_patient_tracking())
    assert [entity.name for entity in entities] == ["Patient", "Appointment", "Invoice"]
    patient = entities[0]
    assert patient.entity_id == "REQ-1:entity:Patient"
    assert patient.attributes == ("date_of_birth", "medical_record_number")
    assert len(patient.supporting_evidence) == 1
    assert patient.supporting_evidence[0].excerpt == "we need to track patient identity"
    assert patient.supporting_evidence[0].source_reference == "REQ-1"


def test_analyze_business_entities_on_a_bare_requirement_is_empty() -> None:
    assert analyze_business_entities(_bare()) == ()


def test_entity_mention_rejects_missing_name() -> None:
    with pytest.raises(ValidationError):
        RawEntityMention.model_validate({"excerpt": "x"})


def test_entity_mention_rejects_missing_excerpt() -> None:
    # The structural guarantee behind "never fabricate evidence": no
    # entity mention can be constructed without a real excerpt to cite.
    with pytest.raises(ValidationError):
        RawEntityMention.model_validate({"name": "Patient"})


# -- analyze_actors -----------------------------------------------------------------------------------


def test_analyze_actors_from_a_real_fixture() -> None:
    actors = analyze_actors(_patient_tracking())
    assert [actor.name for actor in actors] == ["Receptionist", "Doctor"]
    assert actors[0].actor_id == "REQ-1:actor:Receptionist"
    assert actors[0].supporting_evidence[0].excerpt == "the receptionist registers a new patient"


def test_analyze_actors_on_a_bare_requirement_is_empty() -> None:
    assert analyze_actors(_bare()) == ()


def test_actor_mention_rejects_missing_excerpt() -> None:
    with pytest.raises(ValidationError):
        RawActorMention.model_validate({"name": "Receptionist"})


# -- analyze_business_processes --------------------------------------------------------------------


def test_analyze_business_processes_from_a_real_fixture() -> None:
    processes = analyze_business_processes(_patient_tracking())
    assert [process.name for process in processes] == ["Patient Registration", "Appointment Scheduling"]
    registration = processes[0]
    assert registration.process_id == "REQ-1:process:Patient Registration"
    # Declared step order preserved exactly.
    assert registration.steps == ("collect identity", "assign medical record number", "confirm insurance")
    assert registration.actor_ids == ("REQ-1:actor:Receptionist",)

    scheduling = processes[1]
    assert scheduling.actor_ids == ("REQ-1:actor:Receptionist", "REQ-1:actor:Doctor")


def test_process_actor_ids_use_the_identical_formula_analyze_actors_uses() -> None:
    # Cross-consistency: a process's actor_ids and analyze_actors()'s own
    # actor_id for the same name must be identical strings, so a consumer
    # can actually look one up from the other.
    raw = _patient_tracking()
    actors_by_name = {actor.name: actor.actor_id for actor in analyze_actors(raw)}
    processes = analyze_business_processes(raw)
    for process in processes:
        for actor_id in process.actor_ids:
            actor_name = actor_id.rsplit(":", 1)[-1]
            assert actors_by_name[actor_name] == actor_id


def test_analyze_business_processes_references_an_actor_not_separately_mentioned() -> None:
    # A process may cite an actor name with no matching RawActorMention --
    # a valid, merely-unresolved reference, never an error.
    raw = RawRequirement(
        requirement_id="REQ-X",
        description="x",
        processes=(RawProcessMention(name="Some Process", excerpt="x", actors=("Unmentioned Actor",)),),
    )
    processes = analyze_business_processes(raw)
    assert processes[0].actor_ids == ("REQ-X:actor:Unmentioned Actor",)
    assert analyze_actors(raw) == ()


def test_analyze_business_processes_on_a_bare_requirement_is_empty() -> None:
    assert analyze_business_processes(_bare()) == ()


def test_process_mention_rejects_missing_excerpt() -> None:
    with pytest.raises(ValidationError):
        RawProcessMention.model_validate({"name": "Patient Registration"})


# -- analyze_business_rules / analyze_business_constraints -----------------------------------------


def test_analyze_business_rules_from_a_real_fixture() -> None:
    rules = analyze_business_rules(_patient_tracking())
    assert len(rules) == 1
    assert rules[0].rule_id == "REQ-1:rule:0"
    assert rules[0].statement == "An invoice cannot be issued without a confirmed appointment"


def test_analyze_business_constraints_from_a_real_fixture() -> None:
    constraints = analyze_business_constraints(_patient_tracking())
    assert len(constraints) == 1
    assert constraints[0].constraint_id == "REQ-1:constraint:0"
    assert constraints[0].statement == "Only one active prescription per patient at a time"


def test_rule_ids_are_positional_and_stable() -> None:
    raw = RawRequirement(
        requirement_id="REQ-X",
        description="x",
        rules=(
            RawRuleMention(statement="first rule", excerpt="x"),
            RawRuleMention(statement="second rule", excerpt="y"),
        ),
    )
    rules = analyze_business_rules(raw)
    assert rules[0].rule_id == "REQ-X:rule:0"
    assert rules[1].rule_id == "REQ-X:rule:1"


def test_analyze_business_rules_and_constraints_on_a_bare_requirement_are_empty() -> None:
    assert analyze_business_rules(_bare()) == ()
    assert analyze_business_constraints(_bare()) == ()


def test_rule_mention_rejects_missing_statement() -> None:
    with pytest.raises(ValidationError):
        RawRuleMention.model_validate({"excerpt": "x"})


def test_constraint_mention_rejects_missing_excerpt() -> None:
    with pytest.raises(ValidationError):
        RawConstraintMention.model_validate({"statement": "x"})


# -- build_requirement_analysis / build_analysis_result --------------------------------------------


def test_build_requirement_analysis_from_a_real_fixture() -> None:
    analysis = build_requirement_analysis(_patient_tracking())
    assert analysis.requirement_id == "REQ-1"
    assert len(analysis.entities) == 3
    assert len(analysis.processes) == 2
    assert len(analysis.rules) == 1
    assert len(analysis.constraints) == 1
    assert len(analysis.actors) == 2
    assert isinstance(analysis, RequirementAnalysis)


def test_build_requirement_analysis_on_a_bare_requirement_is_all_empty() -> None:
    analysis = build_requirement_analysis(_bare())
    assert analysis == RequirementAnalysis(requirement_id="REQ-2")


def test_build_analysis_result_from_a_real_fixture() -> None:
    result = build_analysis_result(_patient_tracking())
    assert isinstance(result, AnalysisResult)
    assert result.analysis_id == "analysis:REQ-1"
    assert result.requirement_id == "REQ-1"
    assert result.requirement_analysis == build_requirement_analysis(_patient_tracking())


def test_build_analysis_result_never_populates_similarity_or_gaps() -> None:
    # Explicitly out of this phase's scope -- always empty here.
    result = build_analysis_result(_patient_tracking())
    assert result.similarity_results == ()
    assert result.gaps == ()


# -- Determinism, stability, and traceability ---------------------------------------------------------


def test_repeated_analysis_of_identical_input_is_deterministic() -> None:
    first = build_analysis_result(_patient_tracking())
    second = build_analysis_result(_patient_tracking())
    assert first == second


def test_identifiers_are_stable_across_separate_calls() -> None:
    first = analyze_business_entities(_patient_tracking())
    second = analyze_business_entities(_patient_tracking())
    assert [entity.entity_id for entity in first] == [entity.entity_id for entity in second]


def test_every_produced_evidence_excerpt_traces_back_to_the_input() -> None:
    raw = _patient_tracking()
    result = build_analysis_result(raw)
    all_input_excerpts = {mention.excerpt for mention in raw.entities}
    all_input_excerpts |= {mention.excerpt for mention in raw.processes}
    all_input_excerpts |= {mention.excerpt for mention in raw.actors}
    all_input_excerpts |= {mention.excerpt for mention in raw.rules}
    all_input_excerpts |= {mention.excerpt for mention in raw.constraints}

    produced_excerpts: set[str] = set()
    for entity in result.requirement_analysis.entities:
        produced_excerpts |= {evidence.excerpt for evidence in entity.supporting_evidence}
    for process in result.requirement_analysis.processes:
        produced_excerpts |= {evidence.excerpt for evidence in process.supporting_evidence}
    for actor in result.requirement_analysis.actors:
        produced_excerpts |= {evidence.excerpt for evidence in actor.supporting_evidence}
    for rule in result.requirement_analysis.rules:
        produced_excerpts |= {evidence.excerpt for evidence in rule.supporting_evidence}
    for constraint in result.requirement_analysis.constraints:
        produced_excerpts |= {evidence.excerpt for evidence in constraint.supporting_evidence}

    # No excerpt is ever produced that wasn't in the raw input --
    # nothing here is fabricated.
    assert produced_excerpts <= all_input_excerpts


def test_every_produced_evidence_cites_the_requirement_as_its_source() -> None:
    result = build_analysis_result(_patient_tracking())
    for entity in result.requirement_analysis.entities:
        for evidence in entity.supporting_evidence:
            assert evidence.source_reference == "REQ-1"


# -- Serialization ------------------------------------------------------------------------------------


def test_analysis_result_round_trips_through_json() -> None:
    result = build_analysis_result(_patient_tracking())
    restored = AnalysisResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_analysis_result_round_trips_through_dict() -> None:
    result = build_analysis_result(_patient_tracking())
    restored = AnalysisResult.model_validate(result.model_dump())
    assert restored == result


# -- Type correctness -----------------------------------------------------------------------------------


def test_every_analyzer_returns_the_correct_contract_type() -> None:
    raw = _patient_tracking()
    assert all(isinstance(entity, BusinessEntity) for entity in analyze_business_entities(raw))
    assert all(isinstance(process, BusinessProcess) for process in analyze_business_processes(raw))
    assert all(isinstance(actor, Actor) for actor in analyze_actors(raw))
    assert all(isinstance(rule, BusinessRule) for rule in analyze_business_rules(raw))
    assert all(isinstance(constraint, BusinessConstraint) for constraint in analyze_business_constraints(raw))
    assert isinstance(analyze_requirement_statement(raw), Requirement)


# -- Invalid structures rejected clearly -------------------------------------------------------------


def test_raw_requirement_rejects_a_malformed_entity_mention() -> None:
    with pytest.raises(ValidationError):
        RawRequirement.model_validate(
            {"requirement_id": "REQ-1", "description": "x", "entities": [{"excerpt": "no name here"}]}
        )


def test_raw_requirement_ignores_unmodeled_extra_fields() -> None:
    raw = RawRequirement.model_validate(
        {"requirement_id": "REQ-1", "description": "x", "some_future_field": {"nested": True}}
    )
    assert raw.requirement_id == "REQ-1"


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


def test_requirements_package_imports_none_of_the_forbidden_packages() -> None:
    violations = {
        str(py_file.relative_to(ANALYSIS_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN)
        for py_file in (ANALYSIS_DIR / "requirements").rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & _FORBIDDEN)
    }
    assert violations == {}


def test_requirements_package_has_no_network_or_ai_import() -> None:
    forbidden_extra = {"httpx", "requests", "urllib", "aiohttp", "anthropic", "openai"}
    violations = {
        str(py_file.relative_to(ANALYSIS_DIR)): sorted(_direct_imports(py_file) & forbidden_extra)
        for py_file in (ANALYSIS_DIR / "requirements").rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & forbidden_extra)
    }
    assert violations == {}


def test_analyzer_module_imports_only_its_own_sibling_and_stdlib() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "requirements" / "analyzer.py")
    assert imports <= {"__future__", "analysis"}


def test_raw_module_imports_only_stdlib_and_pydantic() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "requirements" / "raw.py")
    assert imports <= {"__future__", "pydantic"}
