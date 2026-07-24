"""Sprint 5, Phase 7 — Execution Philosophy & Ownership (§15.5, §11.5),
verified at the full-system level rather than per-component.

Three claims: (1) best-effort — one step's failure never aborts an
unrelated, independent branch; (2) ownership — `ExecutionRun` is mutated
only from inside `execution/engine.py`, never from any other file in the
project, verified with a source-wide grep-by-AST rather than a single
example; (3) `PlanNotExecutableError` is never raised for an ordinary
capability-availability failure, only for the genuine internal
precondition it is reserved for.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry
from planning.contract import Plan, PlanStep, RuntimeContextInfo

from execution.cancellation import CancellationToken
from execution.confirmation import DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.engine import ExecutionEngine
from execution.errors import PlanNotExecutableError
from execution.lifecycle import ExecutionRunState, StepExecutionState
from execution.retry import RetryPolicy

REPO_ROOT = Path(__file__).resolve().parents[2]


class _PerCapabilityConnectorInvoker:
    def __init__(self, responses: dict[str, ConnectorResponse]) -> None:
        self._responses = responses

    def is_available(self, capability: str) -> bool:
        return capability in self._responses

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        return self._responses[capability]


def _context(invoker: Any) -> ExecutionContext:
    return ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )


# -- 1. Best-effort: an independent branch's failure never aborts another ----------------


def test_two_independent_multi_step_branches_one_failing_the_other_still_completes() -> None:
    # Branch A: A1 -> A2 (A1 fails, so A2 is skipped for an unmet dependency).
    # Branch B: B1 -> B2 (both succeed, entirely unaffected by branch A).
    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(
            PlanStep(step_id="A1", capability="a1.op", requires_confirmation=False),
            PlanStep(step_id="B1", capability="b1.op", requires_confirmation=False),
            PlanStep(step_id="A2", capability="a2.op", depends_on=("A1",), requires_confirmation=False),
            PlanStep(step_id="B2", capability="b2.op", depends_on=("B1",), requires_confirmation=False),
        ),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )
    invoker = _PerCapabilityConnectorInvoker(
        {
            "a1.op": ConnectorResponse(status="failure", diagnostics="boom", correlation_id="corr-1"),
            "b1.op": ConnectorResponse(status="success", correlation_id="corr-1"),
            "b2.op": ConnectorResponse(status="success", correlation_id="corr-1"),
        }
    )
    engine = ExecutionEngine(RetryPolicy(ConnectorRegistry()))

    result = engine.execute(plan, _context(invoker))

    records = {r.step_id: r.state for r in result.step_records}
    assert records["A1"] is StepExecutionState.FAILED
    assert records["A2"] is StepExecutionState.SKIPPED
    assert records["B1"] is StepExecutionState.SUCCEEDED
    assert records["B2"] is StepExecutionState.SUCCEEDED  # entirely unaffected by branch A
    assert result.final_state is ExecutionRunState.FAILED  # the run is still honestly FAILED overall


# -- 2. Ownership: only execution/engine.py ever assigns to ExecutionRun's own fields -----


def _project_python_files() -> list[Path]:
    return [
        py_file
        for py_file in REPO_ROOT.rglob("*.py")
        if "__pycache__" not in py_file.parts and ".venv" not in py_file.parts
    ]


def _assigns_to_run_field(py_file: Path) -> bool:
    """True if `py_file` contains an assignment of the shape `run.state =
    ...` (attribute `state` on a variable literally named `run`, the
    consistent name used everywhere an `ExecutionRun` is held throughout
    this codebase — `state` alone is deliberately *not* checked regardless
    of base, since `runtime.lifecycle.StateMachine.transition()` legitimately
    does `self.state = target` for an entirely unrelated class), or
    `<something>.step_records = ...` / `<something>.finished_at = ...` —
    both distinctive enough to `ExecutionRun`/`StepExecutionRecord` that no
    base-variable restriction is needed. A real AST check, not a substring
    search — immune to a docstring merely mentioning one of these names.
    """

    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Attribute):
                continue
            if target.attr in {"step_records", "finished_at"}:
                return True
            if target.attr == "state" and isinstance(target.value, ast.Name) and target.value.id == "run":
                return True
    return False


def _references_name(py_file: Path, name: str) -> bool:
    """True if `py_file` contains a real `ast.Name`/`ast.alias` reference
    to the exact identifier `name` — immune both to docstring mentions and
    to substring collisions with a differently-named identifier (e.g.
    `ExecutionRunState` must never count as a reference to `ExecutionRun`).
    """

    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.alias) and (node.asname or node.name) == name:
            return True
    return False


def test_execution_run_is_never_mutated_outside_execution_engine() -> None:
    culprits = [
        str(py_file.relative_to(REPO_ROOT))
        for py_file in _project_python_files()
        if "execution/engine.py" not in str(py_file) and "tests/" not in str(py_file.relative_to(REPO_ROOT))
        if _assigns_to_run_field(py_file)
    ]
    assert culprits == []


def test_execution_run_is_imported_for_write_access_only_by_execution_engine() -> None:
    importers = [
        str(py_file.relative_to(REPO_ROOT))
        for py_file in _project_python_files()
        if "tests/" not in str(py_file.relative_to(REPO_ROOT)) and _references_name(py_file, "ExecutionRun")
    ]
    # Every production file that references ExecutionRun at all does so
    # read-only (as a type annotation for confirm()/rollback()'s own
    # signatures) except engine.py and contract.py (its own definition).
    assert set(importers) <= {
        "execution/engine.py",
        "execution/contract.py",
        "execution/confirmation.py",
        "execution/confirmation_gate.py",
        "execution/rollback.py",
        "execution/__init__.py",
    }


# -- 3. PlanNotExecutableError never fires for an ordinary capability-availability gap ----


def test_an_unavailable_capability_is_a_failed_step_never_a_raised_precondition_error() -> None:
    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(PlanStep(step_id="S-1", capability="missing.op", requires_confirmation=False),),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )
    engine = ExecutionEngine(RetryPolicy(ConnectorRegistry()))

    result = engine.execute(plan, _context(_PerCapabilityConnectorInvoker({})))

    assert result.step_records[0].state is StepExecutionState.FAILED


def test_plan_not_executable_error_is_reserved_for_a_genuine_scheduler_precondition() -> None:
    cyclic_plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(
            PlanStep(step_id="S-1", capability="a.op", depends_on=("S-2",), requires_confirmation=False),
            PlanStep(step_id="S-2", capability="a.op", depends_on=("S-1",), requires_confirmation=False),
        ),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )
    engine = ExecutionEngine(RetryPolicy(ConnectorRegistry()))

    with pytest.raises(PlanNotExecutableError):
        engine.execute(cyclic_plan, _context(_PerCapabilityConnectorInvoker({})))
