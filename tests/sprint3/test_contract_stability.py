"""Contract stability tests for Sprint 3, Phase 6.

Proves the public contracts frozen across Phases 3-5 are genuinely
implementation-independent, not merely "happen to work with the one real
implementation each has so far."
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from knowledge.artifacts import ArtifactType, DependencyEdge, RelationshipType
from knowledge.graph.builder import GraphBuilder
from knowledge.graph.model import GraphEdge, GraphNode
from knowledge.graph.store import Direction, GraphStoreAdapter

from integration.connectors.filesystem.connector import FilesystemConnector
from integration.contract import ConnectorManifest
from integration.lifecycle import ConnectorLifecycle
from integration.registry import ConnectorRegistry
from tests.sprint3.conftest import CONNECTORS_DIR, make_validated_knowledge_api


# -- GraphBuilder works with any GraphStoreAdapter --------------------------------------


class _CallOrderSpyAdapter(GraphStoreAdapter):
    """Records the exact sequence of calls `GraphBuilder` makes, proving it
    never reaches past the abstract `GraphStoreAdapter` contract (no
    isinstance check, no attribute access beyond what's declared there).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._nodes: dict[str, GraphNode] = {}
        self._by_wraps: dict[str, str] = {}
        self._counter = 0

    def create_node(self, wraps: str, wraps_type: ArtifactType) -> GraphNode:
        self.calls.append(f"create_node({wraps})")
        if wraps in self._by_wraps:
            return self._nodes[self._by_wraps[wraps]]
        self._counter += 1
        node = GraphNode(node_id=f"SPY-{self._counter}", wraps=wraps, wraps_type=wraps_type)
        self._nodes[node.node_id] = node
        self._by_wraps[wraps] = node.node_id
        return node

    def create_edge(
        self,
        source_node_id: str,
        relationship: RelationshipType,
        target_node_id: str,
        *,
        note: str = "",
        confidence_of_edge: float | None = None,
    ) -> GraphEdge:
        self.calls.append(f"create_edge({source_node_id}, {relationship.value}, {target_node_id})")
        return GraphEdge(
            source_node_id=source_node_id,
            relationship=relationship,
            target_node_id=target_node_id,
            note=note,
            confidence_of_edge=confidence_of_edge,
        )

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_node_by_artifact_id(self, artifact_id: str) -> GraphNode | None:
        node_id = self._by_wraps.get(artifact_id)
        return self._nodes.get(node_id) if node_id is not None else None

    def outgoing_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        return ()

    def incoming_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        return ()

    def neighbors(
        self,
        node_id: str,
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        direction: Direction = "both",
    ) -> tuple[GraphNode, ...]:
        return ()

    def traverse(
        self,
        seed_artifact_ids: Sequence[str],
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        max_depth: int,
        direction: Direction = "outgoing",
    ) -> tuple[GraphNode, ...]:
        return ()

    def all_nodes(self) -> tuple[GraphNode, ...]:
        return tuple(self._nodes.values())


def test_graph_builder_issues_the_expected_call_sequence_against_any_adapter() -> None:
    adapter = _CallOrderSpyAdapter()
    builder = GraphBuilder(adapter)
    artifact = make_validated_knowledge_api(
        "KA-0001", dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),)
    )

    builder.project(artifact)

    assert adapter.calls == [
        "create_node(KA-0001)",
        "create_node(KA-0002)",
        "create_edge(SPY-1, depends_on, SPY-2)",
    ]


# -- ConnectorRegistry works with any ConnectorLifecycle implementation -----------------


def test_connector_registry_registers_and_instantiates_a_non_filesystem_connector(
    make_echo_connector: Callable[..., Path],
) -> None:
    connectors_dir = make_echo_connector("echo")
    registry = ConnectorRegistry()

    registry.register_all(registry.discover([connectors_dir]))
    registry.validate()
    instance = registry.instantiate("echo")

    assert isinstance(instance, ConnectorLifecycle)
    instance.connect()
    assert instance.health_check().healthy is True
    assert instance.echo("hi") == "hi"  # type: ignore[attr-defined]


def test_connector_registry_treats_filesystem_and_echo_identically(
    make_echo_connector: Callable[..., Path],
) -> None:
    # Discover the real Filesystem connector and a synthetic Echo connector
    # side by side — the registry's own code path is identical for both,
    # proven by neither needing any special handling to coexist.
    connectors_dir = make_echo_connector("echo")
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([CONNECTORS_DIR]))
    registry.register_all(registry.discover([connectors_dir]))

    report = registry.validate()

    assert report.ok
    assert {c.manifest.connector_id for c in registry.all_connectors()} == {"filesystem", "echo"}


# -- FilesystemConnector satisfies ConnectorLifecycle completely ------------------------


def test_filesystem_connector_has_no_unimplemented_abstract_methods() -> None:
    assert FilesystemConnector.__abstractmethods__ == frozenset()


def test_filesystem_connector_is_fully_usable_through_the_lifecycle_interface(tmp_path: Path) -> None:
    manifest = ConnectorManifest(
        connector_id="filesystem",
        display_name="Filesystem",
        maintained_by="test-suite",
        target_system_type="filesystem",
        version="0.1.0",
        endpoint_kind="local_path",
        endpoint_reference=str(tmp_path),
        entry_point="connector:create",
    )
    connector: ConnectorLifecycle = FilesystemConnector(manifest)

    connector.initialize()
    connector.connect()
    health = connector.health_check()
    connector.disconnect()

    assert health.healthy is True
