"""Execution Run / Step state machines.

Reuses `runtime.lifecycle.StateMachine[StateT]` — the exact generic
mechanism Sprint 1 built for `RuntimeState`/`ModuleState`/`PipelineRunState`
— a fourth time, with two new, Execution-owned enums (never a repurposing
of `PipelineRunState`, which stays scoped to `runtime.pipeline.engine`'s
own domain), per the Sprint 5 Architecture Package §12.

Two small, disclosed corrections to the approved architecture package's own
§12.1/§16.2 text, made here rather than requiring a further review round,
per the standing "fix only the minimum, explain why" instruction:

1. §12.1's bare transition notation read "RUNNING -> ROLLING_BACK", but its
   own parenthetical ("only if a rollback pass was opted into after
   FAILED") and §8 step 5 ("optional rollback pass — only if the run ended
   FAILED") both already establish that rollback follows a run that has
   *already* reached FAILED, never a direct branch from RUNNING. The
   transition table below is FAILED -> ROLLING_BACK, consistent with the
   rest of the same section, not the one inconsistent arrow.
2. §16.2's original failure-scenario row said a cancelled step "transitions
   to CANCELLED", but the later, explicitly reviewed and accepted
   correction to §15.5 (Execution Philosophy, Review Comment 3) unifies
   cancellation-before-start with the other two SKIPPED reasons (an unmet
   dependency, a denied confirmation) — "the run had already been
   cancelled before that step was reached" is named there as one of three
   reasons a step is SKIPPED, not a fourth, separate state.
   `StepExecutionState` therefore has no independent CANCELLED value; a
   cancelled-before-start step is SKIPPED, same as the other two reasons.
   `ExecutionRunState` keeps its own CANCELLED terminal state unchanged —
   this correction is scoped to the per-step enum only.
"""

from __future__ import annotations

import enum

from runtime.lifecycle import StateMachine


class ExecutionRunState(enum.Enum):
    """One `ExecutionRun`'s own lifecycle. See Sprint 5 Architecture
    Package §12.1 (as corrected above).
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class StepExecutionState(enum.Enum):
    """One `PlanStep`'s own execution lifecycle. See Sprint 5 Architecture
    Package §12.2/§14, and this module's own docstring for the
    cancellation-folds-into-SKIPPED correction.
    """

    PENDING = "pending"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


_EXECUTION_RUN_TRANSITIONS: dict[ExecutionRunState, frozenset[ExecutionRunState]] = {
    ExecutionRunState.PENDING: frozenset({ExecutionRunState.RUNNING, ExecutionRunState.CANCELLED}),
    ExecutionRunState.RUNNING: frozenset(
        {ExecutionRunState.COMPLETED, ExecutionRunState.FAILED, ExecutionRunState.CANCELLED}
    ),
    ExecutionRunState.COMPLETED: frozenset(),
    ExecutionRunState.FAILED: frozenset({ExecutionRunState.ROLLING_BACK}),
    ExecutionRunState.CANCELLED: frozenset(),
    ExecutionRunState.ROLLING_BACK: frozenset({ExecutionRunState.ROLLED_BACK}),
    ExecutionRunState.ROLLED_BACK: frozenset(),
}

_STEP_EXECUTION_TRANSITIONS: dict[StepExecutionState, frozenset[StepExecutionState]] = {
    StepExecutionState.PENDING: frozenset(
        {StepExecutionState.SKIPPED, StepExecutionState.AWAITING_CONFIRMATION, StepExecutionState.RUNNING}
    ),
    StepExecutionState.AWAITING_CONFIRMATION: frozenset(
        {StepExecutionState.RUNNING, StepExecutionState.SKIPPED}
    ),
    StepExecutionState.RUNNING: frozenset({StepExecutionState.SUCCEEDED, StepExecutionState.FAILED}),
    StepExecutionState.SUCCEEDED: frozenset(),
    StepExecutionState.FAILED: frozenset({StepExecutionState.ROLLED_BACK}),
    StepExecutionState.SKIPPED: frozenset(),
    StepExecutionState.ROLLED_BACK: frozenset(),
}


def new_execution_run_lifecycle() -> StateMachine[ExecutionRunState]:
    return StateMachine(state=ExecutionRunState.PENDING, _transitions=_EXECUTION_RUN_TRANSITIONS)


def new_step_execution_lifecycle() -> StateMachine[StepExecutionState]:
    return StateMachine(state=StepExecutionState.PENDING, _transitions=_STEP_EXECUTION_TRANSITIONS)
