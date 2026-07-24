"""Tests for `InMemoryGraphStore` against the `GraphStoreAdapter` contract
(SPRINT3_ARCHITECTURE_PACKAGE.md §7.4)."""

from __future__ import annotations

import pytest

from knowledge.artifacts import ArtifactType, RelationshipType
from knowledge.graph.errors import DependsOnCycleError, InconsistentNodeError
from knowledge.graph.store import InMemoryGraphStore


@pytest.fixture
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore()


# -- Empty graph -----------------------------------------------------------------


def test_empty_store_has_no_nodes(store: InMemoryGraphStore) -> None:
    assert store.all_nodes() == ()


def test_empty_store_lookups_return_none(store: InMemoryGraphStore) -> None:
    assert store.get_node("KG-0001") is None
    assert store.get_node_by_artifact_id("KA-0001") is None


def test_empty_store_traverse_returns_nothing(store: InMemoryGraphStore) -> None:
    assert store.traverse(["KA-0001"], max_depth=5) == ()


# -- create_node -------------------------------------------------------------------


def test_create_node_allocates_sequential_kg_ids(store: InMemoryGraphStore) -> None:
    first = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    second = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    assert first.node_id == "KG-0001"
    assert second.node_id == "KG-0002"


def test_create_node_is_idempotent_by_wraps(store: InMemoryGraphStore) -> None:
    first = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    second = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    assert first.node_id == second.node_id
    assert len(store.all_nodes()) == 1


def test_create_node_with_mismatched_type_raises(store: InMemoryGraphStore) -> None:
    store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    with pytest.raises(InconsistentNodeError):
        store.create_node("KA-0001", ArtifactType.PATTERN)


def test_get_node_by_artifact_id(store: InMemoryGraphStore) -> None:
    created = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    assert store.get_node_by_artifact_id("KA-0001") == created
    assert store.get_node(created.node_id) == created


# -- create_edge: unknown endpoints -------------------------------------------------


def test_create_edge_with_unknown_source_raises(store: InMemoryGraphStore) -> None:
    target = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    with pytest.raises(ValueError, match="unknown source"):
        store.create_edge("KG-9999", RelationshipType.DEPENDS_ON, target.node_id)


def test_create_edge_with_unknown_target_raises(store: InMemoryGraphStore) -> None:
    source = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    with pytest.raises(ValueError, match="unknown target"):
        store.create_edge(source.node_id, RelationshipType.DEPENDS_ON, "KG-9999")


# -- create_edge: idempotency --------------------------------------------------------


def test_create_edge_is_idempotent(store: InMemoryGraphStore) -> None:
    a = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    b = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)

    first = store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, b.node_id, note="first")
    second = store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, b.node_id, note="second")

    assert first == second
    assert first.note == "first"  # first write wins, per §4 "appended, never overwritten"
    assert len(store.outgoing_edges(a.node_id)) == 1


# -- Directed traversal (depends_on) --------------------------------------------------


def test_directed_edge_is_outgoing_from_source_only(store: InMemoryGraphStore) -> None:
    a = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    b = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, b.node_id)

    assert len(store.outgoing_edges(a.node_id)) == 1
    assert len(store.incoming_edges(a.node_id)) == 0
    assert len(store.outgoing_edges(b.node_id)) == 0
    assert len(store.incoming_edges(b.node_id)) == 1


def test_relationship_filter_narrows_edges(store: InMemoryGraphStore) -> None:
    a = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    b = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    c = store.create_node("KA-0003", ArtifactType.KNOWLEDGE_API)
    store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, b.node_id)
    store.create_edge(a.node_id, RelationshipType.REFERENCES, c.node_id)

    only_depends_on = store.outgoing_edges(a.node_id, relationship_filter=[RelationshipType.DEPENDS_ON])

    assert [e.target_node_id for e in only_depends_on] == [b.node_id]


# -- Symmetric relationships ----------------------------------------------------------


def test_symmetric_relationship_is_stored_once_regardless_of_call_direction(
    store: InMemoryGraphStore,
) -> None:
    a = store.create_node("PAT-0001", ArtifactType.PATTERN)
    b = store.create_node("PAT-0002", ArtifactType.PATTERN)

    edge_ab = store.create_edge(a.node_id, RelationshipType.RELATED_TO, b.node_id)
    edge_ba = store.create_edge(b.node_id, RelationshipType.RELATED_TO, a.node_id)

    assert edge_ab == edge_ba
    assert len(store.outgoing_edges(a.node_id)) + len(store.outgoing_edges(b.node_id)) == 2


def test_symmetric_relationship_is_a_neighbor_from_both_endpoints(store: InMemoryGraphStore) -> None:
    a = store.create_node("PAT-0001", ArtifactType.PATTERN)
    b = store.create_node("PAT-0002", ArtifactType.PATTERN)
    store.create_edge(a.node_id, RelationshipType.CONFLICTS_WITH, b.node_id)

    assert [n.node_id for n in store.neighbors(a.node_id)] == [b.node_id]
    assert [n.node_id for n in store.neighbors(b.node_id)] == [a.node_id]


