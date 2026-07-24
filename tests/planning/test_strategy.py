"""Tests for `PlannerStrategy` and `RuleBasedPlannerStrategy` (approved
Sprint 4 Architecture Package §3.3/§4.2, Migration Strategy §11 step 5).
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from knowledge.artifacts import RelationshipType
from knowledge.graph import GraphEdge, GraphNode
from knowledge.graph.store import Direction

from planning.contract import CapabilityDescriptor, Goal, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import PlannerStrategy, RuleBasedPlannerStrategy


class _GraphAccessForbidden(AssertionError):
    """Raised by `_ForbiddenGraph` if `RuleBasedPlannerStrategy` ever calls
    any `GraphReader` method — proving, not merely asserting, "no graph
    access."
    """


class _ForbiddenGraph:
    """A `GraphReader`-shaped double where every method raises. Passed as
    `PlanningContext.graph` so any access at all fails the test loudly.
    """

    def get_node(self, node_id: str) -> GraphNode | None:
        raise _GraphAccessForbidden("get_node")

    def get_node_by_artifact_id(self, artifact_id: str) -> GraphNode | None:
        raise _GraphAccessForbidden("get_node_by_artifact_id")

    def outgoing_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        raise _GraphAccessForbidden("outgoing_edges")

    def incoming_edges(
        self, node_id: str, relationship_filter: Sequence[RelationshipType] | None = None
    ) -> tuple[GraphEdge, ...]:
        raise _GraphAccessForbidden("incoming_edges")

    def neighbors(
        self,
        node_id: str,
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        direction: Direction = "both",
    ) -> tuple[GraphNode, ...]:
        raise _GraphAccessForbidden("neighbors")

    def traverse(
        self,
        seed_artifact_ids: Sequence[str],
        *,
        relationship_filter: Sequence[RelationshipType] | None = None,
        max_depth: int,
        direction: Direction = "outgoing",
    ) -> tuple[GraphNode, ...]:
        raise _GraphAccessForbidden("traverse")

    def all_nodes(self) -> tuple[GraphNode, ...]:
        raise _GraphAccessForbidden("all_nodes")


_READ = CapabilityDescriptor(
    capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
)
_WRITE = CapabilityDescriptor(
    capability="filesystem.write_text", kind="write", idempotent=False, requires_confirmation=True
)
_LIST = CapabilityDescriptor(
    capability="filesystem.list_directory", kind="read", idempotent=True, requires_confirmation=False
)


def _context(*, capabilities: tuple[CapabilityDescriptor, ...]) -> PlanningContext:
    return PlanningContext(
        graph=_ForbiddenGraph(),
        available_capabilities=capabilities,
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )


# -- Contract ---------------------------------------------------------------------------


def test_planner_strategy_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        PlannerStrategy()  # type: ignore[abstract]


def test_rule_based_planner_strategy_is_a_planner_strategy() -> None:
    assert isinstance(RuleBasedPlannerStrategy(), PlannerStrategy)


def test_planner_strategy_exposes_only_create_plan() -> None:
    public_attrs = {name for name in dir(PlannerStrategy) if not name.startswith("_")}
    assert public_attrs == {"create_plan"}


# -- One step per matching capability, in order ------------------------------------------


def test_one_step_per_matching_capability() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text",))
    context = _context(capabilities=(_READ,))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "filesystem.read_text"


def test_deterministic_ordering_follows_goal_desired_capabilities_order() -> None:
    goal = Goal(
        goal_id="G-1",
        intent="x",
        desired_capabilities=("filesystem.write_text", "filesystem.read_text", "filesystem.list_directory"),
    )
    context = _context(capabilities=(_READ, _WRITE, _LIST))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert [step.capability for step in plan.steps] == [
        "filesystem.write_text",
        "filesystem.read_text",
        "filesystem.list_directory",
    ]


def test_ordering_is_never_derived_from_available_capabilities_order() -> None:
    # available_capabilities is in a different order than desired_capabilities
    # -- the Plan's step order must follow the Goal, not the context.
    goal = Goal(
        goal_id="G-1", intent="x", desired_capabilities=("filesystem.list_directory", "filesystem.read_text")
    )
    context = _context(capabilities=(_READ, _WRITE, _LIST))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert [step.capability for step in plan.steps] == ["filesystem.list_directory", "filesystem.read_text"]


def test_duplicate_desired_capability_produces_exactly_one_step() -> None:
    goal = Goal(
        goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text", "filesystem.read_text")
    )
    context = _context(capabilities=(_READ,))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert len(plan.steps) == 1


# -- Empty desired_capabilities -----------------------------------------------------------


def test_empty_desired_capabilities_produces_an_empty_plan() -> None:
    goal = Goal(goal_id="G-1", intent="x")
    context = _context(capabilities=(_READ, _WRITE))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert plan.steps == ()


# -- Unmatched capability / partial matches ------------------------------------------------


def test_unmatched_capability_produces_no_step() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("erpnext.write_record",))
    context = _context(capabilities=(_READ,))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert plan.steps == ()


def test_partial_match_only_produces_steps_for_available_capabilities() -> None:
    goal = Goal(
        goal_id="G-1",
        intent="x",
        desired_capabilities=("filesystem.read_text", "erpnext.write_record", "filesystem.list_directory"),
    )
    context = _context(capabilities=(_READ, _LIST))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert [step.capability for step in plan.steps] == ["filesystem.read_text", "filesystem.list_directory"]


# -- Confirmation propagation ---------------------------------------------------------------


def test_requires_confirmation_is_copied_from_the_descriptor_true_case() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("filesystem.write_text",))
    context = _context(capabilities=(_WRITE,))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert plan.steps[0].requires_confirmation is True


def test_requires_confirmation_is_copied_from_the_descriptor_false_case() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text",))
    context = _context(capabilities=(_READ,))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert plan.steps[0].requires_confirmation is False


# -- Step shape ------------------------------------------------------------------------------


def test_step_has_no_dependencies_and_empty_parameters() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text",))
    context = _context(capabilities=(_READ,))

    plan = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert plan.steps[0].depends_on == ()
    assert plan.steps[0].parameters == {}
    assert plan.steps[0].rationale != ""


# -- No graph access ---------------------------------------------------------------------------


def test_create_plan_never_accesses_the_graph() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text",))
    context = _context(capabilities=(_READ,))  # graph is _ForbiddenGraph

    RuleBasedPlannerStrategy().create_plan(goal, context)  # must not raise


# -- No mutation ------------------------------------------------------------------------------


def test_create_plan_never_mutates_goal_or_context() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text",))
    context = _context(capabilities=(_READ,))
    goal_before = goal.model_copy(deep=True)
    context_before_capabilities = context.available_capabilities

    RuleBasedPlannerStrategy().create_plan(goal, context)

    assert goal == goal_before
    assert context.available_capabilities == context_before_capabilities


# -- Determinism / repeated calls --------------------------------------------------------------


def test_repeated_calls_produce_identical_plans() -> None:
    goal = Goal(
        goal_id="G-1", intent="x", desired_capabilities=("filesystem.write_text", "filesystem.read_text")
    )
    context = _context(capabilities=(_READ, _WRITE))
    strategy = RuleBasedPlannerStrategy()

    first = strategy.create_plan(goal, context)
    second = strategy.create_plan(goal, context)

    assert first == second


def test_repeated_calls_across_separate_strategy_instances_are_identical() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text",))
    context = _context(capabilities=(_READ,))

    first = RuleBasedPlannerStrategy().create_plan(goal, context)
    second = RuleBasedPlannerStrategy().create_plan(goal, context)

    assert first == second


# -- Through PlanningEngine --------------------------------------------------------------------


def test_rule_based_strategy_works_through_planning_engine() -> None:
    goal = Goal(
        goal_id="G-1", intent="x", desired_capabilities=("filesystem.read_text", "filesystem.write_text")
    )
    context = _context(capabilities=(_READ, _WRITE))
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    plan = engine.create_plan(goal, context)  # must pass validate_plan internally too

    assert [step.capability for step in plan.steps] == ["filesystem.read_text", "filesystem.write_text"]
    assert plan.goal_id == "G-1"


def test_rule_based_strategy_produces_an_empty_valid_plan_through_planning_engine() -> None:
    goal = Goal(goal_id="G-1", intent="x")
    context = _context(capabilities=(_READ,))
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    plan = engine.create_plan(goal, context)

    assert plan.steps == ()
