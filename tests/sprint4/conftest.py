"""Shared fixtures for Sprint 4's final validation suite.

Self-contained, mirroring `tests/sprint3/conftest.py`'s own discipline: this
directory does not import fixtures or test doubles from `tests/planning/`
(a sibling, not an ancestor, so pytest would not cascade them here anyway),
to avoid cross-test-file coupling between what each phase's own test suite
independently proves.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from knowledge.artifacts import RelationshipType
from knowledge.graph import GraphEdge, GraphNode, InMemoryGraphStore
from knowledge.graph.store import Direction

from planning.contract import CapabilityDescriptor, Goal, RuntimeContextInfo
from planning.context import PlanningContext

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNING_DIR = REPO_ROOT / "planning"


class GraphAccessForbidden(AssertionError):
    """Raised by `ForbiddenGraph` if anything calls one of its methods."""


class ForbiddenGraph:
    """A `GraphReader`-shaped double where every method raises — used to
    *prove*, not merely assert, that a given call path never touches the
    Knowledge Graph.
    """

    def get_node(self, node_id: str) -> GraphNode | None:
        raise GraphAccessForbidden("get_node")

    def get_node_by_artifact_id(self, artifact_id: str) -> GraphNode | None:
        raise GraphAccessForbidden("get_node_by_artifact_id")

    def outgoing_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        raise GraphAccessForbidden("outgoing_edges")

    def incoming_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        raise GraphAccessForbidden("incoming_edges")

    def neighbors(
        self,
        node_id: str,
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        direction: Direction = "both",
    ) -> tuple[GraphNode, ...]:
        raise GraphAccessForbidden("neighbors")

    def traverse(
        self,
        seed_artifact_ids: Sequence[str],
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        max_depth: int,
        direction: Direction = "outgoing",
    ) -> tuple[GraphNode, ...]:
        raise GraphAccessForbidden("traverse")

    def all_nodes(self) -> tuple[GraphNode, ...]:
        raise GraphAccessForbidden("all_nodes")


READ_CAPABILITY = CapabilityDescriptor(
    capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
)
WRITE_CAPABILITY = CapabilityDescriptor(
    capability="filesystem.write_text", kind="write", idempotent=False, requires_confirmation=True
)
LIST_CAPABILITY = CapabilityDescriptor(
    capability="filesystem.list_directory", kind="read", idempotent=True, requires_confirmation=False
)


@pytest.fixture
def goal() -> Goal:
    return Goal(
        goal_id="G-1",
        intent="read then write a file",
        desired_capabilities=("filesystem.read_text", "filesystem.write_text"),
    )


@pytest.fixture
def empty_goal() -> Goal:
    return Goal(goal_id="G-2", intent="nothing to do here")


@pytest.fixture
def context() -> PlanningContext:
    return PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(READ_CAPABILITY, WRITE_CAPABILITY, LIST_CAPABILITY),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )


@pytest.fixture
def forbidden_graph_context() -> PlanningContext:
    return PlanningContext(
        graph=ForbiddenGraph(),
        available_capabilities=(READ_CAPABILITY, WRITE_CAPABILITY, LIST_CAPABILITY),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )
