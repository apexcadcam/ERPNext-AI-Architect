"""The Graph Store Adapter: one fixed, backend-agnostic contract, plus an
in-memory implementation of it.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §7.4 exactly: the same
"backend-agnostic adapter contract, no product chosen" shape
`docs/runtime/STORAGE_ABSTRACTION.md` already establishes for content
storage, applied to graph storage. `InMemoryGraphStore` is one conforming
implementation, not a special case the rest of this package favors — a
`GraphBuilder` (builder.py) is written against `GraphStoreAdapter` alone and
never imports `InMemoryGraphStore` itself, so a future real backend is
swappable without changing `GraphBuilder` or any caller.

No delete operation exists anywhere in this contract — the exact structural
enforcement docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md §4 already
requires ("edges are appended, never overwritten... never deleted, only
retracted"): there is no operation here that could violate it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal

from knowledge.artifacts import ArtifactType, RelationshipType
from knowledge.graph.errors import DependsOnCycleError, InconsistentNodeError
from knowledge.graph.model import GraphEdge, GraphNode

#: KNOWLEDGE_GRAPH_SPEC.md §3: stored once, as a single undirected edge,
#: regardless of which endpoint's artifact declared it.
SYMMETRIC_RELATIONSHIPS = frozenset({RelationshipType.CONFLICTS_WITH, RelationshipType.RELATED_TO})

Direction = Literal["outgoing", "incoming", "both"]


class GraphStoreAdapter(ABC):
    """Every conforming implementation, in addition to matching these
    method signatures, must:

    - Treat `create_node` as idempotent by `wraps` (the wrapped artifact's
      own id) — creating a node for the same `wraps` twice returns the
      existing node rather than duplicating it.
    - Treat `create_edge` as idempotent by `(source_node_id, relationship,
      target_node_id)` (after canonicalization, for symmetric
      relationships) — creating the same edge twice returns the first one
      written, per §4's "appended, never overwritten."
    - Store a symmetric relationship (`conflicts_with`, `related_to`) as one
      canonical-direction edge regardless of call order, but still surface
      it via `neighbors`/`outgoing_edges`/`incoming_edges` from both
      endpoints (§3).
    - Reject a `depends_on` edge that would close a cycle, at `create_edge`
      time, never merely detect one later (§3).
    - Never expose any operation that deletes a node or an edge.
    """

    @abstractmethod
    def create_node(self, wraps: str, wraps_type: ArtifactType) -> GraphNode: ...

    @abstractmethod
    def create_edge(
        self,
        source_node_id: str,
        relationship: RelationshipType,
        target_node_id: str,
        *,
        note: str = "",
        confidence_of_edge: float | None = None,
    ) -> GraphEdge: ...

    @abstractmethod
    def get_node(self, node_id: str) -> GraphNode | None: ...

    @abstractmethod
    def get_node_by_artifact_id(self, artifact_id: str) -> GraphNode | None: ...

    @abstractmethod
    def outgoing_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]: ...

    @abstractmethod
    def incoming_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]: ...

    @abstractmethod
    def neighbors(
        self,
        node_id: str,
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        direction: Direction = "both",
    ) -> tuple[GraphNode, ...]: ...

    @abstractmethod
    def traverse(
        self,
        seed_artifact_ids: Sequence[str],
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        max_depth: int,
        direction: Direction = "outgoing",
    ) -> tuple[GraphNode, ...]: ...

    @abstractmethod
    def all_nodes(self) -> tuple[GraphNode, ...]: ...


class InMemoryGraphStore(GraphStoreAdapter):
    """A plain in-process dict-backed implementation — no persistence, no
    serialization, valid as a full substitute for any real backend in tests,
    per §7.4's "an in-memory Adapter satisfies the same contract" row.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._node_id_by_wraps: dict[str, str] = {}
        self._edges: dict[tuple[str, RelationshipType, str], GraphEdge] = {}
        self._outgoing: dict[str, list[GraphEdge]] = {}
        self._incoming: dict[str, list[GraphEdge]] = {}
        self._next_id = 1

    def _allocate_node_id(self) -> str:
        node_id = f"KG-{self._next_id:04d}"
        self._next_id += 1
        return node_id

    def create_node(self, wraps: str, wraps_type: ArtifactType) -> GraphNode:
        existing_id = self._node_id_by_wraps.get(wraps)
        if existing_id is not None:
            existing = self._nodes[existing_id]
            if existing.wraps_type != wraps_type:
                raise InconsistentNodeError(
                    f"node for wraps='{wraps}' already exists with wraps_type="
                    f"'{existing.wraps_type.value}', cannot recreate it as '{wraps_type.value}'"
                )
            return existing

        node = GraphNode(node_id=self._allocate_node_id(), wraps=wraps, wraps_type=wraps_type)
        self._nodes[node.node_id] = node
        self._node_id_by_wraps[wraps] = node.node_id
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
        if source_node_id not in self._nodes:
            raise ValueError(f"unknown source node '{source_node_id}'")
        if target_node_id not in self._nodes:
            raise ValueError(f"unknown target node '{target_node_id}'")

        symmetric = relationship in SYMMETRIC_RELATIONSHIPS
        a, b = source_node_id, target_node_id
        if symmetric and b < a:
            a, b = b, a

        key = (a, relationship, b)
        existing = self._edges.get(key)
        if existing is not None:
            return existing

        if relationship is RelationshipType.DEPENDS_ON:
            if source_node_id == target_node_id or self._can_reach(
                target_node_id, source_node_id, RelationshipType.DEPENDS_ON
            ):
                raise DependsOnCycleError(
                    f"adding depends_on edge '{source_node_id}' -> '{target_node_id}' "
                    f"would close a dependency cycle"
                )

        edge = GraphEdge(
            source_node_id=a,
            relationship=relationship,
            target_node_id=b,
            note=note,
            confidence_of_edge=confidence_of_edge,
        )
        self._edges[key] = edge
        self._outgoing.setdefault(a, []).append(edge)
        self._incoming.setdefault(b, []).append(edge)
        if symmetric:
            self._outgoing.setdefault(b, []).append(edge)
            self._incoming.setdefault(a, []).append(edge)
        return edge

    def _can_reach(self, start: str, goal: str, relationship: RelationshipType) -> bool:
        if start == goal:
            return True
        seen = {start}
        frontier = [start]
        while frontier:
            next_frontier: list[str] = []
            for node_id in frontier:
                for edge in self._outgoing.get(node_id, ()):
                    if edge.relationship is not relationship:
                        continue
                    if edge.target_node_id == goal:
                        return True
                    if edge.target_node_id not in seen:
                        seen.add(edge.target_node_id)
                        next_frontier.append(edge.target_node_id)
            frontier = next_frontier
        return False

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_node_by_artifact_id(self, artifact_id: str) -> GraphNode | None:
        node_id = self._node_id_by_wraps.get(artifact_id)
        return self._nodes.get(node_id) if node_id is not None else None

    def outgoing_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        edges = self._outgoing.get(node_id, ())
        if relationship_filter is not None:
            edges = [edge for edge in edges if edge.relationship in relationship_filter]
        return tuple(edges)

    def incoming_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        edges = self._incoming.get(node_id, ())
        if relationship_filter is not None:
            edges = [edge for edge in edges if edge.relationship in relationship_filter]
        return tuple(edges)

    def neighbors(
        self,
        node_id: str,
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        direction: Direction = "both",
    ) -> tuple[GraphNode, ...]:
        found: dict[str, GraphNode] = {}
        if direction in ("outgoing", "both"):
            for edge in self.outgoing_edges(node_id, relationship_filter):
                other_id = edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
                other = self._nodes.get(other_id)
                if other is not None:
                    found[other_id] = other
        if direction in ("incoming", "both"):
            for edge in self.incoming_edges(node_id, relationship_filter):
                other_id = edge.source_node_id if edge.target_node_id == node_id else edge.target_node_id
                other = self._nodes.get(other_id)
                if other is not None:
                    found[other_id] = other
        return tuple(found.values())

    def traverse(
        self,
        seed_artifact_ids: Sequence[str],
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        max_depth: int,
        direction: Direction = "outgoing",
    ) -> tuple[GraphNode, ...]:
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")

        visited: set[str] = set()
        order: list[str] = []
        frontier: list[str] = []
        for artifact_id in seed_artifact_ids:
            node = self.get_node_by_artifact_id(artifact_id)
            if node is not None and node.node_id not in visited:
                visited.add(node.node_id)
                order.append(node.node_id)
                frontier.append(node.node_id)

        depth = 0
        while depth < max_depth and frontier:
            next_frontier: list[str] = []
            for node_id in frontier:
                for neighbor in self.neighbors(
                    node_id, relationship_filter=relationship_filter, direction=direction
                ):
                    if neighbor.node_id not in visited:
                        visited.add(neighbor.node_id)
                        order.append(neighbor.node_id)
                        next_frontier.append(neighbor.node_id)
            frontier = next_frontier
            depth += 1

        return tuple(self._nodes[node_id] for node_id in order)

    def all_nodes(self) -> tuple[GraphNode, ...]:
        return tuple(self._nodes.values())
