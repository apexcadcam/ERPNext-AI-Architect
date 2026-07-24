"""Sprint 5, Phase 7 — End-to-End Execution Flow.

`Goal` -> `PlanningEngine` -> `RuleBasedPlannerStrategy` -> `Plan` ->
`ExecutionEngine` -> a real `ConnectorLifecycle.invoke()` -> `ExecutionResult`,
using the real, already-frozen Sprint 5 Phase 1-6 code as-is, plus Sprint
4's own `PlanningEngine` — the one test in the whole project proving
Planning's output is genuinely consumable by Execution's input, not merely
structurally compatible on paper.
"""

from __future__ import annotations

from pathlib import Path

from integration.registry import ConnectorRegistry
from planning.contract import Goal, PlanStep, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import RuleBasedPlannerStrategy

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider
from execution.connector_invoker import RegistryConnectorInvoker
from execution.context import ExecutionContext
from execution.contract import ExecutionRun
from execution.engine import ExecutionEngine
from execution.lifecycle import ExecutionRunState, StepExecutionState
from execution.retry import RetryPolicy


class _AllowAllConfirmationProvider(ConfirmationProvider):
    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        return True


def _execution_context(registry: ConnectorRegistry) -> ExecutionContext:
    return ExecutionContext(
        connector_invoker=RegistryConnectorInvoker(registry),
        confirmation_provider=_AllowAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )


def test_end_to_end_read_then_write_plan_executes_successfully(
    tmp_path: Path, goal: Goal, planning_context: PlanningContext, real_registry: ConnectorRegistry
) -> None:
    (tmp_path / "input.txt").write_text("hello", encoding="utf-8")

    planner = PlanningEngine()
    planner.register_strategy(RuleBasedPlannerStrategy())
    plan = planner.create_plan(goal, planning_context)
    assert [step.capability for step in plan.steps] == ["filesystem.read_text", "filesystem.write_text"]

    # RuleBasedPlannerStrategy emits parameter-free steps (Sprint 4 scope
    # never included parameter-filling) -- a real caller supplies them
    # before execution, exactly as this fixture does.
    plan = plan.model_copy(
        update={
            "steps": (
                plan.steps[0].model_copy(update={"parameters": {"path": "input.txt"}}),
                plan.steps[1].model_copy(
                    update={"parameters": {"path": "input.txt", "content": "hello again"}}
                ),
            )
        }
    )

    engine = ExecutionEngine(RetryPolicy(real_registry))
    result = engine.execute(plan, _execution_context(real_registry))

    assert result.final_state is ExecutionRunState.COMPLETED
    assert [r.state for r in result.step_records] == [
        StepExecutionState.SUCCEEDED,
        StepExecutionState.SUCCEEDED,
    ]
    assert (tmp_path / "input.txt").read_text(encoding="utf-8") == "hello again"


def test_end_to_end_empty_plan_completes_with_nothing_to_do(
    planning_context: PlanningContext, real_registry: ConnectorRegistry
) -> None:
    empty_goal = Goal(goal_id="G-2", intent="nothing to do here")
    planner = PlanningEngine()
    planner.register_strategy(RuleBasedPlannerStrategy())
    plan = planner.create_plan(empty_goal, planning_context)
    assert plan.steps == ()

    engine = ExecutionEngine(RetryPolicy(real_registry))
    result = engine.execute(plan, _execution_context(real_registry))

    assert result.final_state is ExecutionRunState.COMPLETED
    assert result.step_records == ()


def test_end_to_end_a_step_whose_capability_vanished_since_planning_fails_gracefully(
    goal: Goal, planning_context: PlanningContext, real_registry: ConnectorRegistry
) -> None:
    # Planning saw filesystem.write_text as available; simulate the live
    # Integration layer's state having drifted since then by never
    # registering the connector this Plan's second step needs.
    planner = PlanningEngine()
    planner.register_strategy(RuleBasedPlannerStrategy())
    plan = planner.create_plan(goal, planning_context)

    drifted_registry = ConnectorRegistry()  # zero connectors registered
    engine = ExecutionEngine(RetryPolicy(drifted_registry))
    result = engine.execute(plan, _execution_context(drifted_registry))

    assert result.final_state is ExecutionRunState.FAILED
    assert all(r.state is StepExecutionState.FAILED for r in result.step_records)
