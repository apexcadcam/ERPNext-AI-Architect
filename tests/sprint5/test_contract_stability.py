"""Sprint 5, Phase 7 — Contract Stability.

`ExecutionEngine` continues to work correctly across multiple,
independently-written `ConfirmationProvider`/`RollbackStrategy`/
`ConnectorInvoker` implementations, with no assumption baked in about any
one reference implementation specifically — mirroring
`tests/sprint4/test_contract_stability.py`'s exact "swap the swappable
interface, the engine still works" pattern, applied here to Execution's
three interfaces instead of Planning's one.
"""

from __future__ import annotations

from typing import Any

from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry
from planning.contract import Plan, PlanStep, RuntimeContextInfo

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider
from execution.context import ExecutionContext
from execution.contract import ExecutionRun, RollbackOutcome, StepExecutionRecord
from execution.engine import ExecutionEngine
from execution.lifecycle import ExecutionRunState, StepExecutionState
from execution.retry import RetryPolicy
from execution.rollback import RollbackStrategy


class _AlwaysGrantConfirmationProvider(ConfirmationProvider):
    """A second, independently-written `ConfirmationProvider` — the
    opposite policy from `DenyAllConfirmationProvider`.
    """

    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        return True


class _AlwaysSupportedRollbackStrategy(RollbackStrategy):
    """A second, independently-written `RollbackStrategy` — the opposite
    of `UnsupportedRollbackStrategy`.
    """

    def rollback(self, record: StepExecutionRecord, context: ExecutionContext) -> RollbackOutcome:
        return RollbackOutcome(supported=True, detail="undone by test double")


class _StaticConnectorInvoker:
    """A second, independently-written `ConnectorInvoker` — a fixed,
    single-response fake, structurally unrelated to
    `RegistryConnectorInvoker`.
    """

    def __init__(self, *, available: bool, response: ConnectorResponse) -> None:
        self._available = available
        self._response = response

    def is_available(self, capability: str) -> bool:
        return self._available

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        return self._response


def _context(
    *, confirmation_provider: ConfirmationProvider, rollback_strategy: RollbackStrategy | None = None
) -> ExecutionContext:
    invoker = _StaticConnectorInvoker(
        available=True, response=ConnectorResponse(status="success", correlation_id="corr-1")
    )
    kwargs: dict[str, Any] = {}
    if rollback_strategy is not None:
        kwargs["rollback_strategy"] = rollback_strategy
    return ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=confirmation_provider,
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
        **kwargs,
    )


def _plan() -> Plan:
    return Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(PlanStep(step_id="S-1", capability="a.op", requires_confirmation=True),),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )


def _empty_registry_retry_policy() -> RetryPolicy:
    """`RetryPolicy` needs a `ConnectorRegistry` to classify against
    (§17) — irrelevant here, since `_StaticConnectorInvoker` never fails,
    so no retry decision is ever exercised. A minimal, empty registry
    stands in.
    """

    return RetryPolicy(ConnectorRegistry())


def test_engine_works_with_an_independently_written_confirmation_provider_that_grants() -> None:
    engine = ExecutionEngine(_empty_registry_retry_policy())
    context = _context(confirmation_provider=_AlwaysGrantConfirmationProvider())

    result = engine.execute(_plan(), context)

    assert result.step_records[0].state is StepExecutionState.SUCCEEDED
    assert result.step_records[0].confirmation_granted is True


def test_engine_works_with_an_independently_written_rollback_strategy() -> None:
    # A step whose confirmation is denied never fails -- use an
    # always-failing invoker instead, so the run actually reaches FAILED
    # and the rollback strategy is genuinely exercised.
    invoker = _StaticConnectorInvoker(
        available=True, response=ConnectorResponse(status="failure", correlation_id="corr-1")
    )
    context = ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=_AlwaysGrantConfirmationProvider(),
        rollback_strategy=_AlwaysSupportedRollbackStrategy(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    engine = ExecutionEngine(_empty_registry_retry_policy())

    result = engine.execute(_plan(), context)

    assert result.rollback_attempted is True
    assert result.final_state is ExecutionRunState.ROLLED_BACK
    assert result.step_records[0].state is StepExecutionState.ROLLED_BACK


def test_engine_works_with_an_independently_written_connector_invoker() -> None:
    engine = ExecutionEngine(_empty_registry_retry_policy())
    context = _context(confirmation_provider=_AlwaysGrantConfirmationProvider())

    result = engine.execute(_plan(), context)

    assert result.final_state is ExecutionRunState.COMPLETED
