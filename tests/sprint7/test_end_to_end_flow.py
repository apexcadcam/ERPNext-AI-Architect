"""Sprint 7, Phase 4 — End-to-End Flow.

A real `Goal` → `container.resolve("orchestration.goal_runner").run_goal(...)`
→ a real `Plan` and a real `ExecutionResult`, against the real Filesystem
connector, through a fully booted `Runtime` — the first time this whole
chain has run through a single Container-resolved call rather than by
hand (`tests/sprint6/test_end_to_end_flow.py`'s own equivalent drives
`planning.engine`/`execution.engine` separately). A second case proves a
`Goal` whose desired capability is absent from `available_capabilities`
produces an ordinary, empty-`Plan` outcome — `RuleBasedPlannerStrategy`'s
own established "skip what's unavailable" behavior (Sprint 4) — never a
`PlannerStrategyError`/`PlanValidationError`, which requires a condition
not reachable through a real, fully-wired `PlanningModule`.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.graph import InMemoryGraphStore
from planning.contract import CapabilityDescriptor, Goal, PlanStep, RuntimeContextInfo
from planning.module import CAPABILITY_PLANNING_ENGINE
from runtime.boot import Runtime

from execution.confirmation import ConfirmationProvider
from execution.contract import ExecutionRun
from execution.lifecycle import ExecutionRunState, StepExecutionState
from execution.module import CAPABILITY_EXECUTION_ENGINE
from orchestration.module import CAPABILITY_GOAL_RUNNER
from tests.sprint7.conftest import root_filesystem_connector_at


class _AllowAllConfirmationProvider(ConfirmationProvider):
    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        return True


def _capability_descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
    )


def _runtime_context() -> RuntimeContextInfo:
    return RuntimeContextInfo(environment="Development", requested_by="test-suite")


def test_goal_run_through_orchestration_reaches_both_planning_and_execution(booted_runtime: Runtime) -> None:
    orchestrator = booted_runtime.container.resolve(CAPABILITY_GOAL_RUNNER)

    goal = Goal(goal_id="G-1", intent="read a file", desired_capabilities=("filesystem.read_text",))
    result = orchestrator.run_goal(
        goal,
        graph=InMemoryGraphStore(),
        confirmation_provider=_AllowAllConfirmationProvider(),
        runtime_context=_runtime_context(),
        correlation_id="corr-sprint7",
        available_capabilities=(_capability_descriptor(),),
    )

    assert result.planning_failure is None
    assert result.plan is not None
    assert [step.capability for step in result.plan.steps] == ["filesystem.read_text"]
    assert result.execution_result is not None
    assert len(result.execution_result.step_records) == 1


def test_a_goal_whose_capability_is_unavailable_produces_an_empty_plan_not_an_exception(
    booted_runtime: Runtime,
) -> None:
    orchestrator = booted_runtime.container.resolve(CAPABILITY_GOAL_RUNNER)

    goal = Goal(
        goal_id="G-2", intent="do something impossible", desired_capabilities=("erpnext.write_record",)
    )
    result = orchestrator.run_goal(
        goal,
        graph=InMemoryGraphStore(),
        confirmation_provider=_AllowAllConfirmationProvider(),
        runtime_context=_runtime_context(),
        correlation_id="corr-sprint7",
        available_capabilities=(),  # nothing available -- not a strategy/validation failure
    )

    assert result.planning_failure is None  # never raised -- an empty Plan is a normal outcome
    assert result.plan is not None
    assert result.plan.steps == ()
    assert result.execution_result is not None
    assert result.execution_result.final_state is ExecutionRunState.COMPLETED
    assert result.execution_result.step_records == ()


def test_goal_run_end_to_end_against_the_real_filesystem_connector(
    booted_runtime: Runtime, tmp_path: Path
) -> None:
    # A stronger, fully end-to-end proof against real I/O: since
    # RuleBasedPlannerStrategy itself never fills in step parameters, the
    # real connector call fails structurally on a missing "path" parameter
    # -- an ordinary FAILED step, not an exception, proving the whole
    # chain (real Runtime, real PluginRegistry-discovered connector, real
    # ExecutionEngine invocation) genuinely ran, not merely that Planning
    # produced the right shape.
    (tmp_path / "input.txt").write_text("hello", encoding="utf-8")
    orchestrator = booted_runtime.container.resolve(CAPABILITY_GOAL_RUNNER)
    registry = booted_runtime.container.resolve("integration.connector_registry")
    root_filesystem_connector_at(registry, tmp_path)

    goal = Goal(goal_id="G-3", intent="read a file", desired_capabilities=("filesystem.read_text",))
    result = orchestrator.run_goal(
        goal,
        graph=InMemoryGraphStore(),
        confirmation_provider=_AllowAllConfirmationProvider(),
        runtime_context=_runtime_context(),
        correlation_id="corr-sprint7",
        available_capabilities=(_capability_descriptor(),),
    )

    assert result.plan is not None
    assert result.execution_result is not None
    record = result.execution_result.step_records[0]
    assert record.state is StepExecutionState.FAILED  # no "path" parameter supplied
    assert record.response is not None
    assert result.execution_result.final_state is ExecutionRunState.FAILED


def test_planning_engine_and_execution_engine_used_by_orchestration_are_the_container_resolved_ones(
    booted_runtime: Runtime,
) -> None:
    orchestrator = booted_runtime.container.resolve(CAPABILITY_GOAL_RUNNER)
    planning_engine = booted_runtime.container.resolve(CAPABILITY_PLANNING_ENGINE)
    execution_engine = booted_runtime.container.resolve(CAPABILITY_EXECUTION_ENGINE)

    assert orchestrator._planning_engine is planning_engine
    assert orchestrator._execution_engine is execution_engine
