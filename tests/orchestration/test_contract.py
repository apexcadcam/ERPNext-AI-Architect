"""Tests for `PlanningFailure`/`GoalRunResult` (Sprint 7 Architecture
Package §3), Phase 1.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from execution.contract import ExecutionResult
from execution.lifecycle import ExecutionRunState
from planning.contract import Plan
from pydantic import ValidationError

from orchestration.contract import GoalRunResult, PlanningFailure

ORCHESTRATION_DIR = Path(__file__).resolve().parents[2] / "orchestration"


def _plan() -> Plan:
    return Plan(plan_id="P-1", goal_id="G-1", created_at="2026-01-01T00:00:00Z", strategy_name="stub")


def _execution_result() -> ExecutionResult:
    return ExecutionResult(execution_run_id="R-1", plan_id="P-1", final_state=ExecutionRunState.COMPLETED)


# -- PlanningFailure ------------------------------------------------------------------------


def test_planning_failure_constructs_with_both_fields() -> None:
    failure = PlanningFailure(error_type="PlannerStrategyError", detail="no strategy configured")
    assert failure.error_type == "PlannerStrategyError"
    assert failure.detail == "no strategy configured"


def test_planning_failure_is_frozen() -> None:
    failure = PlanningFailure(error_type="PlannerStrategyError", detail="x")
    with pytest.raises(ValidationError):
        failure.detail = "y"


def test_planning_failure_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PlanningFailure(error_type="PlannerStrategyError", detail="x", extra="y")  # type: ignore[call-arg]


def test_planning_failure_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        PlanningFailure(error_type="", detail="x")
    with pytest.raises(ValidationError):
        PlanningFailure(error_type="PlannerStrategyError", detail="")


# -- GoalRunResult --------------------------------------------------------------------------


def test_goal_run_result_constructs_the_planning_failed_shape() -> None:
    result = GoalRunResult(
        goal_id="G-1",
        planning_failure=PlanningFailure(error_type="PlanValidationError", detail="boom"),
    )
    assert result.plan is None
    assert result.execution_result is None
    assert result.planning_failure is not None
    assert result.planning_failure.error_type == "PlanValidationError"


def test_goal_run_result_constructs_the_executed_shape() -> None:
    result = GoalRunResult(goal_id="G-1", plan=_plan(), execution_result=_execution_result())
    assert result.plan is not None
    assert result.execution_result is not None
    assert result.planning_failure is None


def test_goal_run_result_defaults_are_all_none() -> None:
    result = GoalRunResult(goal_id="G-1")
    assert result.plan is None
    assert result.execution_result is None
    assert result.planning_failure is None


def test_goal_run_result_is_frozen() -> None:
    result = GoalRunResult(goal_id="G-1")
    with pytest.raises(ValidationError):
        result.goal_id = "G-2"


def test_goal_run_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        GoalRunResult(goal_id="G-1", extra="y")  # type: ignore[call-arg]


def test_goal_run_result_rejects_empty_goal_id() -> None:
    with pytest.raises(ValidationError):
        GoalRunResult(goal_id="")


# -- Import boundary (light check; the full AST-plus-subprocess methodology is Phase 2's own scope) --


def test_contract_module_imports_only_planning_and_execution_contract() -> None:
    tree = ast.parse((ORCHESTRATION_DIR / "contract.py").read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module)
    assert modules <= {"__future__", "pydantic", "execution.contract", "planning.contract"}
