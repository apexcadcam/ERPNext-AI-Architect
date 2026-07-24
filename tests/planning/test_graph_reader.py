"""Tests for `GraphReader` (approved Sprint 4 Architecture Package §5.7,
ADR-0011).

No graph traversal behavior is tested here — `GraphReader` defines a
structural contract only, and no implementation of it lives in `planning/`
in this phase. These tests verify the Protocol's shape and that the real,
existing `knowledge.graph.InMemoryGraphStore` already satisfies it.
"""

from __future__ import annotations

from typing import get_type_hints

from knowledge.graph import GraphStoreAdapter, InMemoryGraphStore

from planning.graph_reader import GraphReader

_READ_METHODS = {
    "get_node",
    "get_node_by_artifact_id",
    "outgoing_edges",
    "incoming_edges",
    "neighbors",
    "traverse",
    "all_nodes",
}
_WRITE_METHODS = {"create_node", "create_edge"}


def test_graph_reader_is_a_protocol() -> None:
    # typing.Protocol classes carry this internal marker; issubclass()
    # against typing.Protocol itself is not a supported static check.
    assert getattr(GraphReader, "_is_protocol", False) is True


def test_graph_reader_exposes_exactly_the_seven_read_methods() -> None:
    members = {name for name in vars(GraphReader) if not name.startswith("_")}
    assert members == _READ_METHODS


def test_graph_reader_exposes_no_write_method() -> None:
    members = {name for name in vars(GraphReader) if not name.startswith("_")}
    assert members.isdisjoint(_WRITE_METHODS)


def test_in_memory_graph_store_satisfies_graph_reader_structurally() -> None:
    store = InMemoryGraphStore()
    assert isinstance(store, GraphReader)


def test_in_memory_graph_store_still_has_its_own_write_methods() -> None:
    # GraphReader narrows the *type* a caller is handed; it does not, and
    # cannot, remove create_node/create_edge from the real object itself —
    # ADR-0011's own disclosed reasoning.
    store = InMemoryGraphStore()
    assert hasattr(store, "create_node")
    assert hasattr(store, "create_edge")


def test_graph_reader_method_signatures_match_graph_store_adapter() -> None:
    # Every GraphReader method must be present, with the same parameter
    # names, on the real GraphStoreAdapter it mirrors — proving this
    # Protocol was copied from, not merely inspired by, the Adapter.
    reader_hints = get_type_hints(GraphReader.get_node)
    adapter_hints = get_type_hints(GraphStoreAdapter.get_node)
    assert reader_hints == adapter_hints

    for method_name in _READ_METHODS:
        assert hasattr(GraphStoreAdapter, method_name)


def test_graph_reader_has_no_abstract_class_left_unimplemented_by_a_real_store() -> None:
    # A real GraphStoreAdapter subclass is never abstract with respect to
    # GraphReader's narrower surface.
    store = InMemoryGraphStore()
    for method_name in _READ_METHODS:
        assert callable(getattr(store, method_name))
