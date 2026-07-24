"""Tests proving `GraphStoreAdapter` is a real abstraction: `GraphBuilder`
depends on the interface alone, and a second, independent implementation
can be substituted for `InMemoryGraphStore` with no change to `GraphBuilder`
(SPRINT3_ARCHITECTURE_PACKAGE.md §7.4: "future backends must be swappable
without changing callers")."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from knowledge.artifacts import ArtifactStatus, ArtifactType, DependencyEdge, KnowledgeAPI, RelationshipType
from knowledge.graph.builder import GraphBuilder
from knowledge.graph.model import GraphEdge, GraphNode
from knowledge.graph.store import Direction, GraphStoreAdapter, InMemoryGraphStore


def test_graph_store_adapter_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        GraphStoreAdapter()  # type: ignore[abstract]


def test_in_memory_graph_store_is_a_graph_store_adapter() -> None:
    assert isinstance(InMemoryGraphStore(), GraphStoreAdapter)


class _RecordingAdapter(GraphStoreAdapter):
    """A second, independent `GraphStoreAdapter` implementation — deliberately
    not built on `InMemoryGraphStore` — used only to prove `GraphBuilder`
    never assumes anything beyond the abstract contract.
    """

    def __init__(self) -> None:
        self.created_nodes: list[tuple[str, ArtifactType]] = []
        self.created_edges: list[tuple[str, RelationshipType, str]] = []
        self._nodes: dict[str, GraphNode] = {}
        self._by_wraps: dict[str, str] = {}
        self._counter = 0

    def create_node(self, wraps: str, wraps_type: ArtifactType) -> GraphNode:
        if wraps in self._by_wraps:
            return self._nodes[self._by_wraps[wraps]]
        self._counter += 1
        node = GraphNode(node_id=f"REC-{self._counter}", wraps=wraps, wraps_type=wraps_type)
        self._nodes[node.node_id] = node
        self._by_wraps[wraps] = node.node_id
        self.created_nodes.append((wraps, wraps_type))
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
        self.created_edges.append((source_node_id, relationship, target_node_id))
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


def test_graph_builder_works_against_a_non_in_memory_adapter(
    make_knowledge_api: Callable[..., KnowledgeAPI],
) -> None:
    adapter = _RecordingAdapter()
    builder = GraphBuilder(adapter)
    artifact = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),),
    )

    node = builder.project(artifact)

    assert node is not None
    assert ("KA-0001", ArtifactType.KNOWLEDGE_API) in adapter.created_nodes
    assert ("KA-0002", ArtifactType.KNOWLEDGE_API) in adapter.created_nodes
    assert len(adapter.created_edges) == 1
