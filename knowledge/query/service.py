"""The deterministic Knowledge Query service — Sprint 10, Phase 4.

A read-only API over one already-built `knowledge.domain.KnowledgeSnapshot`
— no graph traversal, no indexing, no caching, no persistence, no
reasoning, no AI. Every method is a plain linear scan performed fresh on
each call over the snapshot's own, already-immutable data; nothing is
pre-built, cached, or mutated across calls.

**API derivation, disclosed rather than invented:** every method maps
directly onto one of `KnowledgeCollection`'s four existing fields —
`artifacts`, `nodes`, `edges`, `references` — plus collection-level
identity (`collection_id`) and the pre-existing `KnowledgeStatistics`
type (Sprint 10 Phase 1). `list_nodes`/`find_node`/`list_edges` are not
named in this phase's own "suggested" list, but are included for the same
reason: `nodes`/`edges` are peers of `artifacts`/`references` on
`KnowledgeCollection` itself — querying two of the four existing fields
and skipping the other two would be the more arbitrary choice, not this
one. Nothing here queries anything `KnowledgeCollection` does not already
carry.

**`list_references`'s filters mirror `KnowledgeReference`'s own three
fields exactly** (`analysis_id`, `subject_id`, `subject_kind`) — the only
three things a caller could legitimately search a reference by, since
`KnowledgeReference` has no id of its own. `subject_kind` is validated
against the same five-value vocabulary `KnowledgeReference.subject_kind`'s
own `Literal` already fixes (kept as a plain, explicit tuple here rather
than derived via runtime type introspection from that `Literal` — the
more explicit, more auditable choice); passing anything else raises
`ValueError` immediately rather than silently matching nothing.

**Scope: one `KnowledgeSnapshot` per service instance.** Querying across
multiple accumulated snapshots is a persistence/accumulation concern this
phase's own brief places out of scope — a future phase's job, not a
redesign of this one's constructor.

**`statistics()` is per-collection, never snapshot-wide.**
`KnowledgeStatistics.collection_id: str` (Phase 1) is a required field
describing exactly one collection; inventing a snapshot-wide aggregate
would mean populating that field with something that doesn't identify a
real collection, which this service does not do. `list_statistics()`
computes one `KnowledgeStatistics` per collection instead.

Imports only `knowledge.domain`/`knowledge.artifacts`/`knowledge.graph`
(this project's own, frozen packages). No `analysis`, `intelligence`,
`planning`, `execution`, `runtime`, `orchestration`, or `integration`. No
graph library, no database SDK, no provider SDK, no networking.
"""

from __future__ import annotations

from knowledge.artifacts import ContentArtifact
from knowledge.domain import KnowledgeCollection, KnowledgeReference, KnowledgeSnapshot, KnowledgeStatistics
from knowledge.graph import GraphEdge, GraphNode

#: Mirrors `KnowledgeReference.subject_kind`'s own `Literal` values exactly
#: (Sprint 10 Phase 1) — kept in sync by hand, disclosed here rather than
#: derived through runtime type introspection, for auditability.
_VALID_SUBJECT_KINDS = (
    "business_entity",
    "business_process",
    "business_rule",
    "business_constraint",
    "actor",
)


class KnowledgeQueryService:
    """A read-only view over one `KnowledgeSnapshot`. Never mutates the
    snapshot or anything it contains — every method returns data, never
    assigns to it.
    """

    def __init__(self, snapshot: KnowledgeSnapshot) -> None:
        self._snapshot = snapshot

    # -- Collections --------------------------------------------------------------------------

    def list_collections(self) -> tuple[KnowledgeCollection, ...]:
        """Every collection, in the snapshot's own declared order."""

        return self._snapshot.collections

    def find_collection(self, collection_id: str) -> KnowledgeCollection | None:
        for collection in self._snapshot.collections:
            if collection.collection_id == collection_id:
                return collection
        return None

    def _collections(self, *, collection_id: str | None) -> tuple[KnowledgeCollection, ...]:
        if collection_id is None:
            return self._snapshot.collections
        collection = self.find_collection(collection_id)
        return (collection,) if collection is not None else ()

    # -- Artifacts ------------------------------------------------------------------------------

    def list_artifacts(self, *, collection_id: str | None = None) -> tuple[ContentArtifact, ...]:
        return tuple(
            artifact
            for collection in self._collections(collection_id=collection_id)
            for artifact in collection.artifacts
        )

    def find_artifact(self, artifact_id: str) -> ContentArtifact | None:
        """The first match, in declared collection/artifact order, if the
        same id appears more than once (duplicates are not merged or
        deduplicated here — see the Builder's own identical discipline).
        """

        for artifact in self.list_artifacts():
            if artifact.id == artifact_id:
                return artifact
        return None

    # -- Graph nodes / edges ----------------------------------------------------------------------

    def list_nodes(self, *, collection_id: str | None = None) -> tuple[GraphNode, ...]:
        return tuple(
            node for collection in self._collections(collection_id=collection_id) for node in collection.nodes
        )

    def find_node(self, node_id: str) -> GraphNode | None:
        for node in self.list_nodes():
            if node.node_id == node_id:
                return node
        return None

    def list_edges(self, *, collection_id: str | None = None) -> tuple[GraphEdge, ...]:
        return tuple(
            edge for collection in self._collections(collection_id=collection_id) for edge in collection.edges
        )

    # -- References -------------------------------------------------------------------------------

    def list_references(
        self,
        *,
        collection_id: str | None = None,
        analysis_id: str | None = None,
        subject_id: str | None = None,
        subject_kind: str | None = None,
    ) -> tuple[KnowledgeReference, ...]:
        if subject_kind is not None and subject_kind not in _VALID_SUBJECT_KINDS:
            raise ValueError(
                f"'{subject_kind}' is not a recognized subject_kind — expected one of {_VALID_SUBJECT_KINDS}"
            )

        references = (
            reference
            for collection in self._collections(collection_id=collection_id)
            for reference in collection.references
        )
        if analysis_id is not None:
            references = (reference for reference in references if reference.analysis_id == analysis_id)
        if subject_id is not None:
            references = (reference for reference in references if reference.subject_id == subject_id)
        if subject_kind is not None:
            references = (reference for reference in references if reference.subject_kind == subject_kind)
        return tuple(references)

    # -- Statistics -----------------------------------------------------------------------------

    def statistics(self, collection_id: str) -> KnowledgeStatistics | None:
        collection = self.find_collection(collection_id)
        if collection is None:
            return None

        counts_by_artifact_type: dict[str, int] = {}
        for artifact in collection.artifacts:
            counts_by_artifact_type[artifact.type.value] = (
                counts_by_artifact_type.get(artifact.type.value, 0) + 1
            )

        return KnowledgeStatistics(
            collection_id=collection.collection_id,
            artifact_count=len(collection.artifacts),
            node_count=len(collection.nodes),
            relationship_count=len(collection.edges),
            counts_by_artifact_type=counts_by_artifact_type,
        )

    def list_statistics(self) -> tuple[KnowledgeStatistics, ...]:
        """One `KnowledgeStatistics` per collection, in declared order."""

        statistics = (self.statistics(collection.collection_id) for collection in self._snapshot.collections)
        return tuple(entry for entry in statistics if entry is not None)
