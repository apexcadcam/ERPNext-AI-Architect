"""Tests for `IntelligenceAwarePlannerStrategy` (Sprint 12, Phase 1).
Mirrors `tests/planning/test_strategy.py`'s own fixture conventions
(`_ForbiddenGraph`, `_context`) rather than importing them — self-contained,
matching this project's established discipline.
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
from planning.strategy import PlannerStrategy
from planning.strategy_intelligence import IntelligenceAwarePlannerStrategy
from planning.validation import validate_plan

from intelligence.contract import TradeoffAssessment

_CREATED_AT = "2026-01-01T00:00:00Z"


class _GraphAccessForbidden(AssertionError):
    """Raised by `_ForbiddenGraph` if the strategy under test ever calls
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


_ENTITY_WORKFLOW = CapabilityDescriptor(
    capability="WF-entity", kind="read", idempotent=True, requires_confirmation=False
)
_PROCESS_WORKFLOW = CapabilityDescriptor(
    capability="WF-process", kind="write", idempotent=False, requires_confirmation=True
)
_OTHER_WORKFLOW = CapabilityDescriptor(
    capability="WF-other", kind="read", idempotent=True, requires_confirmation=False
)


def _context(*, capabilities: tuple[CapabilityDescriptor, ...]) -> PlanningContext:
    return PlanningContext(
        graph=_ForbiddenGraph(),
        available_capabilities=capabilities,
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )


def _goal() -> Goal:
    # desired_capabilities deliberately does NOT include the ranked
    # candidates -- this strategy must never consult it.
    return Goal(goal_id="G-1", intent="x", desired_capabilities=("unrelated.capability",))


def _assessment(*, ranked: tuple[str, ...], rationale: str = "scripted rationale") -> TradeoffAssessment:
    return TradeoffAssessment(ranked_candidate_ids=ranked, rationale=rationale, cited_evidence_ids=())


def _strategy(
    *, ranked: tuple[str, ...], rationale: str = "scripted rationale"
) -> IntelligenceAwarePlannerStrategy:
    return IntelligenceAwarePlannerStrategy(
        _assessment(ranked=ranked, rationale=rationale), created_at=_CREATED_AT
    )


# -- Contract conformance ----------------------------------------------------------------------


def test_is_a_planner_strategy() -> None:
    assert isinstance(_strategy(ranked=()), PlannerStrategy)


def test_exposes_no_additional_public_surface() -> None:
    public_attrs = {name for name in dir(IntelligenceAwarePlannerStrategy) if not name.startswith("_")}
    assert public_attrs == {"create_plan"}


# -- Successful plan generation ------------------------------------------------------------------


def test_successful_plan_generation_single_candidate() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    plan = _strategy(ranked=("WF-entity",)).create_plan(_goal(), context)

    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "WF-entity"
    assert plan.goal_id == "G-1"
    assert plan.strategy_name == "intelligence_aware"
    assert plan.created_at == _CREATED_AT


def test_multiple_ranked_candidates_produce_steps_in_ranked_order() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW, _PROCESS_WORKFLOW, _OTHER_WORKFLOW))
    plan = _strategy(ranked=("WF-process", "WF-other", "WF-entity")).create_plan(_goal(), context)

    assert [step.capability for step in plan.steps] == ["WF-process", "WF-other", "WF-entity"]


def test_duplicate_ranked_candidate_produces_exactly_one_step() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    plan = _strategy(ranked=("WF-entity", "WF-entity")).create_plan(_goal(), context)

    assert len(plan.steps) == 1


def test_unmatched_ranked_candidate_produces_no_step() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    plan = _strategy(ranked=("WF-unknown",)).create_plan(_goal(), context)

    assert plan.steps == ()


def test_partial_match_only_produces_steps_for_available_capabilities() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW, _OTHER_WORKFLOW))
    plan = _strategy(ranked=("WF-entity", "WF-unknown", "WF-other")).create_plan(_goal(), context)

    assert [step.capability for step in plan.steps] == ["WF-entity", "WF-other"]


# -- Empty TradeoffAssessment ---------------------------------------------------------------------


def test_empty_tradeoff_assessment_produces_an_empty_plan() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    plan = _strategy(ranked=()).create_plan(_goal(), context)

    assert plan.steps == ()


# -- Goal.desired_capabilities is never consulted -------------------------------------------------


def test_goal_desired_capabilities_is_never_consulted() -> None:
    goal = Goal(goal_id="G-1", intent="x", desired_capabilities=("WF-entity",))
    # available_capabilities intentionally omits WF-entity (goal's own
    # desired capability) and only supplies WF-process (the ranked one) --
    # if this strategy ever consulted goal.desired_capabilities, it would
    # find no matching descriptor and produce zero steps.
    context = _context(capabilities=(_PROCESS_WORKFLOW,))
    plan = _strategy(ranked=("WF-process",)).create_plan(goal, context)

    assert [step.capability for step in plan.steps] == ["WF-process"]


