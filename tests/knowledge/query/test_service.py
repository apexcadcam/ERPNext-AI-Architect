"""Tests for `knowledge/query/` (Sprint 10, Phase 4). Deterministic,
read-only, in-memory querying only — no persistence/indexing/caching/
graph-traversal/AI tests; those are out of this phase's scope entirely.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from analysis.contract import AnalysisResult, RequirementAnalysis
from knowledge.artifacts import (
    ArtifactMetadata,
    ArtifactType,
    ArtifactVersionInfo,
    KnowledgeAPI,
    KnowledgeAPIContent,
    RelationshipType,
    Workflow,
    WorkflowContent,
)
from knowledge.domain import KnowledgeCollection, KnowledgeReference, KnowledgeSnapshot, KnowledgeStatistics
from knowledge.graph import GraphEdge, GraphNode
from knowledge.query.service import KnowledgeQueryService

QUERY_DIR = Path(__file__).resolve().parents[3] / "knowledge" / "query"
_CREATED_AT = "2026-01-01T00:00:00Z"


def _metadata() -> ArtifactMetadata:
    return ArtifactMetadata(extracted_at=_CREATED_AT, extraction_method="test", extractor_version="0.1.0")


def _workflow(artifact_id: str = "WF-1") -> Workflow:
    return Workflow(
        id=artifact_id,
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=WorkflowContent(title="Patient Registration", steps=()),
    )


def _knowledge_api(artifact_id: str = "KA-1") -> KnowledgeAPI:
    return KnowledgeAPI(
        id=artifact_id,
        type=ArtifactType.KNOWLEDGE_API,
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=KnowledgeAPIContent(interface_kind="doctype-field", name="customer_name"),
    )


def _node(node_id: str = "KG-WF-1", wraps: str = "WF-1") -> GraphNode:
    return GraphNode(node_id=node_id, wraps=wraps, wraps_type=ArtifactType.WORKFLOW)


def _edge() -> GraphEdge:
    return GraphEdge(
        source_node_id="KG-WF-1", relationship=RelationshipType.DEPENDS_ON, target_node_id="KG-KA-1"
    )


def _reference(
    subject_id: str = "REQ-1:entity:Patient", subject_kind: str = "business_entity"
) -> KnowledgeReference:
    return KnowledgeReference(analysis_id="analysis:REQ-1", subject_id=subject_id, subject_kind=subject_kind)  # type: ignore[arg-type]


def _collection(**overrides: object) -> KnowledgeCollection:
    defaults: dict[str, object] = {"collection_id": "COL-1", "name": "REQ-1"}
    defaults.update(overrides)
    return KnowledgeCollection(**defaults)  # type: ignore[arg-type]


def _analysis_result() -> AnalysisResult:
    return AnalysisResult(
        analysis_id="analysis:REQ-1",
        requirement_id="REQ-1",
        requirement_analysis=RequirementAnalysis(requirement_id="REQ-1"),
    )


def _snapshot(*collections: KnowledgeCollection) -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        snapshot_id="SNAP-1", created_at=_CREATED_AT, source=_analysis_result(), collections=collections
    )


def _full_collection() -> KnowledgeCollection:
    return _collection(
        artifacts=(_workflow("WF-1"), _knowledge_api("KA-1")),
        nodes=(_node(), GraphNode(node_id="KG-KA-1", wraps="KA-1", wraps_type=ArtifactType.KNOWLEDGE_API)),
        edges=(_edge(),),
        references=(_reference(), _reference(subject_id="REQ-1:actor:Receptionist", subject_kind="actor")),
    )


# -- Collections ----------------------------------------------------------------------------------


def test_list_collections_returns_declared_order() -> None:
    service = KnowledgeQueryService(
        _snapshot(_collection(collection_id="COL-1"), _collection(collection_id="COL-2"))
    )
    assert [c.collection_id for c in service.list_collections()] == ["COL-1", "COL-2"]


def test_find_collection_success() -> None:
    service = KnowledgeQueryService(_snapshot(_collection(collection_id="COL-1")))
    assert service.find_collection("COL-1") is not None


def test_find_collection_failure_returns_none() -> None:
    service = KnowledgeQueryService(_snapshot(_collection(collection_id="COL-1")))
    assert service.find_collection("NOPE") is None


# -- Artifacts --------------------------------------------------------------------------------------


def test_list_artifacts_across_all_collections() -> None:
    service = KnowledgeQueryService(
        _snapshot(
            _collection(collection_id="COL-1", artifacts=(_workflow("WF-1"),)),
            _collection(collection_id="COL-2", artifacts=(_knowledge_api("KA-1"),)),
        )
    )
    assert {artifact.id for artifact in service.list_artifacts()} == {"WF-1", "KA-1"}


def test_list_artifacts_scoped_to_one_collection() -> None:
    service = KnowledgeQueryService(
        _snapshot(
            _collection(collection_id="COL-1", artifacts=(_workflow("WF-1"),)),
            _collection(collection_id="COL-2", artifacts=(_knowledge_api("KA-1"),)),
        )
    )
    assert [a.id for a in service.list_artifacts(collection_id="COL-1")] == ["WF-1"]


def test_list_artifacts_scoped_to_a_missing_collection_is_empty() -> None:
    service = KnowledgeQueryService(_snapshot(_collection()))
    assert service.list_artifacts(collection_id="NOPE") == ()


def test_find_artifact_success() -> None:
    service = KnowledgeQueryService(_snapshot(_collection(artifacts=(_workflow("WF-1"),))))
    artifact = service.find_artifact("WF-1")
    assert artifact is not None
    assert artifact.id == "WF-1"


def test_find_artifact_failure_returns_none() -> None:
    service = KnowledgeQueryService(_snapshot(_collection(artifacts=(_workflow("WF-1"),))))
    assert service.find_artifact("NOPE") is None


def test_find_artifact_with_duplicates_returns_the_first_in_declared_order() -> None:
    first = _workflow("WF-1")
    service = KnowledgeQueryService(
        _snapshot(
            _collection(collection_id="COL-1", artifacts=(first,)),
            _collection(collection_id="COL-2", artifacts=(_workflow("WF-1"),)),
        )
    )
    assert service.find_artifact("WF-1") is first


# -- Nodes / edges ------------------------------------------------------------------------------------


def test_list_nodes_across_all_collections() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    assert {node.node_id for node in service.list_nodes()} == {"KG-WF-1", "KG-KA-1"}


def test_list_nodes_scoped_to_one_collection() -> None:
    service = KnowledgeQueryService(
        _snapshot(_collection(collection_id="COL-1", nodes=(_node(),)), _collection(collection_id="COL-2"))
    )
    assert [n.node_id for n in service.list_nodes(collection_id="COL-2")] == []


def test_find_node_success_and_failure() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    assert service.find_node("KG-WF-1") is not None
    assert service.find_node("NOPE") is None


def test_list_edges() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    assert service.list_edges() == (_edge(),)


def test_list_edges_scoped_to_a_missing_collection_is_empty() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    assert service.list_edges(collection_id="NOPE") == ()


# -- References -----------------------------------------------------------------------------------------


def test_list_references_no_filter() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    assert len(service.list_references()) == 2


def test_list_references_filtered_by_subject_kind() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    references = service.list_references(subject_kind="actor")
    assert len(references) == 1
    assert references[0].subject_kind == "actor"


def test_list_references_filtered_by_subject_id() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    references = service.list_references(subject_id="REQ-1:entity:Patient")
    assert len(references) == 1


def test_list_references_filtered_by_analysis_id() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    assert len(service.list_references(analysis_id="analysis:REQ-1")) == 2
    assert service.list_references(analysis_id="analysis:OTHER") == ()


def test_list_references_combined_filters() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    references = service.list_references(subject_kind="business_entity", subject_id="REQ-1:entity:Patient")
    assert len(references) == 1


def test_list_references_unknown_subject_kind_raises_value_error() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    with pytest.raises(ValueError, match="not a recognized subject_kind"):
        service.list_references(subject_kind="not_a_real_kind")


# -- Duplicate handling: references with the same subject_id, both preserved -----------------------


def test_list_references_duplicate_subject_ids_are_both_returned() -> None:
    duplicate = _reference()
    collection = _collection(references=(duplicate, duplicate))
    service = KnowledgeQueryService(_snapshot(collection))
    references = service.list_references(subject_id="REQ-1:entity:Patient")
    assert len(references) == 2


# -- Statistics -------------------------------------------------------------------------------------------


def test_statistics_success() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    stats = service.statistics("COL-1")
    assert stats is not None
    assert stats.artifact_count == 2
    assert stats.node_count == 2
    assert stats.relationship_count == 1
    assert stats.counts_by_artifact_type == {"workflow": 1, "knowledge_api": 1}


def test_statistics_failure_returns_none() -> None:
    service = KnowledgeQueryService(_snapshot(_collection()))
    assert service.statistics("NOPE") is None


def test_list_statistics_one_per_collection_in_order() -> None:
    service = KnowledgeQueryService(
        _snapshot(
            _collection(collection_id="COL-1"), _collection(collection_id="COL-2", artifacts=(_workflow(),))
        )
    )
    all_stats = service.list_statistics()
    assert [s.collection_id for s in all_stats] == ["COL-1", "COL-2"]
    assert all_stats[1].artifact_count == 1


# -- Empty knowledge --------------------------------------------------------------------------------------


def test_empty_snapshot_every_query_returns_empty() -> None:
    service = KnowledgeQueryService(_snapshot())
    assert service.list_collections() == ()
    assert service.list_artifacts() == ()
    assert service.list_nodes() == ()
    assert service.list_edges() == ()
    assert service.list_references() == ()
    assert service.list_statistics() == ()


def test_empty_collection_every_query_returns_empty() -> None:
    service = KnowledgeQueryService(_snapshot(_collection()))
    assert service.list_artifacts() == ()
    stats = service.statistics("COL-1")
    assert stats is not None
    assert stats.artifact_count == 0


# -- Determinism and read-only behavior --------------------------------------------------------------


def test_repeated_queries_over_identical_knowledge_are_deterministic() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    assert service.list_artifacts() == service.list_artifacts()
    assert service.list_references() == service.list_references()
    assert service.statistics("COL-1") == service.statistics("COL-1")


def test_service_never_mutates_the_snapshot() -> None:
    snapshot = _snapshot(_full_collection())
    before = copy.deepcopy(snapshot.model_dump())
    service = KnowledgeQueryService(snapshot)

    service.list_collections()
    service.list_artifacts()
    service.list_nodes()
    service.list_edges()
    service.list_references()
    service.statistics("COL-1")
    service.list_statistics()

    assert snapshot.model_dump() == before


# -- Serialization ------------------------------------------------------------------------------------------


def test_query_results_round_trip_through_json() -> None:
    service = KnowledgeQueryService(_snapshot(_full_collection()))
    stats = service.statistics("COL-1")
    assert stats is not None
    restored = KnowledgeStatistics.model_validate_json(stats.model_dump_json())
    assert restored == stats


# -- Invalid input ------------------------------------------------------------------------------------------


def test_constructing_with_a_non_snapshot_raises_on_first_use() -> None:
    service = KnowledgeQueryService(None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        service.list_collections()


# -- Import boundary -----------------------------------------------------------------------------------------


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


_FORBIDDEN = {"analysis", "intelligence", "planning", "execution", "runtime", "orchestration", "integration"}


def test_query_package_imports_none_of_the_forbidden_packages() -> None:
    violations = {
        str(py_file.relative_to(QUERY_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN)
        for py_file in QUERY_DIR.rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & _FORBIDDEN)
    }
    assert violations == {}


def test_service_module_imports_only_expected_modules() -> None:
    imports = _direct_imports(QUERY_DIR / "service.py")
    assert imports <= {"__future__", "knowledge"}


def test_service_has_no_vendor_sdk_network_or_graph_database_import() -> None:
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
    imports = _direct_imports(QUERY_DIR / "service.py")
    assert imports.isdisjoint(forbidden_extra)
