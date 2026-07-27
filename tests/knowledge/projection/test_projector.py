"""Tests for `knowledge/projection/` (Sprint 10, Phase 3). Deterministic,
storeless graph projection only — no persistence/query-engine/traversal/
Intelligence tests; those are out of this phase's scope entirely.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.contract import AnalysisResult, RequirementAnalysis
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
)
from knowledge.domain import KnowledgeCollection, KnowledgeReference, KnowledgeSnapshot
from knowledge.graph import GraphEdge, GraphNode
from knowledge.projection.projector import (
    project_artifact,
    project_artifact_edges,
    project_collection,
    project_snapshot,
)

PROJECTION_DIR = Path(__file__).resolve().parents[3] / "knowledge" / "projection"
_CREATED_AT = "2026-01-01T00:00:00Z"


def _metadata() -> ArtifactMetadata:
    return ArtifactMetadata(extracted_at=_CREATED_AT, extraction_method="test", extractor_version="0.1.0")


def _workflow(
    artifact_id: str = "WF-1",
    *,
    relationships: tuple[RelationshipEdge, ...] = (),
    dependencies: tuple[DependencyEdge, ...] = (),
) -> Workflow:
    return Workflow(
        id=artifact_id,
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=WorkflowContent(title="Patient Registration", steps=()),
        relationships=relationships,
        dependencies=dependencies,
    )


def _knowledge_api(artifact_id: str = "KA-1") -> KnowledgeAPI:
    return KnowledgeAPI(
        id=artifact_id,
        type=ArtifactType.KNOWLEDGE_API,
        metadata=_metadata(),
        version=ArtifactVersionInfo(),
        content=KnowledgeAPIContent(interface_kind="doctype-field", name="customer_name"),
    )


def _reference() -> KnowledgeReference:
    return KnowledgeReference(
        analysis_id="analysis:REQ-1", subject_id="REQ-1:entity:Patient", subject_kind="business_entity"
    )


def _analysis_result() -> AnalysisResult:
    return AnalysisResult(
        analysis_id="analysis:REQ-1",
        requirement_id="REQ-1",
        requirement_analysis=RequirementAnalysis(requirement_id="REQ-1"),
    )


def _collection(**overrides: object) -> KnowledgeCollection:
    defaults: dict[str, object] = {"collection_id": "COL-1", "name": "REQ-1"}
    defaults.update(overrides)
    return KnowledgeCollection(**defaults)  # type: ignore[arg-type]


# -- project_artifact / project_artifact_edges -----------------------------------------------------


def test_project_artifact_produces_a_matching_graph_node() -> None:
    artifact = _workflow("WF-1")
    node = project_artifact(artifact)
    assert node.wraps == "WF-1"
    assert node.wraps_type == ArtifactType.WORKFLOW
    assert node.node_id == "KG-WF-1"


def test_project_artifact_node_id_is_a_pure_function_of_artifact_id() -> None:
    assert project_artifact(_workflow("WF-1")).node_id == project_artifact(_workflow("WF-1")).node_id
    assert project_artifact(_workflow("WF-1")).node_id != project_artifact(_workflow("WF-2")).node_id


def test_project_artifact_edges_translates_relationships_verbatim() -> None:
    artifact = _workflow(
        "WF-1",
        relationships=(
            RelationshipEdge(target_id="KA-1", relationship=RelationshipType.IMPLEMENTS, note="x"),
        ),
    )
    edges = project_artifact_edges(artifact)
    assert edges == (
        GraphEdge(
            source_node_id="KG-WF-1",
            relationship=RelationshipType.IMPLEMENTS,
            target_node_id="KG-KA-1",
            note="x",
        ),
    )


def test_project_artifact_edges_translates_dependencies_as_depends_on() -> None:
    artifact = _workflow("WF-1", dependencies=(DependencyEdge(target_id="KA-1", reason="needs the schema"),))
    edges = project_artifact_edges(artifact)
    assert edges == (
        GraphEdge(
            source_node_id="KG-WF-1",
            relationship=RelationshipType.DEPENDS_ON,
            target_node_id="KG-KA-1",
            note="needs the schema",
        ),
    )


def test_project_artifact_edges_combines_relationships_and_dependencies_in_order() -> None:
    artifact = _workflow(
        "WF-1",
        relationships=(RelationshipEdge(target_id="KA-1", relationship=RelationshipType.IMPLEMENTS),),
        dependencies=(DependencyEdge(target_id="KA-2"),),
    )
    edges = project_artifact_edges(artifact)
    assert [edge.target_node_id for edge in edges] == ["KG-KA-1", "KG-KA-2"]


def test_project_artifact_edges_with_no_relationships_or_dependencies_is_empty() -> None:
    assert project_artifact_edges(_workflow("WF-1")) == ()


def test_project_artifact_edges_targets_a_node_not_projected_in_this_call_are_still_valid() -> None:
    # Mirrors GraphBuilder's own established "resolve by id alone" handling
    # of an edge target that hasn't been projected yet -- not an error.
    artifact = _workflow("WF-1", dependencies=(DependencyEdge(target_id="KA-999"),))
    edges = project_artifact_edges(artifact)
    assert edges[0].target_node_id == "KG-KA-999"


# -- project_collection -----------------------------------------------------------------------------


def test_project_collection_projects_every_artifact() -> None:
    collection = _collection(artifacts=(_workflow("WF-1"), _knowledge_api("KA-1")))
    projected = project_collection(collection)
    assert {node.wraps for node in projected.nodes} == {"WF-1", "KA-1"}


def test_project_collection_derives_edges_from_all_artifacts() -> None:
    collection = _collection(
        artifacts=(
            _workflow("WF-1", dependencies=(DependencyEdge(target_id="KA-1"),)),
            _knowledge_api("KA-1"),
        )
    )
    projected = project_collection(collection)
    assert len(projected.edges) == 1
    assert projected.edges[0].source_node_id == "KG-WF-1"
    assert projected.edges[0].target_node_id == "KG-KA-1"


def test_project_collection_preserves_references_artifacts_and_identity_fields() -> None:
    collection = _collection(
        name="Selling",
        description="x",
        artifacts=(_workflow("WF-1"),),
        references=(_reference(),),
    )
    projected = project_collection(collection)
    assert projected.collection_id == collection.collection_id
    assert projected.name == collection.name
    assert projected.description == collection.description
    assert projected.artifacts == collection.artifacts
    assert projected.references == collection.references


def test_project_collection_replaces_rather_than_appends_to_existing_nodes_and_edges() -> None:
    # Constructed by hand to prove REPLACE semantics, not APPEND -- the
    # property that makes idempotency (below) hold.
    stale_node = GraphNode(node_id="KG-stale", wraps="stale", wraps_type=ArtifactType.WORKFLOW)
    collection = _collection(artifacts=(_workflow("WF-1"),), nodes=(stale_node,))
    projected = project_collection(collection)
    assert stale_node not in projected.nodes
    assert projected.nodes == (GraphNode(node_id="KG-WF-1", wraps="WF-1", wraps_type=ArtifactType.WORKFLOW),)


# -- Empty knowledge --------------------------------------------------------------------------------


def test_project_collection_with_no_artifacts_produces_no_nodes_or_edges() -> None:
    projected = project_collection(_collection())
    assert projected.nodes == ()
    assert projected.edges == ()


def test_project_snapshot_with_an_empty_collection() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1", created_at=_CREATED_AT, source=_analysis_result(), collections=(_collection(),)
    )
    projected = project_snapshot(snapshot)
    assert projected.collections[0].nodes == ()


# -- project_snapshot: identity preservation --------------------------------------------------------


def test_project_snapshot_preserves_identity_fields() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1",
        created_at=_CREATED_AT,
        source=_analysis_result(),
        collections=(_collection(artifacts=(_workflow("WF-1"),)),),
    )
    projected = project_snapshot(snapshot)
    assert projected.snapshot_id == snapshot.snapshot_id
    assert projected.created_at == snapshot.created_at
    assert projected.source == snapshot.source


def test_project_snapshot_projects_every_collection_in_declared_order() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1",
        created_at=_CREATED_AT,
        source=_analysis_result(),
        collections=(
            _collection(collection_id="COL-1", artifacts=(_workflow("WF-1"),)),
            _collection(collection_id="COL-2", artifacts=(_workflow("WF-2"),)),
        ),
    )
    projected = project_snapshot(snapshot)
    assert [c.collection_id for c in projected.collections] == ["COL-1", "COL-2"]
    assert projected.collections[0].nodes[0].wraps == "WF-1"
    assert projected.collections[1].nodes[0].wraps == "WF-2"


# -- Determinism and idempotency ---------------------------------------------------------------------


def test_project_collection_is_deterministic_across_repeated_calls() -> None:
    collection = _collection(artifacts=(_workflow("WF-1", dependencies=(DependencyEdge(target_id="KA-1"),)),))
    assert project_collection(collection) == project_collection(collection)


def test_project_collection_is_idempotent() -> None:
    collection = _collection(artifacts=(_workflow("WF-1", dependencies=(DependencyEdge(target_id="KA-1"),)),))
    once = project_collection(collection)
    twice = project_collection(once)
    assert once == twice


def test_project_snapshot_is_idempotent() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1",
        created_at=_CREATED_AT,
        source=_analysis_result(),
        collections=(_collection(artifacts=(_workflow("WF-1"),)),),
    )
    once = project_snapshot(snapshot)
    twice = project_snapshot(once)
    assert once == twice


# -- Duplicate preservation ---------------------------------------------------------------------------


def test_duplicate_artifacts_produce_duplicate_nodes_not_merged() -> None:
    workflow = _workflow("WF-1")
    collection = _collection(artifacts=(workflow, workflow))
    projected = project_collection(collection)
    assert len(projected.nodes) == 2
    assert projected.nodes[0] == projected.nodes[1]


# -- Serialization --------------------------------------------------------------------------------------


def test_projected_collection_round_trips_through_json() -> None:
    collection = _collection(artifacts=(_workflow("WF-1", dependencies=(DependencyEdge(target_id="KA-1"),)),))
    projected = project_collection(collection)
    restored = KnowledgeCollection.model_validate_json(projected.model_dump_json())
    assert restored == projected


def test_projected_snapshot_round_trips_through_dict() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1",
        created_at=_CREATED_AT,
        source=_analysis_result(),
        collections=(_collection(artifacts=(_workflow("WF-1"),)),),
    )
    projected = project_snapshot(snapshot)
    restored = KnowledgeSnapshot.model_validate(projected.model_dump())
    assert restored == projected


# -- Invalid input ----------------------------------------------------------------------------------------


def test_project_collection_rejects_non_collection_input() -> None:
    with pytest.raises(AttributeError):
        project_collection(None)  # type: ignore[arg-type]


def test_project_snapshot_rejects_non_snapshot_input() -> None:
    with pytest.raises(AttributeError):
        project_snapshot(None)  # type: ignore[arg-type]


# -- Import boundary --------------------------------------------------------------------------------------


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


def test_projection_package_imports_none_of_the_forbidden_packages() -> None:
    violations = {
        str(py_file.relative_to(PROJECTION_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN)
        for py_file in PROJECTION_DIR.rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & _FORBIDDEN)
    }
    assert violations == {}


def test_projector_module_imports_only_expected_modules() -> None:
    imports = _direct_imports(PROJECTION_DIR / "projector.py")
    assert imports <= {"__future__", "knowledge"}


def test_projector_has_no_vendor_sdk_network_or_graph_database_import() -> None:
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
    imports = _direct_imports(PROJECTION_DIR / "projector.py")
    assert imports.isdisjoint(forbidden_extra)
