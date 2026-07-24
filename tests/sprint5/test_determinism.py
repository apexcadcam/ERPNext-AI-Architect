"""Sprint 5, Phase 7 — Determinism (§24).

A more precise claim than Planning's own, exactly as §24 states it:
Execution's *orchestration* is deterministic — the same `(Plan,
ExecutionContext)` always attempts the same steps, in the same order, with
the same retry/gating decisions applied identically, given a fixed,
scripted `ConnectorInvoker`. Execution's *outcome* is not claimed to be
byte-identical across repeated runs, because `ExecutionRun`/
`StepExecutionRecord` carry live wall-clock `started_at`/`finished_at`
timestamps (§20 — `ExecutionRun` is the one place this package's own "no
mutation" discipline differs from Planning's frozen, timestamp-free
`Plan`). Every assertion below therefore compares the *decisions* — step
order, state, attempts, confirmation outcome, response — never the raw
timestamps.
"""

from __future__ import annotations

from typing import Any

from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry
from planning.contract import Plan, PlanStep, RuntimeContextInfo

from execution.cancellation import CancellationToken
from execution.confirmation import DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.contract import ExecutionResult, StepExecutionRecord
from execution.engine import ExecutionEngine
from execution.retry import RetryPolicy


class _FixedScriptConnectorInvoker:
    """Replays the exact same response for the exact same capability every
    time it is called — the "environment held fixed" precondition §24's
    own determinism claim depends on.
    """

    def __init__(self, responses: dict[str, ConnectorResponse]) -> None:
        self._responses = responses

    def is_available(self, capability: str) -> bool:
        return capability in self._responses

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        return self._responses[capability]


def _decision_shape(
    records: tuple[StepExecutionRecord, ...],
) -> tuple[tuple[str, str, int, bool | None], ...]:
    """The orchestration-decision fields §24 actually claims are
    deterministic — excludes `started_at`/`finished_at` and the full
    `ConnectorResponse` (which, for a fixed script, is redundant with
    `state` anyway).
    """

    return tuple((r.step_id, r.state.value, r.attempts, r.confirmation_granted) for r in records)


def _plan() -> Plan:
    return Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(
            PlanStep(step_id="S-1", capability="a.op", requires_confirmation=False),
            PlanStep(step_id="S-2", capability="b.op", requires_confirmation=False),
            PlanStep(step_id="S-3", capability="a.op", depends_on=("S-1",), requires_confirmation=False),
        ),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )


def _context() -> ExecutionContext:
    invoker = _FixedScriptConnectorInvoker(
        {
            "a.op": ConnectorResponse(status="success", correlation_id="corr-1"),
            "b.op": ConnectorResponse(status="failure", diagnostics="boom", correlation_id="corr-1"),
        }
    )
    return ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )


def _engine() -> ExecutionEngine:
    return ExecutionEngine(RetryPolicy(ConnectorRegistry()))


def _run() -> ExecutionResult:
    return _engine().execute(_plan(), _context())


def test_repeated_runs_produce_the_same_step_order_and_states() -> None:
    first = _run()
    second = _run()
    third = _run()

    assert _decision_shape(first.step_records) == _decision_shape(second.step_records)
    assert _decision_shape(second.step_records) == _decision_shape(third.step_records)


def test_repeated_runs_produce_the_same_final_state() -> None:
    first = _run()
    second = _run()

    assert first.final_state == second.final_state


def test_repeated_runs_across_separate_engines_and_contexts_are_identical() -> None:
    # Not the same ExecutionEngine/ExecutionContext object -- fresh
    # instances each time, still deterministic given the same (plan-shape,
    # fixed script).
    first = ExecutionEngine(RetryPolicy(ConnectorRegistry())).execute(_plan(), _context())
    second = ExecutionEngine(RetryPolicy(ConnectorRegistry())).execute(_plan(), _context())

    assert _decision_shape(first.step_records) == _decision_shape(second.step_records)


def test_determinism_holds_for_the_empty_plan_case() -> None:
    empty_plan = Plan(plan_id="P-1", goal_id="G-1", created_at="2026-01-01T00:00:00Z", strategy_name="stub")

    first = _engine().execute(empty_plan, _context())
    second = _engine().execute(empty_plan, _context())

    assert first.step_records == second.step_records == ()
    assert first.final_state == second.final_state
