"""Tests for `knowledge/domain/contract.py` (Sprint 10, Phase 1). Contracts
only — no storage/graph-database/query-engine/Runtime tests; those are
later phases' own scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis.contract import AnalysisResult, RequirementAnalysis
from knowledge.artifacts import (
    ArtifactMetadata,
    ArtifactType,
    ArtifactVersionInfo,
    KnowledgeAPI,
    KnowledgeAPIContent,
    RelationshipType,
)
from knowledge.domain.contract import (
    KnowledgeCollection,
    KnowledgeQuery,
    KnowledgeReference,
    KnowledgeResult,
    KnowledgeSnapshot,
    KnowledgeStatistics,
)
from knowledge.graph import GraphEdge, GraphNode

KNOWLEDGE_DOMAIN_DIR = Path(__file__).resolve().parents[3] / "knowledge" / "domain"


def _knowledge_api(artifact_id: str = "KA-0001") -> KnowledgeAPI:
    return KnowledgeAPI(
        id=artifact_id,
        type=ArtifactType.KNOWLEDGE_API,
        metadata=ArtifactMetadata(
            extracted_at="2026-01-01T00:00:00Z", extraction_method="test", extractor_version="0.1.0"
        ),
        version=ArtifactVersionInfo(),
        content=KnowledgeAPIContent(interface_kind="doctype-field", name="customer_name"),
    )


def _graph_node(node_id: str = "KG-0001", wraps: str = "KA-0001") -> GraphNode:
    return GraphNode(node_id=node_id, wraps=wraps, wraps_type=ArtifactType.KNOWLEDGE_API)


def _graph_edge() -> GraphEdge:
    return GraphEdge(
        source_node_id="KG-0001", relationship=RelationshipType.RELATED_TO, target_node_id="KG-0002"
    )


def _analysis_result(analysis_id: str = "analysis:REQ-1", requirement_id: str = "REQ-1") -> AnalysisResult:
    return AnalysisResult(
        analysis_id=analysis_id,
        requirement_id=requirement_id,
        requirement_analysis=RequirementAnalysis(requirement_id=requirement_id),
    )


def _reference() -> KnowledgeReference:
    return KnowledgeReference(
        analysis_id="analysis:REQ-1", subject_id="REQ-1:entity:Patient", subject_kind="business_entity"
    )


# -- KnowledgeReference -------------------------------------------------------------------------


def test_knowledge_reference_constructs_with_valid_data() -> None:
    reference = _reference()
    assert reference.analysis_id == "analysis:REQ-1"
    assert reference.subject_kind == "business_entity"


def test_knowledge_reference_is_frozen() -> None:
    reference = _reference()
    with pytest.raises(ValidationError):
        reference.subject_id = "changed"


def test_knowledge_reference_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        KnowledgeReference(
            analysis_id="A-1",
            subject_id="S-1",
            subject_kind="actor",
            extra="x",  # type: ignore[call-arg]
        )


def test_knowledge_reference_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        KnowledgeReference(analysis_id="", subject_id="S-1", subject_kind="actor")
    with pytest.raises(ValidationError):
        KnowledgeReference(analysis_id="A-1", subject_id="", subject_kind="actor")


def test_knowledge_reference_rejects_an_unknown_subject_kind() -> None:
    with pytest.raises(ValidationError):
        KnowledgeReference(
            analysis_id="A-1",
            subject_id="S-1",
            subject_kind="not_a_real_kind",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "subject_kind",
    ["business_entity", "business_process", "business_rule", "business_constraint", "actor"],
)
def test_knowledge_reference_accepts_every_analysis_fact_kind(subject_kind: str) -> None:
    reference = KnowledgeReference(analysis_id="A-1", subject_id="S-1", subject_kind=subject_kind)  # type: ignore[arg-type]
    assert reference.subject_kind == subject_kind


# -- KnowledgeCollection: reuses ContentArtifact / GraphNode / GraphEdge directly ----------------


def test_knowledge_collection_constructs_with_real_reused_types() -> None:
    collection = KnowledgeCollection(
        collection_id="COL-1",
        name="Selling",
        artifacts=(_knowledge_api(),),
        nodes=(_graph_node(),),
        edges=(_graph_edge(),),
        references=(_reference(),),
    )
    assert isinstance(collection.artifacts[0], KnowledgeAPI)
    assert isinstance(collection.nodes[0], GraphNode)
    assert isinstance(collection.edges[0], GraphEdge)


def test_knowledge_collection_defaults_are_empty() -> None:
    collection = KnowledgeCollection(collection_id="COL-1", name="Selling")
    assert collection.description == ""
    assert collection.artifacts == ()
    assert collection.nodes == ()
    assert collection.edges == ()
    assert collection.references == ()


def test_knowledge_collection_is_frozen() -> None:
    collection = KnowledgeCollection(collection_id="COL-1", name="Selling")
    with pytest.raises(ValidationError):
        collection.name = "Changed"


def test_knowledge_collection_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCollection(collection_id="COL-1", name="Selling", extra="x")  # type: ignore[call-arg]


def test_knowledge_collection_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCollection(collection_id="", name="Selling")
    with pytest.raises(ValidationError):
        KnowledgeCollection(collection_id="COL-1", name="")


# -- KnowledgeSnapshot: the one direct analysis.contract dependency ------------------------------


def test_knowledge_snapshot_constructs_with_a_real_analysis_result() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1",
        created_at="2026-01-01T00:00:00Z",
        source=_analysis_result(),
        collections=(KnowledgeCollection(collection_id="COL-1", name="Selling"),),
    )
    assert isinstance(snapshot.source, AnalysisResult)
    assert snapshot.source.analysis_id == "analysis:REQ-1"


def test_knowledge_snapshot_defaults_collections_to_empty() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1", created_at="2026-01-01T00:00:00Z", source=_analysis_result()
    )
    assert snapshot.collections == ()


def test_knowledge_snapshot_is_frozen() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1", created_at="2026-01-01T00:00:00Z", source=_analysis_result()
    )
    with pytest.raises(ValidationError):
        snapshot.snapshot_id = "changed"


def test_knowledge_snapshot_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSnapshot(
            snapshot_id="SNAP-1",
            created_at="2026-01-01T00:00:00Z",
            source=_analysis_result(),
            extra="x",  # type: ignore[call-arg]
        )


def test_knowledge_snapshot_requires_a_source_analysis_result() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSnapshot(snapshot_id="SNAP-1", created_at="2026-01-01T00:00:00Z")  # type: ignore[call-arg]


def test_knowledge_snapshot_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSnapshot(snapshot_id="", created_at="2026-01-01T00:00:00Z", source=_analysis_result())
    with pytest.raises(ValidationError):
        KnowledgeSnapshot(snapshot_id="SNAP-1", created_at="", source=_analysis_result())


# -- KnowledgeQuery -------------------------------------------------------------------------------


def test_knowledge_query_constructs_with_valid_data() -> None:
    query = KnowledgeQuery(
        query_id="Q-1",
        text="does ERPNext have a Patient concept?",
        artifact_types=(ArtifactType.KNOWLEDGE_API,),
        tags=("clinic",),
    )
    assert query.text == "does ERPNext have a Patient concept?"
    assert query.artifact_types == (ArtifactType.KNOWLEDGE_API,)


def test_knowledge_query_defaults_are_empty() -> None:
    query = KnowledgeQuery(query_id="Q-1", text="x")
    assert query.artifact_types == ()
    assert query.tags == ()


def test_knowledge_query_is_frozen() -> None:
    query = KnowledgeQuery(query_id="Q-1", text="x")
    with pytest.raises(ValidationError):
        query.text = "changed"


def test_knowledge_query_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuery(query_id="Q-1", text="x", extra="y")  # type: ignore[call-arg]


def test_knowledge_query_rejects_empty_required_strings() -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuery(query_id="", text="x")
    with pytest.raises(ValidationError):
        KnowledgeQuery(query_id="Q-1", text="")


# -- KnowledgeResult: the one enforced structural invariant ----------------------------------------


def test_knowledge_result_constructs_with_valid_data() -> None:
    result = KnowledgeResult(
        query_id="Q-1", artifacts=(_knowledge_api(),), nodes=(_graph_node(),), total_matched=2
    )
    assert result.total_matched == 2
    assert isinstance(result.artifacts[0], KnowledgeAPI)


def test_knowledge_result_defaults_are_empty() -> None:
    result = KnowledgeResult(query_id="Q-1")
    assert result.artifacts == ()
    assert result.nodes == ()
    assert result.total_matched == 0


def test_knowledge_result_is_frozen() -> None:
    result = KnowledgeResult(query_id="Q-1")
    with pytest.raises(ValidationError):
        result.total_matched = 5


def test_knowledge_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        KnowledgeResult(query_id="Q-1", extra="x")  # type: ignore[call-arg]


def test_knowledge_result_rejects_negative_total_matched() -> None:
    with pytest.raises(ValidationError):
        KnowledgeResult(query_id="Q-1", total_matched=-1)


def test_knowledge_result_rejects_total_matched_less_than_included_items() -> None:
    with pytest.raises(ValidationError):
        KnowledgeResult(
            query_id="Q-1", artifacts=(_knowledge_api(),), nodes=(_graph_node(),), total_matched=1
        )


def test_knowledge_result_accepts_total_matched_exactly_equal_to_included_items() -> None:
    result = KnowledgeResult(query_id="Q-1", artifacts=(_knowledge_api(),), total_matched=1)
    assert result.total_matched == 1


def test_knowledge_result_accepts_total_matched_greater_than_included_items() -> None:
    # A real result set may be paginated -- more matched than returned.
    result = KnowledgeResult(query_id="Q-1", artifacts=(_knowledge_api(),), total_matched=100)
    assert result.total_matched == 100


# -- KnowledgeStatistics --------------------------------------------------------------------------


def test_knowledge_statistics_constructs_with_valid_data() -> None:
    stats = KnowledgeStatistics(
        collection_id="COL-1",
        artifact_count=3,
        node_count=3,
        relationship_count=1,
        counts_by_artifact_type={"knowledge_api": 3},
    )
    assert stats.artifact_count == 3
    assert stats.counts_by_artifact_type == {"knowledge_api": 3}


def test_knowledge_statistics_defaults_are_zero_and_empty() -> None:
    stats = KnowledgeStatistics(collection_id="COL-1")
    assert stats.artifact_count == 0
    assert stats.node_count == 0
    assert stats.relationship_count == 0
    assert stats.counts_by_artifact_type == {}


def test_knowledge_statistics_is_frozen() -> None:
    stats = KnowledgeStatistics(collection_id="COL-1")
    with pytest.raises(ValidationError):
        stats.artifact_count = 5


def test_knowledge_statistics_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        KnowledgeStatistics(collection_id="COL-1", extra="x")  # type: ignore[call-arg]


def test_knowledge_statistics_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        KnowledgeStatistics(collection_id="COL-1", artifact_count=-1)
    with pytest.raises(ValidationError):
        KnowledgeStatistics(collection_id="COL-1", node_count=-1)
    with pytest.raises(ValidationError):
        KnowledgeStatistics(collection_id="COL-1", relationship_count=-1)


def test_knowledge_statistics_rejects_empty_collection_id() -> None:
    with pytest.raises(ValidationError):
        KnowledgeStatistics(collection_id="")


# -- Equality and serialization -------------------------------------------------------------------


def test_equal_instances_compare_equal() -> None:
    assert _reference() == _reference()
    assert _analysis_result() == _analysis_result()


def test_knowledge_snapshot_round_trips_through_json() -> None:
    snapshot = KnowledgeSnapshot(
        snapshot_id="SNAP-1",
        created_at="2026-01-01T00:00:00Z",
        source=_analysis_result(),
        collections=(
            KnowledgeCollection(
                collection_id="COL-1",
                name="Selling",
                artifacts=(_knowledge_api(),),
                nodes=(_graph_node(),),
                edges=(_graph_edge(),),
                references=(_reference(),),
            ),
        ),
    )
    restored = KnowledgeSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored == snapshot


def test_knowledge_result_round_trips_through_dict() -> None:
    result = KnowledgeResult(
        query_id="Q-1", artifacts=(_knowledge_api(),), nodes=(_graph_node(),), total_matched=2
    )
    restored = KnowledgeResult.model_validate(result.model_dump())
    assert restored == result


def test_repeated_construction_from_identical_input_is_deterministic() -> None:
    first = KnowledgeStatistics(collection_id="COL-1", artifact_count=3)
    second = KnowledgeStatistics(collection_id="COL-1", artifact_count=3)
    assert first == second


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


def test_domain_package_imports_none_of_the_forbidden_packages() -> None:
    violations = {
        str(py_file.relative_to(KNOWLEDGE_DOMAIN_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN)
        for py_file in KNOWLEDGE_DOMAIN_DIR.rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & _FORBIDDEN)
    }
    assert violations == {}


def test_contract_module_imports_only_expected_modules() -> None:
    imports = _direct_imports(KNOWLEDGE_DOMAIN_DIR / "contract.py")
    assert imports <= {"__future__", "typing", "pydantic", "analysis", "knowledge"}


def test_contract_module_has_no_vendor_sdk_or_network_import() -> None:
    forbidden_extra = {"httpx", "requests", "urllib", "aiohttp", "anthropic", "openai"}
    imports = _direct_imports(KNOWLEDGE_DOMAIN_DIR / "contract.py")
    assert imports.isdisjoint(forbidden_extra)


def test_contract_module_has_no_graph_or_database_sdk_import() -> None:
    forbidden_extra = {"neo4j", "rdflib", "networkx", "sqlalchemy", "pymongo", "redis"}
    imports = _direct_imports(KNOWLEDGE_DOMAIN_DIR / "contract.py")
    assert imports.isdisjoint(forbidden_extra)
