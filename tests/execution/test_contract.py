"""Tests for the Execution Engine's Phase 2 data models
(Sprint 5 Architecture Package §10, §11.5).
"""

from __future__ import annotations

import dataclasses

import pytest
from integration.contract import ConnectorResponse
from pydantic import ValidationError

from execution.contract import ExecutionResult, ExecutionRun, RollbackOutcome, StepExecutionRecord
from execution.lifecycle import ExecutionRunState, StepExecutionState

# -- RollbackOutcome ---------------------------------------------------------------------


def test_rollback_outcome_constructs() -> None:
    outcome = RollbackOutcome(supported=False, detail="no compensating action declared")
    assert outcome.supported is False


def test_rollback_outcome_is_frozen() -> None:
    outcome = RollbackOutcome(supported=False)
    with pytest.raises(ValidationError):
        outcome.supported = True


def test_rollback_outcome_detail_defaults_to_empty_string() -> None:
    outcome = RollbackOutcome(supported=False)
    assert outcome.detail == ""


# -- StepExecutionRecord ------------------------------------------------------------------


def test_step_execution_record_constructs_with_only_required_fields() -> None:
    record = StepExecutionRecord(step_id="S-1", state=StepExecutionState.PENDING)
    assert record.attempts == 0
    assert record.response is None
    assert record.confirmation_granted is None
    assert record.rollback_outcome is None


def test_step_execution_record_constructs_with_every_field() -> None:
    response = ConnectorResponse(status="success", correlation_id="corr-1")
    record = StepExecutionRecord(
        step_id="S-1",
        state=StepExecutionState.SUCCEEDED,
        attempts=2,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        response=response,
        confirmation_granted=True,
        rollback_outcome=RollbackOutcome(supported=False),
    )
    assert record.attempts == 2
    assert record.response == response
    assert record.confirmation_granted is True


def test_step_execution_record_empty_step_id_raises() -> None:
    with pytest.raises(ValidationError):
        StepExecutionRecord(step_id="", state=StepExecutionState.PENDING)


def test_step_execution_record_negative_attempts_raises() -> None:
    with pytest.raises(ValidationError):
        StepExecutionRecord(step_id="S-1", state=StepExecutionState.PENDING, attempts=-1)


def test_step_execution_record_is_frozen() -> None:
    record = StepExecutionRecord(step_id="S-1", state=StepExecutionState.PENDING)
    with pytest.raises(ValidationError):
        record.attempts = 5


def test_step_execution_record_serialization_round_trips() -> None:
    record = StepExecutionRecord(
        step_id="S-1",
        state=StepExecutionState.FAILED,
        attempts=1,
        response=ConnectorResponse(status="failure", diagnostics="boom", correlation_id="corr-1"),
    )
    restored = StepExecutionRecord.model_validate_json(record.model_dump_json())
    assert restored == record


# -- ExecutionResult ----------------------------------------------------------------------


def test_execution_result_constructs_with_zero_steps() -> None:
    result = ExecutionResult(execution_run_id="R-1", plan_id="P-1", final_state=ExecutionRunState.COMPLETED)
    assert result.step_records == ()
    assert result.rollback_attempted is False


def test_execution_result_is_frozen() -> None:
    result = ExecutionResult(execution_run_id="R-1", plan_id="P-1", final_state=ExecutionRunState.COMPLETED)
    with pytest.raises(ValidationError):
        result.final_state = ExecutionRunState.FAILED


def test_execution_result_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        ExecutionResult(execution_run_id="R-1", final_state=ExecutionRunState.COMPLETED)  # type: ignore[call-arg]


def test_execution_result_serialization_round_trips() -> None:
    step = StepExecutionRecord(step_id="S-1", state=StepExecutionState.SUCCEEDED)
    result = ExecutionResult(
        execution_run_id="R-1", plan_id="P-1", final_state=ExecutionRunState.COMPLETED, step_records=(step,)
    )
    restored = ExecutionResult.model_validate_json(result.model_dump_json())
    assert restored == result


# -- ExecutionRun (mutable) ----------------------------------------------------------------


def test_execution_run_constructs() -> None:
    run = ExecutionRun(
        execution_run_id="R-1",
        plan_id="P-1",
        goal_id="G-1",
        state=ExecutionRunState.PENDING,
        started_at="2026-01-01T00:00:00Z",
    )
    assert run.state is ExecutionRunState.PENDING
    assert run.step_records == ()


def test_execution_run_is_a_plain_dataclass() -> None:
    assert dataclasses.is_dataclass(ExecutionRun)


def test_execution_run_is_mutable() -> None:
    run = ExecutionRun(
        execution_run_id="R-1",
        plan_id="P-1",
        goal_id="G-1",
        state=ExecutionRunState.PENDING,
        started_at="2026-01-01T00:00:00Z",
    )
    run.state = ExecutionRunState.RUNNING  # must not raise -- unlike Plan/PlanStep
    assert run.state is ExecutionRunState.RUNNING


def test_execution_run_step_records_can_be_reassigned() -> None:
    run = ExecutionRun(
        execution_run_id="R-1",
        plan_id="P-1",
        goal_id="G-1",
        state=ExecutionRunState.RUNNING,
        started_at="2026-01-01T00:00:00Z",
    )
    step = StepExecutionRecord(step_id="S-1", state=StepExecutionState.SUCCEEDED)
    run.step_records = (step,)
    assert run.step_records == (step,)


@pytest.mark.parametrize("missing_field", ["execution_run_id", "plan_id", "goal_id", "started_at"])
def test_execution_run_empty_required_string_raises(missing_field: str) -> None:
    kwargs: dict[str, object] = {
        "execution_run_id": "R-1",
        "plan_id": "P-1",
        "goal_id": "G-1",
        "state": ExecutionRunState.PENDING,
        "started_at": "2026-01-01T00:00:00Z",
    }
    kwargs[missing_field] = ""
    with pytest.raises(ValueError, match="must not be empty"):
        ExecutionRun(**kwargs)  # type: ignore[arg-type]