# -- requires_confirmation propagation -------------------------------------------------------------


def test_requires_confirmation_is_copied_from_the_descriptor_true_case() -> None:
    context = _context(capabilities=(_PROCESS_WORKFLOW,))
    plan = _strategy(ranked=("WF-process",)).create_plan(_goal(), context)

    assert plan.steps[0].requires_confirmation is True


def test_requires_confirmation_is_copied_from_the_descriptor_false_case() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    plan = _strategy(ranked=("WF-entity",)).create_plan(_goal(), context)

    assert plan.steps[0].requires_confirmation is False


# -- Rationale propagation --------------------------------------------------------------------------


def test_rationale_propagates_the_tradeoff_assessments_own_rationale() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    plan = _strategy(ranked=("WF-entity",), rationale="because it is the only real option").create_plan(
        _goal(), context
    )

    assert "because it is the only real option" in plan.steps[0].rationale
    assert "WF-entity" in plan.steps[0].rationale


# -- Step shape --------------------------------------------------------------------------------------


def test_step_has_no_dependencies_and_empty_parameters() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    plan = _strategy(ranked=("WF-entity",)).create_plan(_goal(), context)

    assert plan.steps[0].depends_on == ()
    assert plan.steps[0].parameters == {}


# -- No graph access -----------------------------------------------------------------------------------


def test_create_plan_never_accesses_the_graph() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))  # graph is _ForbiddenGraph
    _strategy(ranked=("WF-entity",)).create_plan(_goal(), context)  # must not raise


# -- No mutation -----------------------------------------------------------------------------------------


def test_create_plan_never_mutates_goal_or_context() -> None:
    goal = _goal()
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    goal_before = goal.model_copy(deep=True)
    capabilities_before = context.available_capabilities

    _strategy(ranked=("WF-entity",)).create_plan(goal, context)

    assert goal == goal_before
    assert context.available_capabilities == capabilities_before


# -- Invalid constructor arguments -----------------------------------------------------------------------


def test_empty_created_at_raises_value_error() -> None:
    with pytest.raises(ValueError):
        IntelligenceAwarePlannerStrategy(_assessment(ranked=()), created_at="")


# -- Determinism / repeated execution -----------------------------------------------------------------------


def test_repeated_calls_on_the_same_strategy_instance_produce_identical_plans() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW, _PROCESS_WORKFLOW))
    strategy = _strategy(ranked=("WF-process", "WF-entity"))

    first = strategy.create_plan(_goal(), context)
    second = strategy.create_plan(_goal(), context)

    assert first == second


def test_repeated_calls_across_separate_strategy_instances_are_identical() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))

    first = _strategy(ranked=("WF-entity",)).create_plan(_goal(), context)
    second = _strategy(ranked=("WF-entity",)).create_plan(_goal(), context)

    assert first == second


# -- PlanningEngine compatibility --------------------------------------------------------------------------


def test_works_through_planning_engine() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW, _PROCESS_WORKFLOW))
    engine = PlanningEngine()
    engine.register_strategy(_strategy(ranked=("WF-process", "WF-entity")))

    plan = engine.create_plan(_goal(), context)  # must pass validate_plan internally too

    assert [step.capability for step in plan.steps] == ["WF-process", "WF-entity"]
    assert plan.goal_id == "G-1"


def test_produces_an_empty_valid_plan_through_planning_engine() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW,))
    engine = PlanningEngine()
    engine.register_strategy(_strategy(ranked=()))

    plan = engine.create_plan(_goal(), context)

    assert plan.steps == ()


# -- validate_plan compatibility ----------------------------------------------------------------------------


def test_produced_plan_passes_validate_plan_directly() -> None:
    context = _context(capabilities=(_ENTITY_WORKFLOW, _PROCESS_WORKFLOW))
    plan = _strategy(ranked=("WF-process", "WF-entity")).create_plan(_goal(), context)

    report = validate_plan(plan, context, raise_on_failure=False)

    assert report.ok


def test_produced_plan_honestly_understating_confirmation_is_impossible() -> None:
    # requires_confirmation is always copied verbatim from the matching
    # descriptor, so validate_plan's own confirmation-understatement rule
    # can never fire against a plan this strategy produced.
    context = _context(capabilities=(_PROCESS_WORKFLOW,))
    plan = _strategy(ranked=("WF-process",)).create_plan(_goal(), context)

    report = validate_plan(plan, context, raise_on_failure=False)

    assert report.ok
    assert plan.steps[0].requires_confirmation is True
