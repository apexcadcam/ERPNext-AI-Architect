"""Tests for `knowledge/builder/` (Sprint 10, Phase 2). Deterministic
transformation only — no persistence/indexing/querying/graph/runtime
tests; those are later phases' own scope (or explicitly out of scope).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis.contract import (
    Actor,
    AnalysisResult,
    BusinessConstraint,
    BusinessEntity,
    BusinessProcess,
    BusinessRule,
    RequirementAnalysis,
)
from knowledge.artifacts import Workflow
from knowledge.builder.builder import (
    build_actor_references,
    build_constraint_references,
    build_entity_references,
    build_knowledge_collection,
    build_knowledge_snapshot,
    build_process_references,
    build_rule_references,
    build_workflow_artifacts,
)
from knowledge.domain import KnowledgeCollection, KnowledgeSnapshot

BUILDER_DIR = Path(__file__).resolve().parents[3] / "knowledge" / "builder"
_CREATED_AT = "2026-01-01T00:00:00Z"


def _realistic_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        analysis_id="analysis:REQ-1",
        requirement_id="REQ-1",
        requirement_analysis=RequirementAnalysis(
            requirement_id="REQ-1",
            entities=(
                BusinessEntity(entity_id="REQ-1:entity:Patient", name="Patient"),
                BusinessEntity(entity_id="REQ-1:entity:Invoice", name="Invoice"),
            ),
            processes=(
                BusinessProcess(
                    process_id="REQ-1:process:Patient Registration",
                    name="Patient Registration",
                    steps=("collect identity", "assign medical record number"),
                ),
            ),
            rules=(
                BusinessRule(
                    rule_id="REQ-1:rule:0",
                    statement="An invoice cannot be issued without a confirmed appointment",
                ),
            ),
            constraints=(
                BusinessConstraint(
                    constraint_id="REQ-1:constraint:0",
                    statement="Only one active prescription per patient at a time",
                ),
            ),
            actors=(Actor(actor_id="REQ-1:actor:Receptionist", name="Receptionist"),),
        ),
    )


def _empty_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        analysis_id="analysis:REQ-2",
        requirement_id="REQ-2",
        requirement_analysis=RequirementAnalysis(requirement_id="REQ-2"),
    )


# -- build_knowledge_snapshot: the full, realistic case --------------------------------------------


def test_build_knowledge_snapshot_from_a_realistic_analysis_result() -> None:
    result = _realistic_analysis_result()
    snapshot = build_knowledge_snapshot(result, created_at=_CREATED_AT)

    assert isinstance(snapshot, KnowledgeSnapshot)
    assert snapshot.snapshot_id == "snapshot:analysis:REQ-1"
    assert snapshot.created_at == _CREATED_AT
    assert snapshot.source is result
    assert len(snapshot.collections) == 1

    collection = snapshot.collections[0]
    assert collection.collection_id == "collection:analysis:REQ-1"
    assert collection.name == "REQ-1"
    # One Workflow artifact (from the one BusinessProcess) -- the only
    # fact kind with a genuine ContentArtifact fit.
    assert len(collection.artifacts) == 1
    assert isinstance(collection.artifacts[0], Workflow)
    # 2 entities + 1 process + 1 rule + 1 constraint + 1 actor = 6 references.
    assert len(collection.references) == 6
    assert collection.nodes == ()
    assert collection.edges == ()


def test_build_workflow_artifacts_maps_business_process_fields_correctly() -> None:
    result = _realistic_analysis_result()
    workflows = build_workflow_artifacts(result, created_at=_CREATED_AT)

    assert len(workflows) == 1
    workflow = workflows[0]
    assert workflow.id == "WF-REQ-1:process:Patient Registration"
    assert workflow.content.title == "Patient Registration"
    assert [step.description for step in workflow.content.steps] == [
        "collect identity",
        "assign medical record number",
    ]
    # Declared step order preserved exactly, numbered from zero.
    assert [step.order for step in workflow.content.steps] == [0, 1]
    assert workflow.metadata.extracted_at == _CREATED_AT
    # Never fabricated: no confidence claim, no status claim, no source
    # references, no provenance, no relationships -- all left at their
    # honest, unvalidated defaults.
    assert workflow.confidence == 0.0
    assert workflow.source_references == ()
    assert workflow.provenance == ()
    assert workflow.dependencies == ()
    assert workflow.relationships == ()


def test_build_workflow_artifacts_on_a_process_with_no_steps() -> None:
    result = AnalysisResult(
        analysis_id="analysis:REQ-3",
        requirement_id="REQ-3",
        requirement_analysis=RequirementAnalysis(
            requirement_id="REQ-3",
            processes=(BusinessProcess(process_id="REQ-3:process:Bare", name="Bare"),),
        ),
    )
    workflows = build_workflow_artifacts(result, created_at=_CREATED_AT)
    assert workflows[0].content.steps == ()


# -- Per-kind reference builders --------------------------------------------------------------


def test_build_entity_references() -> None:
    result = _realistic_analysis_result()
    references = build_entity_references(result)
    assert [reference.subject_id for reference in references] == [
        "REQ-1:entity:Patient",
        "REQ-1:entity:Invoice",
    ]
    assert all(reference.subject_kind == "business_entity" for reference in references)
    assert all(reference.analysis_id == "analysis:REQ-1" for reference in references)


def test_build_process_references() -> None:
    references = build_process_references(_realistic_analysis_result())
    assert references[0].subject_id == "REQ-1:process:Patient Registration"
    assert references[0].subject_kind == "business_process"


def test_build_rule_references() -> None:
    references = build_rule_references(_realistic_analysis_result())
    assert references[0].subject_id == "REQ-1:rule:0"
    assert references[0].subject_kind == "business_rule"


def test_build_constraint_references() -> None:
    references = build_constraint_references(_realistic_analysis_result())
    assert references[0].subject_id == "REQ-1:constraint:0"
    assert references[0].subject_kind == "business_constraint"


def test_build_actor_references() -> None:
    references = build_actor_references(_realistic_analysis_result())
    assert references[0].subject_id == "REQ-1:actor:Receptionist"
    assert references[0].subject_kind == "actor"


# -- Empty AnalysisResult -----------------------------------------------------------------------


def test_empty_analysis_result_produces_an_empty_but_valid_collection() -> None:
    snapshot = build_knowledge_snapshot(_empty_analysis_result(), created_at=_CREATED_AT)
    collection = snapshot.collections[0]
    assert collection.artifacts == ()
    assert collection.references == ()
    assert collection.nodes == ()
    assert collection.edges == ()


# -- Large AnalysisResult -----------------------------------------------------------------------


def test_large_analysis_result_is_handled_completely() -> None:
    entities = tuple(BusinessEntity(entity_id=f"REQ-4:entity:E{i}", name=f"Entity {i}") for i in range(200))
    processes = tuple(
        BusinessProcess(process_id=f"REQ-4:process:P{i}", name=f"Process {i}", steps=(f"step {i}",))
        for i in range(200)
    )
    result = AnalysisResult(
        analysis_id="analysis:REQ-4",
        requirement_id="REQ-4",
        requirement_analysis=RequirementAnalysis(
            requirement_id="REQ-4", entities=entities, processes=processes
        ),
    )

    collection = build_knowledge_collection(result, created_at=_CREATED_AT)

    assert len(collection.artifacts) == 200
    assert len([r for r in collection.references if r.subject_kind == "business_entity"]) == 200
    assert len([r for r in collection.references if r.subject_kind == "business_process"]) == 200


# -- Deterministic output / idempotency ----------------------------------------------------------


def test_deterministic_output_repeated_calls_produce_equal_results() -> None:
    result = _realistic_analysis_result()
    first = build_knowledge_snapshot(result, created_at=_CREATED_AT)
    second = build_knowledge_snapshot(result, created_at=_CREATED_AT)
    assert first == second


def test_idempotent_byte_for_byte_across_repeated_calls() -> None:
    result = _realistic_analysis_result()
    first = build_knowledge_snapshot(result, created_at=_CREATED_AT)
    second = build_knowledge_snapshot(result, created_at=_CREATED_AT)
    assert first.model_dump_json() == second.model_dump_json()


def test_deterministic_across_two_independently_constructed_equal_inputs() -> None:
    # Not just "the same object called twice" -- two separately built,
    # value-equal AnalysisResult instances must also converge.
    first = build_knowledge_snapshot(_realistic_analysis_result(), created_at=_CREATED_AT)
    second = build_knowledge_snapshot(_realistic_analysis_result(), created_at=_CREATED_AT)
    assert first == second


# -- Duplicate handling: preserved, never merged -------------------------------------------------


def test_duplicate_entities_are_preserved_not_merged() -> None:
    result = AnalysisResult(
        analysis_id="analysis:REQ-5",
        requirement_id="REQ-5",
        requirement_analysis=RequirementAnalysis(
            requirement_id="REQ-5",
            entities=(
                BusinessEntity(entity_id="REQ-5:entity:Patient", name="Patient"),
                BusinessEntity(entity_id="REQ-5:entity:Patient", name="Patient"),
            ),
        ),
    )
    references = build_entity_references(result)
    # Two mentions in, two references out -- no deduplication/inference.
    assert len(references) == 2
    assert references[0] == references[1]


# -- Provenance preservation ----------------------------------------------------------------------


def test_every_reference_traces_back_to_the_source_analysis_id() -> None:
    result = _realistic_analysis_result()
    collection = build_knowledge_collection(result, created_at=_CREATED_AT)
    assert all(reference.analysis_id == result.analysis_id for reference in collection.references)


def test_snapshot_embeds_the_exact_source_analysis_result() -> None:
    result = _realistic_analysis_result()
    snapshot = build_knowledge_snapshot(result, created_at=_CREATED_AT)
    assert snapshot.source is result


# -- Serialization --------------------------------------------------------------------------------


def test_knowledge_snapshot_round_trips_through_json() -> None:
    snapshot = build_knowledge_snapshot(_realistic_analysis_result(), created_at=_CREATED_AT)
    restored = KnowledgeSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored == snapshot


def test_knowledge_collection_round_trips_through_dict() -> None:
    collection = build_knowledge_collection(_realistic_analysis_result(), created_at=_CREATED_AT)
    restored = KnowledgeCollection.model_validate(collection.model_dump())
    assert restored == collection


# -- Invalid input ---------------------------------------------------------------------------------


def test_empty_created_at_is_rejected_clearly() -> None:
    with pytest.raises(ValidationError):
        build_knowledge_snapshot(_realistic_analysis_result(), created_at="")


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


_FORBIDDEN = {"intelligence", "planning", "execution", "runtime", "orchestration", "integration"}


def test_builder_package_imports_none_of_the_forbidden_packages() -> None:
    violations = {
        str(py_file.relative_to(BUILDER_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN)
        for py_file in BUILDER_DIR.rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & _FORBIDDEN)
    }
    assert violations == {}


def test_builder_module_imports_only_expected_modules() -> None:
    imports = _direct_imports(BUILDER_DIR / "builder.py")
    assert imports <= {"__future__", "analysis", "knowledge"}


def test_builder_has_no_vendor_sdk_network_or_graph_database_import() -> None:
    forbidden_extra = {
        "httpx",
        "requests",
        "urllib",
        "aiohttp",
        "anthropic",
        "openai",
        "neo4j",
        "rdflib",
        "networkx",
        "sqlalchemy",
        "pymongo",
        "redis",
    }
    imports = _direct_imports(BUILDER_DIR / "builder.py")
    assert imports.isdisjoint(forbidden_extra)
