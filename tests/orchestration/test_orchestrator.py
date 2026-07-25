"""Tests for `GoalOrchestrator` (Sprint 7 Architecture Package §3, §5 —
ADR Candidates A and B), Phase 2.

Uses `_FunctionStrategy` (mirroring `tests/planning/test_engine.py`'s own
fake discipline exactly) with a real `PlanningEngine`, and a real
`ExecutionEngine` subclass whose `execute()` is overridden to record calls
— proves, not merely asserts, that `GoalOrchestrator` reaches `execute()`
only when planning genuinely succeeded.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from knowledge.graph import InMemoryGraphStore
from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import PlannerStrategy
from runtime.events.bus import EventBus

from execution.cancellation import CancellationToken
from execution.confirmation import DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.contract import ExecutionResult
from execution.engine import ExecutionEngine
from execution.lifecycle import ExecutionRunState
from execution.rollback import RollbackStrategy, UnsupportedRollbackStrategy

from orchestration.orchestrator import GoalOrchestrator


class _FunctionStrategy(PlannerStrategy):
    def __init__(self, func: Callable[[Goal, PlanningContext], Plan]) -> None:
        self._func = func

    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        return self._func(goal, context)


def _planning_engine(func: Callable[[Goal, PlanningContext], Plan]) -> PlanningEngine:
    engine = PlanningEngine()
    engine.register_strategy(_FunctionStrategy(func))
    return engine


class _SpyExecutionEngine(ExecutionEngine):
    """A real `ExecutionEngine` subclass whose `execute()` is overridden
    to record every call — proves `GoalOrchestrator` never reaches it when
    Planning fails (Architecture Review's own non-blocking recommendation 1).
    """

    def __init__(self) -> None:
        # Deliberately skips ExecutionEngine.__init__ (which requires a
        # real RetryPolicy) -- execute() is fully overridden below, so the
        # real base class's own construction-time state is never needed.
        self.calls: list[tuple[Plan, ExecutionContext]] = []

    def execute(self, plan: Plan, context: ExecutionContext) -> ExecutionResult:
        self.calls.append((plan, context))
        return ExecutionResult(
            execution_run_id="R-spy", plan_id=plan.plan_id, final_state=ExecutionRunState.COMPLETED
        )


class _FakeConnectorInvoker:
    def is_available(self, capability: str) -> bool:
        return True

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> Any:
        raise AssertionError("must not be called by these tests")


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


def _goal() -> Goal:
    return Goal(goal_id="G-1", intent="do the thing")


def _run_goal_kwargs(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "graph": InMemoryGraphStore(),
        "confirmation_provider": DenyAllConfirmationProvider(),
        "runtime_context": RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        "correlation_id": "corr-1",
        "available_capabilities": (
            CapabilityDescriptor(
                capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
            ),
        ),
    }
    defaults.update(overrides)
    return defaults


# -- Planning failure is captured, never propagated ----------------------------------------


def test_planner_strategy_error_is_captured_as_planning_failure() -> None:
    def broken_strategy(goal: Goal, context: PlanningContext) -> Plan:
        raise ValueError("no viable path found")

    orchestrator = GoalOrchestrator(
        _planning_engine(broken_strategy), _SpyExecutionEngine(), _FakeConnectorInvoker()
    )

    result = orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    assert result.plan is None
    assert result.execution_result is None
    assert result.planning_failure is not None
    assert result.planning_failure.error_type == "PlannerStrategyError"
    assert "no viable path found" in result.planning_failure.detail


def test_plan_validation_error_is_captured_as_planning_failure() -> None:
    orchestrator = GoalOrchestrator(
        _planning_engine(lambda g, c: _invalid_plan(g.goal_id)),
        _SpyExecutionEngine(),
        _FakeConnectorInvoker(),
    )

    result = orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    assert result.plan is None
    assert result.execution_result is None
    assert result.planning_failure is not None
    assert result.planning_failure.error_type == "PlanValidationError"


def test_execution_engine_is_never_called_when_planning_fails() -> None:
    def broken_strategy(goal: Goal, context: PlanningContext) -> Plan:
        raise ValueError("boom")

    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(broken_strategy), spy, _FakeConnectorInvoker())

    orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    assert spy.calls == []


# -- Successful planning proceeds to execution, result passes through unmodified -----------


def test_successful_plan_proceeds_to_execution_and_result_passes_through() -> None:
    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())

    result = orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    assert len(spy.calls) == 1
    called_plan, _ = spy.calls[0]
    assert called_plan is plan  # the exact object PlanningEngine returned -- no copy, no reconstruction
    assert result.plan is plan
    assert result.execution_result is not None
    assert result.execution_result.execution_run_id == "R-spy"
    assert result.planning_failure is None


# -- Construction-time vs. per-call collaborators (ADR Candidate A) ------------------------


def test_cancellation_token_defaults_to_a_fresh_token_when_omitted() -> None:
    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())

    orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    _, context = spy.calls[0]
    assert isinstance(context.cancellation_token, CancellationToken)


def test_a_supplied_cancellation_token_is_used_unchanged() -> None:
    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())
    token = CancellationToken()

    orchestrator.run_goal(_goal(), **_run_goal_kwargs(cancellation_token=token))

    _, context = spy.calls[0]
    assert context.cancellation_token is token


def test_rollback_strategy_defaults_to_unsupported_when_omitted() -> None:
    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())

    orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    _, context = spy.calls[0]
    assert isinstance(context.rollback_strategy, UnsupportedRollbackStrategy)


def test_a_supplied_rollback_strategy_passes_through_unchanged() -> None:
    class _CustomRollbackStrategy(RollbackStrategy):
        def rollback(self, record: Any, context: Any) -> Any:
            raise AssertionError("not exercised by this test")

    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())
    strategy = _CustomRollbackStrategy()

    orchestrator.run_goal(_goal(), **_run_goal_kwargs(rollback_strategy=strategy))

    _, context = spy.calls[0]
    assert context.rollback_strategy is strategy


def test_event_bus_defaults_to_none_when_omitted() -> None:
    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())

    orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    _, context = spy.calls[0]
    assert context.event_bus is None


def test_a_supplied_event_bus_passes_through_unchanged() -> None:
    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())
    bus = EventBus()

    orchestrator.run_goal(_goal(), **_run_goal_kwargs(event_bus=bus))

    _, context = spy.calls[0]
    assert context.event_bus is bus


def test_correlation_id_threads_into_both_planning_and_execution_contexts() -> None:
    seen_correlation_ids: list[str] = []

    def capturing_strategy(goal: Goal, context: PlanningContext) -> Plan:
        seen_correlation_ids.append(context.correlation_id)
        return _valid_plan(goal.goal_id)

    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(capturing_strategy), spy, _FakeConnectorInvoker())

    orchestrator.run_goal(_goal(), **_run_goal_kwargs(correlation_id="corr-shared"))

    assert seen_correlation_ids == ["corr-shared"]
    _, context = spy.calls[0]
    assert context.correlation_id == "corr-shared"


# -- Invariant 9: no mutation of Goal/Plan/ExecutionResult ---------------------------------


def test_goal_orchestrator_never_mutates_the_goal_it_is_given() -> None:
    plan = _valid_plan()
    goal = _goal()
    goal_before = goal.model_copy(deep=True)
    orchestrator = GoalOrchestrator(
        _planning_engine(lambda g, c: plan), _SpyExecutionEngine(), _FakeConnectorInvoker()
    )

    orchestrator.run_goal(goal, **_run_goal_kwargs())

    assert goal == goal_before


def test_goal_orchestrator_never_reconstructs_the_plan_it_receives() -> None:
    # Identity, not just equality -- proves no model_copy()/reconstruction
    # happened anywhere between PlanningEngine and the returned GoalRunResult.
    plan = _valid_plan()
    spy = _SpyExecutionEngine()
    orchestrator = GoalOrchestrator(_planning_engine(lambda g, c: plan), spy, _FakeConnectorInvoker())

    result = orchestrator.run_goal(_goal(), **_run_goal_kwargs())

    assert result.plan is plan
    called_plan, _ = spy.calls[0]
    assert called_plan is plan
