"""Tests for `PlanningEngine` (approved Sprint 4 Architecture Package
§3.2/§4.1, scoped to Phase 4's own five-step Responsibilities list).

Uses `_FunctionStrategy`, a minimal local test double wrapping a plain
function into the permanent `PlannerStrategy` contract (Phase 5) — not
`RuleBasedPlannerStrategy` itself, which has its own dedicated test module
and its own "works through PlanningEngine" integration test there.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from knowledge.graph import InMemoryGraphStore
from pytest import MonkeyPatch

from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.errors import PlannerStrategyError, PlanValidationError
from planning.strategy import PlannerStrategy
from planning.validation import PlanValidationReport


class _FunctionStrategy(PlannerStrategy):
    """Wraps a plain function as a `PlannerStrategy`, so test bodies can
    stay expressed as simple functions/lambdas rather than one-off classes.
    """

    def __init__(self, func: Callable[[Goal, PlanningContext], Plan]) -> None:
        self._func = func

    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        return self._func(goal, context)


@pytest.fixture
def goal() -> Goal:
    return Goal(goal_id="G-1", intent="do the thing")


@pytest.fixture
def context() -> PlanningContext:
    return PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(
            CapabilityDescriptor(
                capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
            ),
        ),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )


def _valid_plan(goal_id: str = "G-1") -> Plan:
    return Plan(
        plan_id="P-1",
        goal_id=goal_id,
        steps=(PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False),),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )


def _invalid_plan(goal_id: str = "G-1") -> Plan:
    return Plan(
        plan_id="P-1",
        goal_id=goal_id,
        steps=(PlanStep(step_id="S-1", capability="unknown.capability", requires_confirmation=False),),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )


# -- Strategy invocation ---------------------------------------------------------------


def test_create_plan_invokes_the_registered_strategy_with_goal_and_context(
    goal: Goal, context: PlanningContext
) -> None:
    received: list[tuple[Goal, PlanningContext]] = []

    def stub_strategy(g: Goal, c: PlanningContext) -> Plan:
        received.append((g, c))
        return _valid_plan()

    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(stub_strategy))

    engine.create_plan(goal, context)

    assert received == [(goal, context)]


def test_create_plan_returns_the_strategys_validated_plan(goal: Goal, context: PlanningContext) -> None:
    plan = _valid_plan()
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: plan))

    result = engine.create_plan(goal, context)

    assert result is plan


# -- Orchestration order --------------------------------------------------------------


def test_orchestration_calls_strategy_before_validate_plan(
    goal: Goal, context: PlanningContext, monkeypatch: MonkeyPatch
) -> None:
    call_order: list[str] = []
    plan = _valid_plan()

    def stub_strategy(g: Goal, c: PlanningContext) -> Plan:
        call_order.append("strategy")
        return plan

    def fake_validate_plan(
        candidate: Plan, ctx: PlanningContext, *, raise_on_failure: bool = True
    ) -> PlanValidationReport:
        call_order.append("validate_plan")
        assert candidate is plan
        assert ctx is context
        return PlanValidationReport()

    monkeypatch.setattr("planning.engine.validate_plan", fake_validate_plan)

    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(stub_strategy))
    engine.create_plan(goal, context)

    assert call_order == ["strategy", "validate_plan"]


def test_validate_plan_is_invoked_exactly_once(
    goal: Goal, context: PlanningContext, monkeypatch: MonkeyPatch
) -> None:
    calls = 0

    def fake_validate_plan(
        candidate: Plan, ctx: PlanningContext, *, raise_on_failure: bool = True
    ) -> PlanValidationReport:
        nonlocal calls
        calls += 1
        return PlanValidationReport()

    monkeypatch.setattr("planning.engine.validate_plan", fake_validate_plan)

    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: _valid_plan()))
    engine.create_plan(goal, context)

    assert calls == 1


# -- No strategy configured -------------------------------------------------------------


def test_create_plan_raises_when_no_strategy_is_registered(goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    with pytest.raises(PlannerStrategyError):
        engine.create_plan(goal, context)


# -- register_strategy -------------------------------------------------------------------


def test_register_strategy_twice_without_override_raises() -> None:
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: _valid_plan()))
    with pytest.raises(PlannerStrategyError):
        engine.register_strategy(_FunctionStrategy(lambda g, c: _valid_plan()))


def test_register_strategy_with_override_replaces_the_active_strategy(
    goal: Goal, context: PlanningContext
) -> None:
    first_plan = _valid_plan()
    second_plan = _valid_plan()
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: first_plan))
    engine.register_strategy(_FunctionStrategy(lambda g, c: second_plan), override=True)

    result = engine.create_plan(goal, context)

    assert result is second_plan


# -- Error propagation --------------------------------------------------------------------


def test_strategy_raising_is_wrapped_as_planner_strategy_error(goal: Goal, context: PlanningContext) -> None:
    def broken_strategy(g: Goal, c: PlanningContext) -> Plan:
        raise ValueError("no viable path found")

    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(broken_strategy))

    with pytest.raises(PlannerStrategyError) as excinfo:
        engine.create_plan(goal, context)

    assert "no viable path found" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, ValueError)


def test_strategy_returning_a_non_plan_raises_planner_strategy_error(
    goal: Goal, context: PlanningContext
) -> None:
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: "not a plan"))  # type: ignore[arg-type, return-value]

    with pytest.raises(PlannerStrategyError):
        engine.create_plan(goal, context)


def test_invalid_candidate_plan_raises_plan_validation_error_unwrapped(
    goal: Goal, context: PlanningContext
) -> None:
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: _invalid_plan()))

    with pytest.raises(PlanValidationError):
        engine.create_plan(goal, context)


# -- No mutation ----------------------------------------------------------------------------


def test_create_plan_never_mutates_goal_or_context(goal: Goal, context: PlanningContext) -> None:
    goal_before = goal.model_copy(deep=True)
    context_before = context.model_copy(deep=True)
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: _valid_plan()))

    engine.create_plan(goal, context)

    assert goal == goal_before
    assert context.available_capabilities == context_before.available_capabilities
    assert context.correlation_id == context_before.correlation_id


def test_create_plan_never_touches_the_graph(goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: _valid_plan()))

    engine.create_plan(goal, context)

    graph = context.graph
    assert isinstance(graph, InMemoryGraphStore)
    assert graph.all_nodes() == ()


# -- Determinism -------------------------------------------------------------------------


def test_create_plan_is_deterministic_for_a_deterministic_strategy(
    goal: Goal, context: PlanningContext
) -> None:
    plan = _valid_plan()
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(lambda g, c: plan))

    first = engine.create_plan(goal, context)
    second = engine.create_plan(goal, context)

    assert first == second


# -- Structural minimalism ------------------------------------------------------------------


def test_planning_engine_exposes_only_the_expected_public_surface() -> None:
    public_attrs = {name for name in dir(PlanningEngine) if not name.startswith("_")}
    assert public_attrs == {"register_strategy", "create_plan"}


def test_planning_engine_constructor_takes_no_arguments() -> None:
    PlanningEngine()  # must not raise / must not require a strategy up front
