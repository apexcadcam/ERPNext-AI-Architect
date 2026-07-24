"""`GraphReader` — the Planner's read-only view of the Knowledge Graph.

Implements the approved Sprint 4 Architecture Package §5.7 and ADR-0011: a
structural (`typing.Protocol`) **subset** of `knowledge.graph.GraphStoreAdapter`
(Sprint 3, Phase 5, frozen) — every read operation, none of the write ones
(`create_node`/`create_edge` are deliberately absent from this Protocol's
surface).

Because `Protocol` typing is structural, no adapter/wrapper class is needed
here and none is defined: any real `GraphStoreAdapter` implementation (e.g.
`knowledge.graph.InMemoryGraphStore`) already satisfies `GraphReader` simply
by having every method below with a matching signature — the type system
just never exposes the write methods through a `GraphReader`-typed
reference. This is a structural side-effect guarantee, not a documented
convention, per ADR-0011's own reasoning (itself reapplying
`SPRINT3_ARCHITECTURE_PACKAGE.md §5.4`'s "Isolation Is Structural, Not a
Convention" one layer up).

Every method signature below is copied verbatim from
`knowledge.graph.store.GraphStoreAdapter`'s own abstract methods — including
its `Direction` type alias and its `RelationshipType`/`GraphNode`/
`GraphEdge` types, imported from the Knowledge Graph package rather than
redefined, so this Protocol cannot silently drift out of structural sync
with the real Adapter it mirrors.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from knowledge.artifacts import RelationshipType
from knowledge.graph import GraphEdge, GraphNode
from knowledge.graph.store import Direction


@runtime_checkable
class GraphReader(Protocol):
    """The read-only method surface a `PlannerStrategy` (a later phase's
    concern — not defined in this phase) is handed instead of the full
    `GraphStoreAdapter`. No implementation of this Protocol lives in this
    module — it is satisfied structurally by whatever `GraphStoreAdapter`
    instance a caller already has.
    """

    def get_node(self, node_id: str) -> GraphNode | None: ...

    def get_node_by_artifact_id(self, artifact_id: str) -> GraphNode | None: ...

    def outgoing_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]: ...

    def incoming_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]: ...

    def neighbors(
        self,
        node_id: str,
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        direction: Direction = "both",
    ) -> tuple[GraphNode, ...]: ...

    def traverse(
        self,
        seed_artifact_ids: Sequence[str],
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        max_depth: int,
        direction: Direction = "outgoing",
    ) -> tuple[GraphNode, ...]: ...

    def all_nodes(self) -> tuple[GraphNode, ...]: ...
