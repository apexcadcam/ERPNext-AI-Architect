"""The deterministic Knowledge Graph Projection — Sprint 10, Phase 3.

Converts `knowledge.domain` objects into the *existing* graph contracts
`knowledge.graph.GraphNode`/`GraphEdge` (Sprint 3) — representation only,
no storage, no graph technology, no reasoning, no querying, no indexing,
no persistence, no traversal algorithms.

**Compatibility finding: `knowledge.graph.builder.GraphBuilder` (Sprint 3)
already does conceptually the right thing, and is not reused directly.**
Its own docstring states the identical governing principle this phase's
brief restates — "invents no relationship — every edge it creates already
exists on the artifact's own, frozen `relationships`/`dependencies`
envelope fields... never mutates the artifact it reads." But it cannot be
called as-is here, for two structural reasons checked directly against
its source, not assumed:

1. `GraphBuilder.__init__(self, store: GraphStoreAdapter)` requires a live
   graph store — this phase's own brief explicitly forbids any storage
   dependency ("does NOT implement graph storage... does NOT depend on
   any graph technology").
2. `GraphBuilder.project()` raises `ArtifactNotValidatedError` unless
   `artifact.status is ArtifactStatus.VALIDATED` — its own stated
   precondition is entry into the Knowledge Factory's *validated* graph
   (Sprint 2/3's Extraction → Validation → Graph pipeline). Sprint 10's
   Knowledge layer has no Validation stage of its own; every `Workflow`
   `knowledge.builder` produces is left at the default `ArtifactStatus.
   DRAFT` (disclosed there, deliberately — Knowledge doesn't run
   Validation, so asserting a validated confidence would be fabricated).
   Requiring `VALIDATED` here would make projection of Sprint 10's own
   output permanently unreachable — the opposite of this phase's goal.

This module therefore implements its own storeless, precondition-free
projection function, reusing `GraphNode`/`GraphEdge`/`RelationshipType`
directly (no parallel graph concept is introduced) and mirroring
`GraphBuilder.project()`'s own edge-derivation logic — `relationships`
plus `dependencies`-as-`depends_on` — exactly, translated into node-id
addressed edges instead of store-created ones.

**Node identifiers.** `node_id = f"KG-{artifact.id}"` — a pure function of
the artifact's own id, not a sequential counter (`GraphStoreAdapter`'s own
`KG-NNNN` scheme is store-assigned and stateful; a counter would make this
function's output depend on call order, breaking determinism for a
storeless function). An edge's `target_node_id` is computed the same way
from a `relationships`/`dependencies` edge's own `target_id`, without
requiring the target artifact to have been projected in this same call —
the same "resolve by id alone, don't require the target object present"
discipline `GraphBuilder`'s own `_wraps_type_for_id` already established,
simplified here because `GraphEdge.target_node_id` is a plain string with
no `wraps_type` of its own to resolve.

**Only `KnowledgeCollection.artifacts` is projected into `GraphNode`s.**
`KnowledgeReference`s (the four Analysis fact kinds `knowledge.builder`
could not honestly turn into a `ContentArtifact` — `business_entity`,
`business_rule`, `business_constraint`, `actor`) are not projected either,
for the identical, already-disclosed reason: `GraphNode.wraps_type:
ArtifactType` has no value for any of them, and inventing one would be
extending a closed, frozen Sprint-2 vocabulary — exactly the "parallel
graph concept" this phase is forbidden from creating. `.references`
passes through every projection completely untouched.

**Idempotent, not merely deterministic.** `project_collection` always
*replaces* `.nodes`/`.edges` with what is freshly derived from
`.artifacts` — never appends to whatever was already there. Since
`.artifacts` is never itself modified by projection, projecting an
already-projected `KnowledgeCollection` recomputes the identical
`.nodes`/`.edges` and leaves the result unchanged: `project(project(x))
== project(x)`, not merely `project(x) == project(x)`.

Imports only `knowledge.domain`/`knowledge.artifacts`/`knowledge.graph`
(this project's own, frozen packages). No `analysis`, `intelligence`,
`planning`, `execution`, `runtime`, `orchestration`, or `integration`. No
graph library, no database SDK, no provider SDK, no networking.
"""

from __future__ import annotations

from knowledge.artifacts import ContentArtifact, RelationshipType
from knowledge.domain import KnowledgeCollection, KnowledgeSnapshot
from knowledge.graph import GraphEdge, GraphNode


def _node_id_for(artifact_id: str) -> str:
    return f"KG-{artifact_id}"


def project_artifact(artifact: ContentArtifact) -> GraphNode:
    """One `ContentArtifact` becomes exactly one `GraphNode` — always;
    unlike `GraphBuilder.project()`, this function does not skip artifacts
    with no edges, since there is no store here to keep proportionally
    sized — every artifact this Builder produced is worth representing.
    """

    return GraphNode(node_id=_node_id_for(artifact.id), wraps=artifact.id, wraps_type=artifact.type)


def project_artifact_edges(artifact: ContentArtifact) -> tuple[GraphEdge, ...]:
    """Mirrors `GraphBuilder.project()`'s own edge derivation exactly:
    `artifact.relationships` verbatim, plus `artifact.dependencies`
    translated to `RelationshipType.DEPENDS_ON` — nothing invented beyond
    what the artifact's own envelope fields already declare.
    """

    source_node_id = _node_id_for(artifact.id)
    edges = [
        GraphEdge(
            source_node_id=source_node_id,
            relationship=relationship_edge.relationship,
            target_node_id=_node_id_for(relationship_edge.target_id),
            note=relationship_edge.note,
        )
        for relationship_edge in artifact.relationships
    ]
    edges.extend(
        GraphEdge(
            source_node_id=source_node_id,
            relationship=RelationshipType.DEPENDS_ON,
            target_node_id=_node_id_for(dependency.target_id),
            note=dependency.reason,
        )
        for dependency in artifact.dependencies
    )
    return tuple(edges)


def project_collection(collection: KnowledgeCollection) -> KnowledgeCollection:
    """Returns a *new* `KnowledgeCollection` (frozen models are never
    mutated in place) with `.nodes`/`.edges` replaced by what `.artifacts`
    alone derives. `.collection_id`, `.name`, `.description`,
    `.artifacts`, and `.references` are carried over completely
    unchanged.
    """

    projected_nodes = tuple(project_artifact(artifact) for artifact in collection.artifacts)
    projected_edges = tuple(
        edge for artifact in collection.artifacts for edge in project_artifact_edges(artifact)
    )
    return collection.model_copy(update={"nodes": projected_nodes, "edges": projected_edges})


def project_snapshot(snapshot: KnowledgeSnapshot) -> KnowledgeSnapshot:
    """Projects every collection in `snapshot.collections`, in declared
    order. `.snapshot_id`, `.created_at`, and `.source` are carried over
    completely unchanged — this function touches only `.collections`.
    """

    return snapshot.model_copy(
        update={"collections": tuple(project_collection(collection) for collection in snapshot.collections)}
    )
