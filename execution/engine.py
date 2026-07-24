"""`ExecutionEngine` — Sprint 5 Architecture Package §8, §9.2, §15, §18, §19.

Orchestrates exactly one `execute()` call end to end — mirrors
`planning.engine.PlanningEngine`'s role exactly: contains no logic of its
own beyond sequencing calls to components already built and independently
tested in Phases 1-4. `StepScheduler` orders; `ConfirmationGate` gates;
`RetryPolicy` retries; `ExecutionRun`/`StepExecutionRecord`/`ExecutionResult`
record. Phase 5 implemented the Execution Pipeline's steps 1-4 (§8: Intake,
Ordering, the per-step loop, Completion); Phase 6 (this phase) adds the two
pieces explicitly deferred then: the `cancellation_token` check at each
step boundary (§8 step 3b, §18) and the optional post-`FAILED` rollback
pass (§8 step 5, §19) — both additive to `execute()`, calling only into
already-built, already-tested Phase 3 contracts (`RollbackStrategy`,
`CancellationToken`), per the Sprint 5 Implementation Plan's own Phase 6
scope.

**Cancellation (§18).** Checked once per step, after the dependency check
and before that step is otherwise touched (§8's own a-then-b ordering) —
cooperative, never preemptive: a step already dispatched to `_run_step`
always runs to completion first. Once signaled, this step and every
remaining step are transitioned to `SKIPPED` in one pass, and the loop
stops; the run's own final state becomes `CANCELLED`, never `FAILED`, even
if some earlier step had already failed — §12.1's own transition table
has no path from `CANCELLED` to `FAILED` or back, so whichever is detected
here is final.

**Rollback (§19).** Only attempted if the run ended `FAILED` (never for
`CANCELLED` or `COMPLETED`) and the caller "opted in" (§15 step 7) — read
here as `context.rollback_strategy` being anything other than the default
`UnsupportedRollbackStrategy`. Every `FAILED` step's own `StepExecutionState`
machine (kept, per step, for exactly this reason — see `_dispatch`) is
reused to validate the `FAILED -> ROLLED_BACK` edge, rather than a fresh
one replaying an equivalent path; a step whose `RollbackOutcome.supported`
is `False` keeps its `FAILED` state and simply gains a non-`None`
`rollback_outcome` — never silently promoted to look like a success.

**Disclosed, not silently resolved — no event publication in this phase.**
Unchanged from Phase 5: `ExecutionContext` has no `event_bus` field (still
the same open, disclosed architecture clarification), so `ExecutionEngine`
continues to publish nothing.

**On `PlanNotExecutableError` and `ExecutionCancelledError`.** Unchanged
from Phase 5's own reasoning: neither is raised by `execute()`. A step
whose capability is unavailable is an ordinary `FAILED` record; a
cancelled run is a normal, returned `ExecutionResult` with
`final_state=CANCELLED`, mirroring `RetryExhaustedError`'s own
defined-but-unraised status.
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
from execution.rollback import UnsupportedRollbackStrategy
from execution.scheduler import StepScheduler

_StepLifecycle = StateMachine[StepExecutionState]


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
        step_lifecycles: dict[str, _StepLifecycle] = {}
        succeeded_step_ids: set[str] = set()
        cancelled = False

        for index, step in enumerate(ordered_steps):
            if not self._dependencies_met(step, succeeded_step_ids):
                record, lifecycle = self._skip(step)
            elif context.cancellation_token.is_cancellation_requested:
                cancelled = True
                for remaining_step in ordered_steps[index:]:
                    remaining_record, remaining_lifecycle = self._skip(remaining_step)
                    records.append(remaining_record)
                    step_lifecycles[remaining_step.step_id] = remaining_lifecycle
                run.step_records = tuple(records)
                break
            else:
                record, lifecycle = self._run_step(step, context, confirmation_gate, run)

            records.append(record)
            step_lifecycles[step.step_id] = lifecycle
            run.step_records = tuple(records)  # §20: a held ExecutionRun reference
            if record.state is StepExecutionState.SUCCEEDED:  # reflects progress so far, not just the end
                succeeded_step_ids.add(step.step_id)

        final_state = self._finalize_run(run, run_lifecycle, records, cancelled=cancelled)
        rollback_attempted = False

        if final_state is ExecutionRunState.FAILED and self._rollback_opted_in(context):
            records = self._run_rollback_pass(records, step_lifecycles, context)
            run.step_records = tuple(records)
            final_state = self._complete_rollback(run, run_lifecycle)
            rollback_attempted = True

        return ExecutionResult(
            execution_run_id=run.execution_run_id,
            plan_id=run.plan_id,
            final_state=final_state,
            step_records=run.step_records,
            rollback_attempted=rollback_attempted,
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

    def _skip(self, step: PlanStep) -> tuple[StepExecutionRecord, _StepLifecycle]:
        lifecycle = new_step_execution_lifecycle()
        lifecycle.transition(StepExecutionState.SKIPPED)
        return StepExecutionRecord(step_id=step.step_id, state=lifecycle.state), lifecycle

    def _run_step(
        self,
        step: PlanStep,
        context: ExecutionContext,
        confirmation_gate: ConfirmationGate,
        run: ExecutionRun,
    ) -> tuple[StepExecutionRecord, _StepLifecycle]:
        lifecycle = new_step_execution_lifecycle()
        confirmation_granted = confirmation_gate.evaluate(step, run)

        if confirmation_granted is False:
            lifecycle.transition(StepExecutionState.AWAITING_CONFIRMATION)
            lifecycle.transition(StepExecutionState.SKIPPED)
            record = StepExecutionRecord(
                step_id=step.step_id, state=lifecycle.state, confirmation_granted=False
            )
            return record, lifecycle

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

        record = StepExecutionRecord(
            step_id=step.step_id,
            state=lifecycle.state,
            attempts=attempts,
            started_at=started_at,
            finished_at=self._now(),
            response=response,
            confirmation_granted=confirmation_granted,
        )
        return record, lifecycle

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
        *,
        cancelled: bool,
    ) -> ExecutionRunState:
        if cancelled:
            target = ExecutionRunState.CANCELLED
        elif any(record.state is StepExecutionState.FAILED for record in records):
            target = ExecutionRunState.FAILED
        else:
            target = ExecutionRunState.COMPLETED
        lifecycle.transition(target)
        run.state = lifecycle.state
        run.finished_at = self._now()
        return run.state

    def _rollback_opted_in(self, context: ExecutionContext) -> bool:
        return not isinstance(context.rollback_strategy, UnsupportedRollbackStrategy)

    def _run_rollback_pass(
        self,
        records: list[StepExecutionRecord],
        step_lifecycles: dict[str, _StepLifecycle],
        context: ExecutionContext,
    ) -> list[StepExecutionRecord]:
        updated: list[StepExecutionRecord] = []
        for record in records:
            if record.state is not StepExecutionState.FAILED:
                updated.append(record)
                continue

            outcome = context.rollback_strategy.rollback(record, context)
            new_state: StepExecutionState = record.state
            if outcome.supported:
                lifecycle = step_lifecycles[record.step_id]
                lifecycle.transition(StepExecutionState.ROLLED_BACK)
                new_state = lifecycle.state

            updated.append(record.model_copy(update={"rollback_outcome": outcome, "state": new_state}))
        return updated

    def _complete_rollback(
        self, run: ExecutionRun, lifecycle: StateMachine[ExecutionRunState]
    ) -> ExecutionRunState:
        lifecycle.transition(ExecutionRunState.ROLLING_BACK)
        lifecycle.transition(ExecutionRunState.ROLLED_BACK)
        run.state = lifecycle.state
        run.finished_at = self._now()
        return run.state

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
