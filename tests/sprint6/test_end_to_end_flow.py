"""Sprint 6, Phase 7 — End-to-End Flow.

A real `Goal` → `container.resolve("planning.engine").create_plan(...)` →
`container.resolve("execution.engine").execute(plan, context)` → a real
`ExecutionResult`, against the real Filesystem connector, through a fully
booted `Runtime` — the first time this whole chain has ever run through
Container resolution rather than by-hand construction
(`tests/sprint5/test_end_to_end_flow.py`'s own equivalent constructs every
piece directly). `ExecutionContext` assembly remains this test's own
responsibility, not the Runtime's — no automatic assembly exists yet
(Sprint 6 Architecture Package §3's own Non-Goal, the future Agent
Orchestration Loop).
"""

from __future__ import annotations

from pathlib import Path

from knowledge.graph import InMemoryGraphStore
from planning.context import PlanningContext
from planning.contract import CapabilityDescriptor, Goal, PlanStep, RuntimeContextInfo
from planning.module import CAPABILITY_PLANNING_ENGINE
from runtime.boot import Runtime

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider
from execution.connector_invoker import RegistryConnectorInvoker
from execution.context import ExecutionContext
from execution.contract import ExecutionRun
from execution.lifecycle import ExecutionRunState, StepExecutionState
from execution.module import CAPABILITY_EXECUTION_ENGINE
from tests.sprint6.conftest import root_filesystem_connector_at


class _AllowAllConfirmationProvider(ConfirmationProvider):
    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        return True


def test_goal_to_plan_to_execution_through_container_resolution(
    booted_runtime: Runtime, tmp_path: Path
) -> None:
    (tmp_path / "input.txt").write_text("hello", encoding="utf-8")

    planning_engine = booted_runtime.container.resolve(CAPABILITY_PLANNING_ENGINE)
    execution_engine = booted_runtime.container.resolve(CAPABILITY_EXECUTION_ENGINE)
    registry = booted_runtime.container.resolve("integration.connector_registry")
    root_filesystem_connector_at(registry, tmp_path)

    goal = Goal(
        goal_id="G-1",
        intent="read then write a file",
        desired_capabilities=("filesystem.read_text", "filesystem.write_text"),
    )
    planning_context = PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(
            CapabilityDescriptor(
                capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
            ),
            CapabilityDescriptor(
                capability="filesystem.write_text", kind="write", idempotent=False, requires_confirmation=True
            ),
        ),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )

    plan = planning_engine.create_plan(goal, planning_context)
    assert [step.capability for step in plan.steps] == ["filesystem.read_text", "filesystem.write_text"]

    # RuleBasedPlannerStrategy emits parameter-free steps -- a real caller
    # fills them in before execution, exactly as tests/sprint5/
    # test_end_to_end_flow.py's own equivalent already does.
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

    execution_context = ExecutionContext(
        connector_invoker=RegistryConnectorInvoker(registry),
        confirmation_provider=_AllowAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )

    result = execution_engine.execute(plan, execution_context)

    assert result.final_state is ExecutionRunState.COMPLETED
    assert [r.state for r in result.step_records] == [
        StepExecutionState.SUCCEEDED,
        StepExecutionState.SUCCEEDED,
    ]
    assert (tmp_path / "input.txt").read_text(encoding="utf-8") == "hello again"


def test_goal_with_no_available_capabilities_produces_an_empty_plan_that_executes_cleanly(
    booted_runtime: Runtime,
) -> None:
    planning_engine = booted_runtime.container.resolve(CAPABILITY_PLANNING_ENGINE)
    execution_engine = booted_runtime.container.resolve(CAPABILITY_EXECUTION_ENGINE)

    goal = Goal(goal_id="G-2", intent="nothing to do here")
    planning_context = PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )
    plan = planning_engine.create_plan(goal, planning_context)
    assert plan.steps == ()

    registry = booted_runtime.container.resolve("integration.connector_registry")
    execution_context = ExecutionContext(
        connector_invoker=RegistryConnectorInvoker(registry),
        confirmation_provider=_AllowAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )

    result = execution_engine.execute(plan, execution_context)

    assert result.final_state is ExecutionRunState.COMPLETED
    assert result.step_records == ()
