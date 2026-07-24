"""Tests for the Execution Run/Step state machines (Sprint 5 Architecture
Package §12, as corrected by `execution/lifecycle.py`'s own disclosed
corrections to §12.1/§16.2).
"""

from __future__ import annotations

import pytest
from runtime.lifecycle import InvalidTransitionError

from execution.lifecycle import (
    ExecutionRunState,
    StepExecutionState,
    new_execution_run_lifecycle,
    new_step_execution_lifecycle,
)

# -- ExecutionRunState -----------------------------------------------------------------


def test_execution_run_lifecycle_starts_pending() -> None:
    lifecycle = new_execution_run_lifecycle()
    assert lifecycle.state is ExecutionRunState.PENDING


def test_execution_run_pending_to_running_to_completed() -> None:
    lifecycle = new_execution_run_lifecycle()
    lifecycle.transition(ExecutionRunState.RUNNING)
    lifecycle.transition(ExecutionRunState.COMPLETED)
    assert lifecycle.state is ExecutionRunState.COMPLETED


def test_execution_run_pending_to_cancelled_directly() -> None:
    lifecycle = new_execution_run_lifecycle()
    lifecycle.transition(ExecutionRunState.CANCELLED)
    assert lifecycle.state is ExecutionRunState.CANCELLED


def test_execution_run_running_to_failed_to_rolling_back_to_rolled_back() -> None:
    # The corrected path: rollback follows FAILED, never a direct branch
    # from RUNNING (see this module's own docstring in execution/lifecycle.py).
    lifecycle = new_execution_run_lifecycle()
    lifecycle.transition(ExecutionRunState.RUNNING)
    lifecycle.transition(ExecutionRunState.FAILED)
    lifecycle.transition(ExecutionRunState.ROLLING_BACK)
    lifecycle.transition(ExecutionRunState.ROLLED_BACK)
    assert lifecycle.state is ExecutionRunState.ROLLED_BACK


def test_execution_run_cannot_go_directly_from_running_to_rolling_back() -> None:
    lifecycle = new_execution_run_lifecycle()
    lifecycle.transition(ExecutionRunState.RUNNING)
    with pytest.raises(InvalidTransitionError):
        lifecycle.transition(ExecutionRunState.ROLLING_BACK)


def test_execution_run_completed_is_terminal() -> None:
    lifecycle = new_execution_run_lifecycle()
    lifecycle.transition(ExecutionRunState.RUNNING)
    lifecycle.transition(ExecutionRunState.COMPLETED)
    with pytest.raises(InvalidTransitionError):
        lifecycle.transition(ExecutionRunState.RUNNING)


def test_execution_run_cancelled_is_terminal() -> None:
    lifecycle = new_execution_run_lifecycle()
    lifecycle.transition(ExecutionRunState.CANCELLED)
    with pytest.raises(InvalidTransitionError):
        lifecycle.transition(ExecutionRunState.RUNNING)


# -- StepExecutionState ------------------------------------------------------------------


def test_step_execution_lifecycle_starts_pending() -> None:
    lifecycle = new_step_execution_lifecycle()
    assert lifecycle.state is StepExecutionState.PENDING


def test_step_pending_to_skipped_directly() -> None:
    # Covers all three §15.5 skip reasons (unmet dependency, denied
    # confirmation, run already cancelled) -- all collapse to this one
    # transition, per execution/lifecycle.py's own disclosed correction.
    lifecycle = new_step_execution_lifecycle()
    lifecycle.transition(StepExecutionState.SKIPPED)
    assert lifecycle.state is StepExecutionState.SKIPPED


def test_step_pending_to_awaiting_confirmation_to_running_to_succeeded() -> None:
    lifecycle = new_step_execution_lifecycle()
    lifecycle.transition(StepExecutionState.AWAITING_CONFIRMATION)
    lifecycle.transition(StepExecutionState.RUNNING)
    lifecycle.transition(StepExecutionState.SUCCEEDED)
    assert lifecycle.state is StepExecutionState.SUCCEEDED


def test_step_awaiting_confirmation_can_be_denied_to_skipped() -> None:
    lifecycle = new_step_execution_lifecycle()
    lifecycle.transition(StepExecutionState.AWAITING_CONFIRMATION)
    lifecycle.transition(StepExecutionState.SKIPPED)
    assert lifecycle.state is StepExecutionState.SKIPPED


def test_step_pending_directly_to_running_when_no_confirmation_needed() -> None:
    lifecycle = new_step_execution_lifecycle()
    lifecycle.transition(StepExecutionState.RUNNING)
    assert lifecycle.state is StepExecutionState.RUNNING


def test_step_running_to_failed_to_rolled_back() -> None:
    lifecycle = new_step_execution_lifecycle()
    lifecycle.transition(StepExecutionState.RUNNING)
    lifecycle.transition(StepExecutionState.FAILED)
    lifecycle.transition(StepExecutionState.ROLLED_BACK)
    assert lifecycle.state is StepExecutionState.ROLLED_BACK


def test_step_succeeded_is_terminal() -> None:
    lifecycle = new_step_execution_lifecycle()
    lifecycle.transition(StepExecutionState.RUNNING)
    lifecycle.transition(StepExecutionState.SUCCEEDED)
    with pytest.raises(InvalidTransitionError):
        lifecycle.transition(StepExecutionState.RUNNING)


def test_step_skipped_is_terminal() -> None:
    lifecycle = new_step_execution_lifecycle()
    lifecycle.transition(StepExecutionState.SKIPPED)
    with pytest.raises(InvalidTransitionError):
        lifecycle.transition(StepExecutionState.RUNNING)


def test_step_execution_state_has_no_independent_cancelled_value() -> None:
    # Locks in this module's own disclosed correction: cancellation-before
    # -start is a SKIPPED reason, not a fourth, separate state.
    assert not hasattr(StepExecutionState, "CANCELLED")


def test_execution_run_state_keeps_its_own_cancelled_value() -> None:
    # The correction above is scoped to the per-step enum only.
    assert hasattr(ExecutionRunState, "CANCELLED")
