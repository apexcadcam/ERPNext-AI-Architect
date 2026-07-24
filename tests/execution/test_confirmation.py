"""Tests for `ConfirmationProvider`/`DenyAllConfirmationProvider`
(Sprint 5 Architecture Package §9.4)."""

from __future__ import annotations

import pytest
from planning.contract import PlanStep

from execution.confirmation import ConfirmationProvider, DenyAllConfirmationProvider
from execution.contract import ExecutionRun
from execution.lifecycle import ExecutionRunState


def _run() -> ExecutionRun:
    return ExecutionRun(
        execution_run_id="R-1",
        plan_id="P-1",
        goal_id="G-1",
        state=ExecutionRunState.RUNNING,
        started_at="2026-01-01T00:00:00Z",
    )


def _step(requires_confirmation: bool = True) -> PlanStep:
    return PlanStep(
        step_id="S-1", capability="filesystem.write_text", requires_confirmation=requires_confirmation
    )


def test_confirmation_provider_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ConfirmationProvider()  # type: ignore[abstract]


def test_deny_all_confirmation_provider_always_denies() -> None:
    provider = DenyAllConfirmationProvider()
    assert provider.confirm(_step(), _run()) is False


def test_deny_all_confirmation_provider_denies_regardless_of_step_shape() -> None:
    provider = DenyAllConfirmationProvider()
    assert provider.confirm(_step(requires_confirmation=False), _run()) is False


def test_deny_all_confirmation_provider_is_a_confirmation_provider() -> None:
    assert isinstance(DenyAllConfirmationProvider(), ConfirmationProvider)


def test_confirmation_provider_exposes_only_confirm() -> None:
    public_attrs = {name for name in dir(ConfirmationProvider) if not name.startswith("_")}
    assert public_attrs == {"confirm"}
