"""Sprint 5, Phase 7 — Scheduling Tie-Breaking (§24's own subsection,
added by Architecture Review Comment 4).

`tests/execution/test_scheduler.py` already proves `StepScheduler.order()`
itself is a stable topological sort keyed by original `Plan.steps` index,
never a `set`'s iteration order. This suite proves the same guarantee
holds one layer up, at the full `ExecutionEngine` level: the *order
connector invocations actually happen in* — not just the order
`StepScheduler` computes — is stable and matches declaration order among
simultaneously-ready, independent steps, repeatably.
"""

from __future__ import annotations

from typing import Any

from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry
from planning.contract import Plan, PlanStep, RuntimeContextInfo

from execution.cancellation import CancellationToken
from execution.confirmation import DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.engine import ExecutionEngine
from execution.retry import RetryPolicy


class _RecordingConnectorInvoker:
    """Records the exact order capabilities were invoked in — the
    observable proxy for "the order the engine actually dispatched
    steps," independent of any dict/set iteration order internal to
    `StepScheduler` or `ExecutionEngine`.
    """

    def __init__(self) -> None:
        self.invocation_order: list[str] = []

    def is_available(self, capability: str) -> bool:
        return True

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        self.invocation_order.append(capability)
        return ConnectorResponse(status="success", correlation_id=correlation_id)


def _plan_with_five_independent_steps() -> Plan:
    # Five steps, zero dependencies among any of them -- every one is
    # simultaneously "ready" from StepScheduler's very first moment, so
    # only the tie-breaking rule (original declaration order), never
    # dependency order, determines the outcome.
    return Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=tuple(
            PlanStep(step_id=f"S-{i}", capability=f"cap-{i}.op", requires_confirmation=False)
            for i in ("e", "c", "a", "d", "b")
        ),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )


def _execute_and_record(plan: Plan) -> list[str]:
    invoker = _RecordingConnectorInvoker()
    context = ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    engine = ExecutionEngine(RetryPolicy(ConnectorRegistry()))
    engine.execute(plan, context)
    return invoker.invocation_order


def test_independent_steps_are_invoked_in_original_declaration_order() -> None:
    plan = _plan_with_five_independent_steps()
    expected = [f"cap-{i}.op" for i in ("e", "c", "a", "d", "b")]

    assert _execute_and_record(plan) == expected


def test_invocation_order_is_stable_across_repeated_runs() -> None:
    plan = _plan_with_five_independent_steps()

    orders = [_execute_and_record(plan) for _ in range(5)]

    assert all(order == orders[0] for order in orders)


def test_a_diamond_dependency_still_resolves_ties_among_ready_steps_by_declaration_order() -> None:
    # S-2 and S-3 both depend only on S-1 and become ready simultaneously
    # once S-1 succeeds; S-3 was declared first, so it must run first.
    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(
            PlanStep(step_id="S-1", capability="root.op", requires_confirmation=False),
            PlanStep(step_id="S-2", capability="second.op", depends_on=("S-1",), requires_confirmation=False),
            PlanStep(step_id="S-3", capability="first.op", depends_on=("S-1",), requires_confirmation=False),
        ),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )

    assert _execute_and_record(plan) == ["root.op", "second.op", "first.op"]
