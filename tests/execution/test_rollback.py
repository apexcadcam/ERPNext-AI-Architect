"""Tests for `RollbackStrategy`/`UnsupportedRollbackStrategy`
(Sprint 5 Architecture Package §9.5, §19)."""

from __future__ import annotations

from typing import Any

import pytest
from planning.contract import RuntimeContextInfo

from execution.cancellation import CancellationToken
from execution.confirmation import DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.contract import StepExecutionRecord
from execution.lifecycle import StepExecutionState
from execution.rollback import RollbackStrategy, UnsupportedRollbackStrategy


class _NullConnectorInvoker:
    def is_available(self, capability: str) -> bool:
        return False

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> Any:
        raise AssertionError("must not be called by these tests")


def _context() -> ExecutionContext:
    return ExecutionContext(
        connector_invoker=_NullConnectorInvoker(),
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )


def test_rollback_strategy_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        RollbackStrategy()  # type: ignore[abstract]


def test_unsupported_rollback_strategy_always_reports_unsupported() -> None:
    strategy = UnsupportedRollbackStrategy()
    record = StepExecutionRecord(step_id="S-1", state=StepExecutionState.FAILED)

    outcome = strategy.rollback(record, _context())

    assert outcome.supported is False
    assert outcome.detail


def test_unsupported_rollback_strategy_is_a_rollback_strategy() -> None:
    assert isinstance(UnsupportedRollbackStrategy(), RollbackStrategy)


def test_rollback_strategy_exposes_only_rollback() -> None:
    public_attrs = {name for name in dir(RollbackStrategy) if not name.startswith("_")}
    assert public_attrs == {"rollback"}
