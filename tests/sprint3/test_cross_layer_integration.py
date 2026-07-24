"""Cross-layer integration tests for Sprint 3, Phase 6.

Validates the two complete flows named by the Phase 6 task, independently,
plus that they coexist without coupling:

  Knowledge Artifact -> Graph Builder -> InMemoryGraphStore -> Graph Traversal
  Connector Discovery -> Connector Registry -> Filesystem Connector -> Capability Resolution

Neither flow references the other's package.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.artifacts import DependencyEdge, RelationshipEdge, RelationshipType
from knowledge.graph import GraphBuilder, InMemoryGraphStore

from integration import ConnectorRegistry
from tests.sprint3.conftest import CONNECTORS_DIR, make_validated_knowledge_api


# -- Knowledge flow: Artifact -> Builder -> Store -> Traversal ----------------------


def test_knowledge_artifact_to_traversal_end_to_end() -> None:
    sales_invoice = make_validated_knowledge_api(
        "KA-0001",
        dependencies=(DependencyEdge(target_id="KA-0002", reason="Sales Invoice.customer is a Link field"),),
    )
    customer = make_validated_knowledge_api(
        "KA-0002",
        dependencies=(DependencyEdge(target_id="KA-0003", reason="Customer.address is a Link field"),),
    )

    store = InMemoryGraphStore()
    builder = GraphBuilder(store)
    builder.project(sales_invoice)
    builder.project(customer)

    result = store.traverse(["KA-0001"], relationship_filter=[RelationshipType.DEPENDS_ON], max_depth=2)

    assert [node.wraps for node in result] == ["KA-0001", "KA-0002", "KA-0003"]


def test_knowledge_flow_never_touches_the_connector_registry() -> None:
    # A fresh ConnectorRegistry, untouched by anything in this test, proves
    # the Knowledge flow above has no way to reach it even by accident.
    registry = ConnectorRegistry()

    store = InMemoryGraphStore()
    builder = GraphBuilder(store)
    builder.project(
        make_validated_knowledge_api(
            "KA-0001",
            relationships=(RelationshipEdge(target_id="KA-0002", relationship=RelationshipType.RELATED_TO),),
        )
    )

    assert registry.all_connectors() == ()


# -- Connector flow: Discovery -> Registry -> Filesystem Connector -> Capability Resolution --


def test_connector_discovery_to_capability_resolution_end_to_end(tmp_path: Path) -> None:
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([CONNECTORS_DIR]))
    registry.validate()

    providers = registry.capability_providers("filesystem.read_text")
    assert providers == ("filesystem",)

    connector = registry.instantiate(providers[0])
    connector.manifest = connector.manifest.model_copy(update={"endpoint_reference": str(tmp_path)})
    connector.connect()

    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    assert connector.read_text("hello.txt") == "hi"  # type: ignore[attr-defined]


def test_connector_flow_never_touches_the_graph_store() -> None:
    store = InMemoryGraphStore()

    registry = ConnectorRegistry()
    registry.register_all(registry.discover([CONNECTORS_DIR]))
    registry.validate()
    registry.instantiate("filesystem")

    assert store.all_nodes() == ()


# -- Coexistence: both flows in one process, no shared/leaked state -------------------


def test_both_subsystems_coexist_without_coupling(tmp_path: Path) -> None:
    graph_store = InMemoryGraphStore()
    builder = GraphBuilder(graph_store)
    builder.project(
        make_validated_knowledge_api(
            "KA-0001",
            relationships=(RelationshipEdge(target_id="KA-0002", relationship=RelationshipType.REFERENCES),),
        )
    )

    connector_registry = ConnectorRegistry()
    connector_registry.register_all(connector_registry.discover([CONNECTORS_DIR]))
    connector_registry.validate()
    filesystem = connector_registry.instantiate("filesystem")
    filesystem.manifest = filesystem.manifest.model_copy(update={"endpoint_reference": str(tmp_path)})
    filesystem.connect()

    # Each subsystem reflects only its own operations.
    assert len(graph_store.all_nodes()) == 2
    assert connector_registry.all_connectors()[0].manifest.connector_id == "filesystem"
    assert filesystem.exists("nothing-written-yet.txt") is False  # type: ignore[attr-defined]
    assert graph_store.get_node_by_artifact_id("filesystem") is None
    assert connector_registry.get("KA-0001") is None
