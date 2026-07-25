"""Sprint 6, Phase 7 — Event Observability.

The full-system proof of ADR Candidate C (Sprint 6 Architecture Package
§18): a real `Runtime.boot()`, a subscriber registered on the real
`runtime.event_bus` capability *before* `execute()` runs, and a real
`ExecutionContext` assembled with that same bus (manually, by this test —
no automatic `ExecutionContext` assembly exists yet, §3's own Non-Goal) —
proving real events genuinely arrive for a real run through the real
`EventBus`, not just a fake recorder at the unit level
(`tests/execution/test_engine.py`'s own scope).
"""

from __future__ import annotations

import time
from pathlib import Path

from planning.contract import Plan, PlanStep, RuntimeContextInfo
from runtime.boot import Runtime
from runtime.events.bus import Event

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider
from execution.connector_invoker import RegistryConnectorInvoker
from execution.context import ExecutionContext
from execution.contract import ExecutionRun
from execution.events import EXECUTION_COMPLETED, EXECUTION_STARTED, STEP_STARTED, STEP_SUCCEEDED
from execution.module import CAPABILITY_EXECUTION_ENGINE
from tests.sprint6.conftest import root_filesystem_connector_at


class _AllowAllConfirmationProvider(ConfirmationProvider):
    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        return True


def _wait_for(predicate: object, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.01)
    raise AssertionError("condition was not met within the timeout")


def test_a_real_run_publishes_real_events_through_runtime_event_bus(
    booted_runtime: Runtime, tmp_path: Path
) -> None:
    (tmp_path / "input.txt").write_text("hello", encoding="utf-8")

    event_bus = booted_runtime.container.resolve("runtime.event_bus")
    registry = booted_runtime.container.resolve("integration.connector_registry")
    root_filesystem_connector_at(registry, tmp_path)
    execution_engine = booted_runtime.container.resolve(CAPABILITY_EXECUTION_ENGINE)

    received: list[Event] = []
    for event_type in (EXECUTION_STARTED, STEP_STARTED, STEP_SUCCEEDED, EXECUTION_COMPLETED):
        event_bus.subscribe(event_type, received.append)

    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(
            PlanStep(
                step_id="S-1",
                capability="filesystem.read_text",
                requires_confirmation=False,
                parameters={"path": "input.txt"},
            ),
        ),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="stub",
    )
    context = ExecutionContext(
        connector_invoker=RegistryConnectorInvoker(registry),
        confirmation_provider=_AllowAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-sprint6",
        cancellation_token=CancellationToken(),
        event_bus=event_bus,
    )

    result = execution_engine.execute(plan, context)

    # EventBus delivery is asynchronous (per-subscription background
    # threads, runtime/events/bus.py) -- wait for all four, rather than
    # asserting immediately after execute() returns.
    _wait_for(lambda: len(received) == 4)

    event_types = {e.event_type for e in received}
    assert event_types == {EXECUTION_STARTED, STEP_STARTED, STEP_SUCCEEDED, EXECUTION_COMPLETED}
    assert all(e.correlation_id == "corr-sprint6" for e in received)
    assert all(e.payload["execution_run_id"] == result.execution_run_id for e in received)
