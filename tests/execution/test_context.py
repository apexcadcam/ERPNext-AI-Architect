"""Tests for `ExecutionContext` (Sprint 5 Architecture Package §11)."""

from __future__ import annotations

from typing import Any

import pytest
from planning.contract import RuntimeContextInfo
from pydantic import ValidationError

from execution.cancellation import CancellationToken
from execution.confirmation import DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.rollback import UnsupportedRollbackStrategy


class _NullConnectorInvoker:
    def is_available(self, capability: str) -> bool:
        return False

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> Any:
        raise AssertionError("must not be called by these tests")


def _runtime_context() -> RuntimeContextInfo:
    return RuntimeContextInfo(environment="Development", requested_by="test-suite")


def test_execution_context_constructs_with_required_fields_only() -> None:
    context = ExecutionContext(
        connector_invoker=_NullConnectorInvoker(),
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=_runtime_context(),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    assert isinstance(context.rollback_strategy, UnsupportedRollbackStrategy)


def test_execution_context_rollback_strategy_defaults_to_unsupported() -> None:
    context = ExecutionContext(
        connector_invoker=_NullConnectorInvoker(),
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=_runtime_context(),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    outcome = context.rollback_strategy.rollback  # just confirm attribute presence/type
    assert callable(outcome)


def test_execution_context_confirmation_provider_is_required() -> None:
    with pytest.raises(ValidationError):
        ExecutionContext(  # type: ignore[call-arg]
            connector_invoker=_NullConnectorInvoker(),
            runtime_context=_runtime_context(),
            correlation_id="corr-1",
            cancellation_token=CancellationToken(),
        )


def test_execution_context_cancellation_token_is_required() -> None:
    with pytest.raises(ValidationError):
        ExecutionContext(  # type: ignore[call-arg]
            connector_invoker=_NullConnectorInvoker(),
            confirmation_provider=DenyAllConfirmationProvider(),
            runtime_context=_runtime_context(),
            correlation_id="corr-1",
        )


def test_execution_context_event_bus_defaults_to_none() -> None:
    # Sprint 6 Architecture Package §18, ADR Candidate C: event_bus is now
    # an approved, optional, additive field -- every construction that
    # predates this Sprint (like every other test in this file) omits it
    # and must keep working unchanged.
    context = ExecutionContext(
        connector_invoker=_NullConnectorInvoker(),
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=_runtime_context(),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    assert context.event_bus is None


def test_execution_context_is_frozen() -> None:
    context = ExecutionContext(
        connector_invoker=_NullConnectorInvoker(),
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=_runtime_context(),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    with pytest.raises(ValidationError):
        context.correlation_id = "corr-2"


def test_execution_context_empty_correlation_id_raises() -> None:
    with pytest.raises(ValidationError):
        ExecutionContext(
            connector_invoker=_NullConnectorInvoker(),
            confirmation_provider=DenyAllConfirmationProvider(),
            runtime_context=_runtime_context(),
            correlation_id="",
            cancellation_token=CancellationToken(),
        )


def test_execution_context_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ExecutionContext(
            connector_invoker=_NullConnectorInvoker(),
            confirmation_provider=DenyAllConfirmationProvider(),
            runtime_context=_runtime_context(),
            correlation_id="corr-1",
            cancellation_token=CancellationToken(),
            nonsense="x",  # type: ignore[call-arg]
        )
