"""The Graph Build Engine: projects validated Knowledge Artifacts into a
Graph Store, per SPRINT3_ARCHITECTURE_PACKAGE.md §7.3.

A pure projection step. It invents no relationship — every edge it creates
already exists on the artifact's own, frozen `relationships`/`dependencies`
envelope fields (knowledge/artifacts/envelope.py, Sprint 2, unmodified). It
never mutates the artifact it reads. Per
docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md §4, an artifact with zero
edges gets no node at all — the graph's size stays proportional to actual
connectivity, not to total artifact count.
"""

from __future__ import annotations

from knowledge.artifacts import (
    ARTIFACT_ID_PREFIXES,
    ArtifactStatus,
    ArtifactType,
    ContentArtifact,
    RelationshipEdge,
    RelationshipType,
)
from knowledge.graph.errors import ArtifactNotValidatedError, UnknownArtifactPrefixError
from knowledge.graph.model import GraphNode
from knowledge.graph.store import GraphStoreAdapter

#: The reverse of ARTIFACT_ID_PREFIXES — lets the Builder determine an edge
#: target's `wraps_type` from its id alone (e.g. "KA-0042" -> KNOWLEDGE_API),
#: without requiring the target's own artifact object to have been
#: projected yet. This is not an inference or a heuristic: it is the same
#: prefix<->type mapping knowledge/artifacts/envelope.py's own
#: `_id_matches_type_prefix` validator already enforces on every artifact id
#: at construction time.
_TYPE_BY_PREFIX: dict[str, ArtifactType] = {prefix: kind for kind, prefix in ARTIFACT_ID_PREFIXES.items()}


def _wraps_type_for_id(artifact_id: str) -> ArtifactType:
    prefix = artifact_id.split("-", 1)[0]
    kind = _TYPE_BY_PREFIX.get(prefix)
    if kind is None:
        raise UnknownArtifactPrefixError(
            f"id '{artifact_id}' has no recognized artifact-type prefix among "
            f"{sorted(_TYPE_BY_PREFIX)} — cannot determine its graph node's wraps_type"
        )
    return kind


class GraphBuilder:
    """Projects one validated `ContentArtifact` at a time into `store`.
    Depends only on `GraphStoreAdapter`'s abstract contract — never on
    `InMemoryGraphStore` concretely — so a future Graph Store backend is
    swappable here without any change to this class.
    """

    def __init__(self, store: GraphStoreAdapter) -> None:
        self._store = store

    def project(self, artifact: ContentArtifact) -> GraphNode | None:
        """Projects `artifact`'s `relationships`/`dependencies` fields into
        the Graph Store. Returns the artifact's own `GraphNode` if one was
        created or already existed, or `None` if this artifact has no edges
        at all (per §4, no node is created for it).

        Raises `ArtifactNotValidatedError` if `artifact.status` is not
        `ArtifactStatus.VALIDATED` — §7.3's own stated precondition for the
        Graph Build Engine's input.
        """

        if artifact.status is not ArtifactStatus.VALIDATED:
            raise ArtifactNotValidatedError(
                f"artifact '{artifact.id}' has status '{artifact.status.value}', "
                f"the Graph Build Engine only projects status='validated' artifacts"
            )

        edges = list(artifact.relationships) + [
            RelationshipEdge(
                target_id=dependency.target_id,
                relationship=RelationshipType.DEPENDS_ON,
                note=dependency.reason,
            )
            for dependency in artifact.dependencies
        ]
        if not edges:
            return None

        source_node = self._store.create_node(wraps=artifact.id, wraps_type=artifact.type)
        for edge in edges:
            target_node = self._store.create_node(
                wraps=edge.target_id, wraps_type=_wraps_type_for_id(edge.target_id)
            )
            self._store.create_edge(
                source_node.node_id, edge.relationship, target_node.node_id, note=edge.note
            )
        return source_node
