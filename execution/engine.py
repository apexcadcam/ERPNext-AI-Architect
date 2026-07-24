"""`ExecutionEngine` — Sprint 5 Architecture Package §8, §9.2, §15.

Orchestrates exactly one `execute()` call end to end — mirrors
`planning.engine.PlanningEngine`'s role exactly: contains no logic of its
own beyond sequencing calls to components already built and independently
tested in Phases 1-4. `StepScheduler` orders; `ConfirmationGate` gates;
`RetryPolicy` retries; `ExecutionRun`/`StepExecutionRecord`/`ExecutionResult`
record. This phase implements the Execution Pipeline's steps 1-4 (§8:
Intake, Ordering, the per-step loop, Completion) exactly; the optional
post-`FAILED` rollback pass (§8 step 5, §19) and `cancellation_token`
checks are Phase 6 scope per the Sprint 5 Implementation Plan — a run that
fails stays `FAILED`, and cancellation is not yet checked mid-loop.

**Disclosed, not silently resolved — no event publication in this phase.**
`execution/events.py`'s own docstring and the Sprint 5 Implementation
Plan's Phase 5 objectives both name event publication as in scope, via an
`ExecutionContext.event_bus`. `ExecutionContext` (Phase 3) has no such
field — that is the same still-open, disclosed architecture clarification
`execution/context.py` and `execution/connector_invoker.py` already named,
orthogonal to the `ConnectorRegistry`/`RetryPolicy` construction gap
`ADR-0014` just resolved. Adding an `event_bus` field anywhere is not this
phase's call to make unilaterally, so `ExecutionEngine` publishes nothing
this phase.

**On `PlanNotExecutableError` and `ExecutionCancelledError`.** Neither is
raised by `execute()` in this phase. `PlanNotExecutableError` is reserved
for a genuine internal precondition violation — e.g. `StepScheduler`
failing to order every one of `plan.steps` despite Sprint 4's
`validate_plan` already having passed, which should never happen given a
valid `Plan` (`execution/errors.py`'s own docstring: "never raised for
runtime capability availability... that is always a per-step outcome").
A step whose capability is unavailable at execution time is recorded as an
ordinary `FAILED` `StepExecutionRecord`, exactly like any other connector
failure — not a special, thrown case; this corrects this package's own
§16.2 row 1, whose literal wording predates the Review Comment 3 follow-up
already reflected in `execution/errors.py`'s live docstring. `Execution
CancelledError` is never raised either: a run cancelled mid-loop is a
normal, disclosed terminal outcome (`ExecutionRunState.CANCELLED`),
returned in the `ExecutionResult` like `FAILED` — mirroring how
`RetryExhaustedError` is already defined but never raised by `RetryPolicy`
(Phase 4). Both remain in the hierarchy, unused by this phase's own normal
flow, exactly as their own docstrings already state. Since cancellation
checks are Phase 6 scope, no run produced by this phase ever reaches
`CANCELLED` yet either — the enum value and this reasoning are recorded
now so Phase 6 only has to wire the check in, not decide the semantics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from integration.contract import ConnectorResponse
from planning.contract import Plan, PlanStep
from runtime.lifecycle import StateMachine

from execution.confirmation_gate import ConfirmationGate
from execution.context import ExecutionContext
from execution.contract import ExecutionResult, ExecutionRun, StepExecutionRecord
from execution.errors import PlanNotExecutableError
from execution.lifecycle import (
    ExecutionRunState,
    StepExecutionState,
    new_execution_run_lifecycle,
    new_step_execution_lifecycle,
)
from execution.retry import RetryPolicy
from execution.scheduler import StepScheduler


class ExecutionEngine:
    """Orchestrates exactly one `execute()` call end to end. See
    `ADR-0014` for why `RetryPolicy` is a construction-time collaborator
    rather than an `ExecutionContext` field.
    """

    def __init__(self, retry_policy: RetryPolicy) -> None:
        self._retry_policy = retry_policy
        self._scheduler = StepScheduler()

    def execute(self, plan: Plan, context: ExecutionContext) -> ExecutionResult:
        """Runs `plan` to completion against `context`. Never raises for
        an individual step's outcome — every failure, skip, or success is
        recorded in the returned `ExecutionResult` instead (§9.2).
        """

        run, run_lifecycle = self._start_run(plan)
        ordered_steps = self._order_steps(plan)
        confirmation_gate = ConfirmationGate(context.confirmation_provider)

        records: list[StepExecutionRecord] = []
        succeeded_step_ids: set[str] = set()
        for step in ordered_steps:
            if self._dependencies_met(step, succeeded_step_ids):
                record = self._run_step(step, context, confirmation_gate, run)
            else:
                record = self._skip(step)
            records.append(record)
            run.step_records = tuple(records)  # §20: a held ExecutionRun reference
            if record.state is StepExecutionState.SUCCEEDED:  # reflects progress so far, not just the end
                succeeded_step_ids.add(step.step_id)

        final_state = self._finalize_run(run, run_lifecycle, records)
        return ExecutionResult(
            execution_run_id=run.execution_run_id,
            plan_id=run.plan_id,
            final_state=final_state,
            step_records=run.step_records,
            rollback_attempted=False,
        )

    def _start_run(self, plan: Plan) -> tuple[ExecutionRun, StateMachine[ExecutionRunState]]:
        lifecycle = new_execution_run_lifecycle()
        lifecycle.transition(ExecutionRunState.RUNNING)
        run = ExecutionRun(
            execution_run_id=str(uuid.uuid4()),
            plan_id=plan.plan_id,
            goal_id=plan.goal_id,
            state=lifecycle.state,
            started_at=self._now(),
        )
        return run, lifecycle

    def _order_steps(self, plan: Plan) -> tuple[PlanStep, ...]:
        ordered = self._scheduler.order(plan)
        if len(ordered) != len(plan.steps):
            raise PlanNotExecutableError(
                "StepScheduler could not order every step in plan.steps — a "
                "dependency cycle or reference to an unknown step_id was not "
                "caught by prior planning-time validation"
            )
        return ordered

    def _dependencies_met(self, step: PlanStep, succeeded_step_ids: set[str]) -> bool:
        return all(dependency_id in succeeded_step_ids for dependency_id in step.depends_on)

    def _skip(self, step: PlanStep) -> StepExecutionRecord:
        lifecycle = new_step_execution_lifecycle()
        lifecycle.transition(StepExecutionState.SKIPPED)
        return StepExecutionRecord(step_id=step.step_id, state=lifecycle.state)

    def _run_step(
        self,
        step: PlanStep,
        context: ExecutionContext,
        confirmation_gate: ConfirmationGate,
        run: ExecutionRun,
    ) -> StepExecutionRecord:
        lifecycle = new_step_execution_lifecycle()
        confirmation_granted = confirmation_gate.evaluate(step, run)

        if confirmation_granted is False:
            lifecycle.transition(StepExecutionState.AWAITING_CONFIRMATION)
            lifecycle.transition(StepExecutionState.SKIPPED)
            return StepExecutionRecord(
                step_id=step.step_id, state=lifecycle.state, confirmation_granted=False
            )

        if confirmation_granted is True:
            lifecycle.transition(StepExecutionState.AWAITING_CONFIRMATION)
        lifecycle.transition(StepExecutionState.RUNNING)

        started_at = self._now()
        response, attempts = self._invoke(step, context)
        lifecycle.transition(
            StepExecutionState.SUCCEEDED
            if response.status in ("success", "partial")
            else StepExecutionState.FAILED
        )

        return StepExecutionRecord(
            step_id=step.step_id,
            state=lifecycle.state,
            attempts=attempts,
            started_at=started_at,
            finished_at=self._now(),
            response=response,
            confirmation_granted=confirmation_granted,
        )

    def _invoke(self, step: PlanStep, context: ExecutionContext) -> tuple[ConnectorResponse, int]:
        if not context.connector_invoker.is_available(step.capability):
            return (
                ConnectorResponse(
                    status="failure",
                    diagnostics=f"capability '{step.capability}' is not available",
                    correlation_id=context.correlation_id,
                ),
                0,
            )
        return self._retry_policy.invoke_with_retries(
            context.connector_invoker,
            step.capability,
            step.parameters,
            correlation_id=context.correlation_id,
            requested_by=context.runtime_context.requested_by,
        )

    def _finalize_run(
        self,
        run: ExecutionRun,
        lifecycle: StateMachine[ExecutionRunState],
        records: list[StepExecutionRecord],
    ) -> ExecutionRunState:
        if any(record.state is StepExecutionState.FAILED for record in records):
            target = ExecutionRunState.FAILED
        else:
            target = ExecutionRunState.COMPLETED
        lifecycle.transition(target)
        run.state = lifecycle.state
        run.finished_at = self._now()
        return run.state

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
