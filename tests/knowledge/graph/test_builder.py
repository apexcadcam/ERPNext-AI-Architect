"""Tests for `GraphBuilder` — the projection step from validated Knowledge
Artifacts into a Graph Store (SPRINT3_ARCHITECTURE_PACKAGE.md §7.3)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from knowledge.artifacts import (
    ArtifactStatus,
    DependencyEdge,
    KnowledgeAPI,
    RelationshipEdge,
    RelationshipType,
)
from knowledge.graph.builder import GraphBuilder
from knowledge.graph.errors import ArtifactNotValidatedError, DependsOnCycleError, UnknownArtifactPrefixError
from knowledge.graph.store import InMemoryGraphStore


@pytest.fixture
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore()


@pytest.fixture
def builder(store: InMemoryGraphStore) -> GraphBuilder:
    return GraphBuilder(store)


# -- No node for a relationship-less artifact ------------------------------------------


def test_artifact_with_no_edges_produces_no_node(
    builder: GraphBuilder, store: InMemoryGraphStore, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(status=ArtifactStatus.VALIDATED)

    result = builder.project(artifact)

    assert result is None
    assert store.all_nodes() == ()


# -- Invalid artifact handling --------------------------------------------------------


def test_non_validated_artifact_raises(
    builder: GraphBuilder, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(status=ArtifactStatus.DRAFT)
    with pytest.raises(ArtifactNotValidatedError):
        builder.project(artifact)


def test_edge_to_an_unrecognized_id_prefix_raises(
    builder: GraphBuilder, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="ZZ-0001", reason="bogus prefix"),),
    )
    with pytest.raises(UnknownArtifactPrefixError):
        builder.project(artifact)


# -- Node/edge creation from dependencies ----------------------------------------------


def test_project_creates_a_node_and_edge_from_a_dependency(
    builder: GraphBuilder, store: InMemoryGraphStore, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0002", reason="Link field"),),
    )

    node = builder.project(artifact)

    assert node is not None
    assert node.wraps == "KA-0001"
    target_node = store.get_node_by_artifact_id("KA-0002")
    assert target_node is not None
    edges = store.outgoing_edges(node.node_id)
    assert len(edges) == 1
    assert edges[0].relationship == RelationshipType.DEPENDS_ON
    assert edges[0].target_node_id == target_node.node_id
    assert edges[0].note == "Link field"


def test_project_creates_an_edge_from_an_explicit_relationship(
    builder: GraphBuilder, store: InMemoryGraphStore, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        relationships=(
            RelationshipEdge(target_id="KA-0002", relationship=RelationshipType.EXTENDS, note="specializes"),
        ),
    )

    node = builder.project(artifact)

    assert node is not None
    edges = store.outgoing_edges(node.node_id)
    assert len(edges) == 1
    assert edges[0].relationship == RelationshipType.EXTENDS


def test_project_never_mutates_the_source_artifact(
    builder: GraphBuilder, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),),
    )
    before = artifact.model_copy(deep=True)

    builder.project(artifact)

    assert artifact == before


# -- depends_on / relationships overlap dedup ------------------------------------------


def test_a_target_named_in_both_dependencies_and_relationships_yields_one_edge(
    builder: GraphBuilder, store: InMemoryGraphStore, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        relationships=(
            RelationshipEdge(
                target_id="KA-0002", relationship=RelationshipType.DEPENDS_ON, note="from relationships"
            ),
        ),
        dependencies=(DependencyEdge(target_id="KA-0002", reason="from dependencies"),),
    )

    node = builder.project(artifact)

    assert node is not None
    edges = store.outgoing_edges(node.node_id)
    assert len(edges) == 1
    assert edges[0].note == "from relationships"  # relationships processed first, first write wins


# -- Duplicate artifact handling --------------------------------------------------------


def test_projecting_the_same_artifact_twice_is_idempotent(
    builder: GraphBuilder, store: InMemoryGraphStore, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    artifact = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),),
    )

    first = builder.project(artifact)
    second = builder.project(artifact)

    assert first is not None and second is not None
    assert first.node_id == second.node_id
    assert len(store.all_nodes()) == 2  # KA-0001 and KA-0002 — not duplicated
    assert len(store.outgoing_edges(first.node_id)) == 1


def test_a_lazily_created_target_node_is_reused_when_that_artifact_is_later_projected(
    builder: GraphBuilder, store: InMemoryGraphStore, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    source = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),),
    )
    builder.project(source)
    placeholder = store.get_node_by_artifact_id("KA-0002")
    assert placeholder is not None

    target = make_knowledge_api(
        api_id="KA-0002",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0003", reason="y"),),
    )
    projected_target = builder.project(target)

    assert projected_target is not None
    assert projected_target.node_id == placeholder.node_id


# -- Cycle rejection bubbles up through the Builder --------------------------------------


def test_depends_on_cycle_across_two_artifacts_raises(
    builder: GraphBuilder, make_knowledge_api: Callable[..., KnowledgeAPI]
) -> None:
    first = make_knowledge_api(
        api_id="KA-0001",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),),
    )
    builder.project(first)

    second = make_knowledge_api(
        api_id="KA-0002",
        status=ArtifactStatus.VALIDATED,
        dependencies=(DependencyEdge(target_id="KA-0001", reason="y"),),
    )
    with pytest.raises(DependsOnCycleError):
        builder.project(second)
