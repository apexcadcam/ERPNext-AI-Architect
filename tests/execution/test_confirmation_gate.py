"""Tests for `ConfirmationGate` (Sprint 5 Architecture Package §8 step 3c,
§14).
"""

from __future__ import annotations

from planning.contract import PlanStep

from execution.confirmation import ConfirmationProvider
from execution.confirmation_gate import ConfirmationGate
from execution.contract import ExecutionRun
from execution.lifecycle import ExecutionRunState


class _SpyProvider(ConfirmationProvider):
    """Records every call, so a test can assert it was never called at
    all for a step that doesn't require confirmation.
    """

    def __init__(self, *, grants: bool) -> None:
        self._grants = grants
        self.calls: list[PlanStep] = []

    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        self.calls.append(step)
        return self._grants


def _run() -> ExecutionRun:
    return ExecutionRun(
        execution_run_id="R-1",
        plan_id="P-1",
        goal_id="G-1",
        state=ExecutionRunState.RUNNING,
        started_at="2026-01-01T00:00:00Z",
    )


def _step(requires_confirmation: bool) -> PlanStep:
    return PlanStep(
        step_id="S-1", capability="filesystem.write_text", requires_confirmation=requires_confirmation
    )


def test_step_not_requiring_confirmation_never_consults_the_provider() -> None:
    provider = _SpyProvider(grants=True)
    gate = ConfirmationGate(provider)

    result = gate.evaluate(_step(requires_confirmation=False), _run())

    assert result is None
    assert provider.calls == []  # never called, not just "called and ignored"


def test_step_requiring_confirmation_granted_returns_true() -> None:
    provider = _SpyProvider(grants=True)
    gate = ConfirmationGate(provider)

    result = gate.evaluate(_step(requires_confirmation=True), _run())

    assert result is True
    assert len(provider.calls) == 1


def test_step_requiring_confirmation_denied_returns_false() -> None:
    provider = _SpyProvider(grants=False)
    gate = ConfirmationGate(provider)

    result = gate.evaluate(_step(requires_confirmation=True), _run())

    assert result is False
    assert len(provider.calls) == 1


def test_evaluate_passes_the_exact_step_and_run_to_the_provider() -> None:
    provider = _SpyProvider(grants=True)
    gate = ConfirmationGate(provider)
    step = _step(requires_confirmation=True)
    run = _run()

    gate.evaluate(step, run)

    assert provider.calls == [step]


def test_return_value_matches_step_execution_record_confirmation_granted_shape() -> None:
    # None = not required, True = required+granted, False = required+denied
    # -- exactly StepExecutionRecord.confirmation_granted's own three cases.
    gate_granted = ConfirmationGate(_SpyProvider(grants=True))
    gate_denied = ConfirmationGate(_SpyProvider(grants=False))

    assert gate_granted.evaluate(_step(requires_confirmation=False), _run()) is None
    assert gate_granted.evaluate(_step(requires_confirmation=True), _run()) is True
    assert gate_denied.evaluate(_step(requires_confirmation=True), _run()) is False