# -- depends_on cycle rejection -----------------------------------------------------------


def test_depends_on_self_loop_is_rejected(store: InMemoryGraphStore) -> None:
    a = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    with pytest.raises(DependsOnCycleError):
        store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, a.node_id)


def test_transitive_depends_on_cycle_is_rejected(store: InMemoryGraphStore) -> None:
    a = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    b = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    c = store.create_node("KA-0003", ArtifactType.KNOWLEDGE_API)
    store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, b.node_id)
    store.create_edge(b.node_id, RelationshipType.DEPENDS_ON, c.node_id)

    with pytest.raises(DependsOnCycleError):
        store.create_edge(c.node_id, RelationshipType.DEPENDS_ON, a.node_id)


def test_non_cyclic_depends_on_chain_is_accepted(store: InMemoryGraphStore) -> None:
    a = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    b = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    c = store.create_node("KA-0003", ArtifactType.KNOWLEDGE_API)
    store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, b.node_id)

    edge = store.create_edge(b.node_id, RelationshipType.DEPENDS_ON, c.node_id)

    assert edge.target_node_id == c.node_id


def test_a_shared_dependency_is_not_mistaken_for_a_cycle(store: InMemoryGraphStore) -> None:
    # A -> C and B -> C (diamond shape) must not be rejected as a cycle.
    a = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    b = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    c = store.create_node("KA-0003", ArtifactType.KNOWLEDGE_API)
    store.create_edge(a.node_id, RelationshipType.DEPENDS_ON, c.node_id)

    edge = store.create_edge(b.node_id, RelationshipType.DEPENDS_ON, c.node_id)

    assert edge.target_node_id == c.node_id


# -- Traversal --------------------------------------------------------------------------


def test_traverse_includes_the_seed_first(store: InMemoryGraphStore) -> None:
    store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)

    result = store.traverse(["KA-0001"], max_depth=3)

    assert [n.wraps for n in result] == ["KA-0001"]


def test_traverse_walks_a_multi_hop_chain_in_order(store: InMemoryGraphStore) -> None:
    # Sales Invoice -> Customer -> Address, per
    # SPRINT3_ARCHITECTURE_PACKAGE.md §7.6's worked example.
    invoice = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    customer = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    address = store.create_node("KA-0003", ArtifactType.KNOWLEDGE_API)
    store.create_edge(invoice.node_id, RelationshipType.DEPENDS_ON, customer.node_id)
    store.create_edge(customer.node_id, RelationshipType.DEPENDS_ON, address.node_id)

    result = store.traverse(["KA-0001"], relationship_filter=[RelationshipType.DEPENDS_ON], max_depth=2)

    assert [n.wraps for n in result] == ["KA-0001", "KA-0002", "KA-0003"]


def test_traverse_respects_max_depth(store: InMemoryGraphStore) -> None:
    invoice = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    customer = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    address = store.create_node("KA-0003", ArtifactType.KNOWLEDGE_API)
    store.create_edge(invoice.node_id, RelationshipType.DEPENDS_ON, customer.node_id)
    store.create_edge(customer.node_id, RelationshipType.DEPENDS_ON, address.node_id)

    result = store.traverse(["KA-0001"], max_depth=1)

    assert [n.wraps for n in result] == ["KA-0001", "KA-0002"]


def test_traverse_max_depth_zero_returns_only_seeds(store: InMemoryGraphStore) -> None:
    invoice = store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)
    customer = store.create_node("KA-0002", ArtifactType.KNOWLEDGE_API)
    store.create_edge(invoice.node_id, RelationshipType.DEPENDS_ON, customer.node_id)

    result = store.traverse(["KA-0001"], max_depth=0)

    assert [n.wraps for n in result] == ["KA-0001"]


def test_traverse_negative_max_depth_raises(store: InMemoryGraphStore) -> None:
    with pytest.raises(ValueError, match="max_depth"):
        store.traverse(["KA-0001"], max_depth=-1)


def test_traverse_unknown_seed_is_skipped_not_an_error(store: InMemoryGraphStore) -> None:
    store.create_node("KA-0001", ArtifactType.KNOWLEDGE_API)

    result = store.traverse(["KA-9999"], max_depth=2)

    assert result == ()


def test_traverse_never_revisits_a_node_in_a_cyclic_shaped_relationship_graph(
    store: InMemoryGraphStore,
) -> None:
    # related_to is symmetric — a naive walk could bounce back and forth
    # forever; traversal must visit each node once.
    a = store.create_node("PAT-0001", ArtifactType.PATTERN)
    b = store.create_node("PAT-0002", ArtifactType.PATTERN)
    store.create_edge(a.node_id, RelationshipType.RELATED_TO, b.node_id)

    result = store.traverse(["PAT-0001"], max_depth=5)

    assert [n.wraps for n in result] == ["PAT-0001", "PAT-0002"]
