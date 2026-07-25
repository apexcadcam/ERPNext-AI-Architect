"""Tests for `ExecutionEngine` (Sprint 5 Architecture Package §8, §9.2,
§15, §18, §19), Phases 5 and 6.

Uses `_ScriptedConnectorInvoker` (a fake `ConnectorInvoker`, no live
connector) paired with a small, self-contained `ConnectorRegistry` built
the same way `tests/execution/test_retry.py` builds its own — proving
`RetryPolicy` genuinely reads `idempotent`/`max_attempts` classification
from the registry, independently of whatever the fake invoker returns —
for every fake-based scenario, plus one end-to-end test against the real
Filesystem connector (mirroring `tests/execution/test_connector_invoker.py`'s
own real-registry pattern), per the Sprint 5 Implementation Plan's own
validation strategy for this phase.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml
from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry, DiscoveredConnector
from planning.contract import Plan, PlanStep, RuntimeContextInfo
from runtime.events.bus import Event, EventBus, EventBusBackpressureError

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider, DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.contract import ExecutionRun, RollbackOutcome, StepExecutionRecord
from execution.engine import ExecutionEngine
from execution.errors import PlanNotExecutableError
from execution.events import (
    EXECUTION_CANCELLED,
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
    EXECUTION_STARTED,
    STEP_AWAITING_CONFIRMATION,
    STEP_FAILED,
    STEP_SKIPPED,
    STEP_STARTED,
    STEP_SUCCEEDED,
)
from execution.lifecycle import ExecutionRunState, StepExecutionState
from execution.retry import RetryPolicy
from execution.rollback import RollbackStrategy, UnsupportedRollbackStrategy


class _ScriptedConnectorInvoker:
    """A fake `ConnectorInvoker`: `is_available()` answers from a fixed
    set, `invoke()` replays a fixed, per-capability script of responses
    (the last entry repeats past the end of its own script).
    """

    def __init__(
        self, responses: dict[str, list[ConnectorResponse]], *, available: set[str] | None = None
    ) -> None:
        self._responses = responses
        self._available = available if available is not None else set(responses)
        self._call_counts: dict[str, int] = {}
        self.calls: list[str] = []

    def is_available(self, capability: str) -> bool:
        return capability in self._available

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        self.calls.append(capability)
        script = self._responses[capability]
        index = self._call_counts.get(capability, 0)
        self._call_counts[capability] = index + 1
        return script[min(index, len(script) - 1)]


class _SpyConfirmationProvider(ConfirmationProvider):
    def __init__(self, *, grants: bool) -> None:
        self._grants = grants
        self.seen_run_states: list[ExecutionRunState] = []

    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        self.seen_run_states.append(run.state)
        return self._grants


_SUCCESS = ConnectorResponse(status="success", correlation_id="corr-1")
_PARTIAL = ConnectorResponse(status="partial", diagnostics="partial detail", correlation_id="corr-1")
_FAILURE = ConnectorResponse(status="failure", diagnostics="boom", correlation_id="corr-1")


def _registry(
    tmp_path: Path, operations: list[dict[str, Any]], *, max_attempts: int = 1
) -> ConnectorRegistry:
    connector_dir = tmp_path / "connectors" / "test"
    connector_dir.mkdir(parents=True)
    manifest = {
        "connector_id": "test",
        "display_name": "Test",
        "maintained_by": "test-suite",
        "target_system_type": "filesystem",
        "version": "0.1.0",
        "endpoint_kind": "local_path",
        "endpoint_reference": ".",
        "operations": operations,
        "max_attempts": max_attempts,
        "base_delay_ms": 0,
        "entry_point": "connector:create",
    }
    (connector_dir / "connector.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (connector_dir / "connector.py").write_text(
        "from integration.contract import ConnectorResponse\n"
        "from integration.lifecycle import ConnectorHealth, ConnectorLifecycle\n"
        "class _T(ConnectorLifecycle):\n"
        "    def connect(self): pass\n"
        "    def health_check(self): return ConnectorHealth(healthy=True)\n"
        "    def invoke(self, request): return ConnectorResponse(status='success', correlation_id=request.correlation_id)\n"
        "def create(manifest): return _T(manifest)\n",
        encoding="utf-8",
    )
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([tmp_path / "connectors"]))
    registry.validate()
    return registry


def _context(
    *,
    invoker: Any,
    confirmation_provider: ConfirmationProvider | None = None,
    event_bus: Any = None,
) -> ExecutionContext:
    return ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=confirmation_provider or DenyAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
        event_bus=event_bus,
    )


def _plan(steps: tuple[PlanStep, ...]) -> Plan:
    return Plan(
        plan_id="P-1", goal_id="G-1", steps=steps, created_at="2026-01-01T00:00:00Z", strategy_name="stub"
    )


def _step(
    step_id: str,
    capability: str,
    *,
    depends_on: tuple[str, ...] = (),
    requires_confirmation: bool = False,
    parameters: dict[str, Any] | None = None,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        capability=capability,
        depends_on=depends_on,
        requires_confirmation=requires_confirmation,
        parameters=parameters or {},
    )


# -- Happy path -------------------------------------------------------------------------


def test_empty_plan_completes_with_no_step_records(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [])
    engine = ExecutionEngine(RetryPolicy(registry))
    context = _context(invoker=_ScriptedConnectorInvoker({}))

    result = engine.execute(_plan(()), context)

    assert result.final_state is ExecutionRunState.COMPLETED
    assert result.step_records == ()
    assert result.plan_id == "P-1"


def test_two_independent_successful_steps_complete(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            {"name": "a.op", "kind": "read", "idempotent": True},
            {"name": "b.op", "kind": "read", "idempotent": True},
        ],
    )
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS], "b.op": [_SUCCESS]})
    context = _context(invoker=invoker)
    plan = _plan((_step("S-1", "a.op"), _step("S-2", "b.op")))

    result = engine.execute(plan, context)

    assert result.final_state is ExecutionRunState.COMPLETED
    assert {r.step_id: r.state for r in result.step_records} == {
        "S-1": StepExecutionState.SUCCEEDED,
        "S-2": StepExecutionState.SUCCEEDED,
    }


def test_partial_status_counts_as_succeeded(tmp_path: Path) -> None:
    invoker = _ScriptedConnectorInvoker({"a.op": [_PARTIAL]})
    context = _context(invoker=invoker)
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    record = result.step_records[0]
    assert record.state is StepExecutionState.SUCCEEDED
    assert record.response is not None
    assert record.response.status == "partial"


# -- §16.2 Failure Scenarios --------------------------------------------------------------


def test_unavailable_capability_fails_the_step_without_invoking(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({}, available=set())
    context = _context(invoker=invoker)

    result = engine.execute(_plan((_step("S-1", "missing.capability"),)), context)

    record = result.step_records[0]
    assert record.state is StepExecutionState.FAILED
    assert record.response is not None
    assert record.response.status == "failure"
    assert invoker.calls == []  # never invoked -- caught by the is_available() pre-check


def test_dependent_step_is_skipped_after_its_dependency_fails(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE]})
    context = _context(invoker=invoker)
    plan = _plan((_step("S-1", "a.op"), _step("S-2", "a.op", depends_on=("S-1",))))

    result = engine.execute(plan, context)

    records = {r.step_id: r.state for r in result.step_records}
    assert records["S-1"] is StepExecutionState.FAILED
    assert records["S-2"] is StepExecutionState.SKIPPED
    assert result.final_state is ExecutionRunState.FAILED


def test_independent_step_still_runs_after_an_unrelated_step_fails(tmp_path: Path) -> None:
    # Best-effort model (§15.5): one step's failure never aborts the run.
    registry = _registry(
        tmp_path,
        [
            {"name": "a.op", "kind": "read", "idempotent": False},
            {"name": "b.op", "kind": "read", "idempotent": True},
        ],
    )
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE], "b.op": [_SUCCESS]})
    context = _context(invoker=invoker)
    plan = _plan((_step("S-1", "a.op"), _step("S-2", "b.op")))

    result = engine.execute(plan, context)

    records = {r.step_id: r.state for r in result.step_records}
    assert records["S-1"] is StepExecutionState.FAILED
    assert records["S-2"] is StepExecutionState.SUCCEEDED
    assert result.final_state is ExecutionRunState.FAILED


def test_confirmation_denied_skips_not_fails(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    context = _context(invoker=invoker, confirmation_provider=DenyAllConfirmationProvider())
    plan = _plan((_step("S-1", "a.op", requires_confirmation=True),))

    result = engine.execute(plan, context)

    record = result.step_records[0]
    assert record.state is StepExecutionState.SKIPPED
    assert record.confirmation_granted is False
    assert invoker.calls == []  # denial short-circuits before invocation
    assert result.final_state is ExecutionRunState.COMPLETED  # a denial is not a failure


def test_confirmation_granted_proceeds_to_invocation(tmp_path: Path) -> None:
    class _AllowAll(ConfirmationProvider):
        def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
            return True

    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    context = _context(invoker=invoker, confirmation_provider=_AllowAll())

    result = engine.execute(_plan((_step("S-1", "a.op", requires_confirmation=True),)), context)

    record = result.step_records[0]
    assert record.state is StepExecutionState.SUCCEEDED
    assert record.confirmation_granted is True


def test_no_confirmation_required_never_consults_the_provider(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    provider = _SpyConfirmationProvider(grants=True)
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    context = _context(invoker=invoker, confirmation_provider=provider)

    result = engine.execute(_plan((_step("S-1", "a.op", requires_confirmation=False),)), context)

    assert result.step_records[0].confirmation_granted is None
    assert provider.seen_run_states == []  # never called at all


def test_idempotent_failure_is_retried_to_exhaustion(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}], max_attempts=3)
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE, _FAILURE, _FAILURE]})
    context = _context(invoker=invoker)

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    record = result.step_records[0]
    assert record.state is StepExecutionState.FAILED
    assert record.attempts == 3


def test_non_idempotent_failure_is_never_retried(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}], max_attempts=5)
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE, _SUCCESS]})
    context = _context(invoker=invoker)

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    record = result.step_records[0]
    assert record.state is StepExecutionState.FAILED
    assert record.attempts == 1


# -- PlanNotExecutableError (engine-internal precondition only) -----------------------------


def test_a_dependency_cycle_that_evaded_planning_time_validation_raises(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [])
    engine = ExecutionEngine(RetryPolicy(registry))
    context = _context(invoker=_ScriptedConnectorInvoker({}))
    # Bypasses planning/validation.validate_plan entirely -- Plan itself does
    # not check for cycles, only ExecutionEngine's own defensive precondition
    # does, per execution/errors.py's PlanNotExecutableError docstring.
    cyclic_plan = _plan(
        (_step("S-1", "a.op", depends_on=("S-2",)), _step("S-2", "a.op", depends_on=("S-1",)))
    )

    with pytest.raises(PlanNotExecutableError):
        engine.execute(cyclic_plan, context)


# -- Ownership ----------------------------------------------------------------------------


def test_confirmation_provider_sees_the_run_already_transitioned_to_running(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    provider = _SpyConfirmationProvider(grants=True)
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    context = _context(invoker=invoker, confirmation_provider=provider)

    engine.execute(_plan((_step("S-1", "a.op", requires_confirmation=True),)), context)

    assert provider.seen_run_states == [ExecutionRunState.RUNNING]


# -- Structural minimalism -----------------------------------------------------------------


def test_execution_engine_exposes_only_execute() -> None:
    public_attrs = {name for name in dir(ExecutionEngine) if not name.startswith("_")}
    assert public_attrs == {"execute"}


def test_execution_engine_requires_a_retry_policy() -> None:
    with pytest.raises(TypeError):
        ExecutionEngine()  # type: ignore[call-arg]


# -- Real Filesystem connector smoke test --------------------------------------------------

_CONNECTORS_DIR = Path(__file__).resolve().parents[2] / "integration" / "connectors"


def _real_registry_rooted_at(tmp_path: Path) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    discovered = registry.discover([_CONNECTORS_DIR])
    patched = [
        DiscoveredConnector(
            manifest=connector.manifest.model_copy(update={"endpoint_reference": str(tmp_path)}),
            connector_dir=connector.connector_dir,
        )
        for connector in discovered
    ]
    registry.register_all(patched)
    registry.validate()
    return registry


def test_end_to_end_against_the_real_filesystem_connector(tmp_path: Path) -> None:
    from execution.connector_invoker import RegistryConnectorInvoker

    (tmp_path / "input.txt").write_text("hello", encoding="utf-8")
    registry = _real_registry_rooted_at(tmp_path)
    engine = ExecutionEngine(RetryPolicy(registry))

    class _AllowAll(ConfirmationProvider):
        def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
            return True

    context = _context(invoker=RegistryConnectorInvoker(registry), confirmation_provider=_AllowAll())
    plan = _plan(
        (
            _step("S-1", "filesystem.read_text", parameters={"path": "input.txt"}),
            _step(
                "S-2",
                "filesystem.write_text",
                depends_on=("S-1",),
                requires_confirmation=True,
                parameters={"path": "output.txt", "content": "hello"},
            ),
        )
    )

    result = engine.execute(plan, context)

    assert result.final_state is ExecutionRunState.COMPLETED
    assert all(r.state is StepExecutionState.SUCCEEDED for r in result.step_records)
    assert (tmp_path / "output.txt").read_text(encoding="utf-8") == "hello"


# -- Cancellation (§18) -----------------------------------------------------------------


def test_cancellation_before_the_run_starts_skips_every_step(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    context = _context(invoker=invoker)
    context.cancellation_token.request_cancellation()
    plan = _plan((_step("S-1", "a.op"), _step("S-2", "a.op")))

    result = engine.execute(plan, context)

    assert result.final_state is ExecutionRunState.CANCELLED
    assert all(r.state is StepExecutionState.SKIPPED for r in result.step_records)
    assert invoker.calls == []


def test_cancellation_signaled_mid_run_lets_the_current_step_finish_first(tmp_path: Path) -> None:
    class _CancelOnFirstConfirm(ConfirmationProvider):
        """Signals cancellation the moment the engine consults it for the
        first step -- proving that step, already past its own cancellation
        checkpoint, still runs to completion rather than being interrupted.
        """

        def __init__(self, token: CancellationToken) -> None:
            self._token = token

        def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
            self._token.request_cancellation()
            return True

    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS], "b.op": [_SUCCESS]})
    token = CancellationToken()
    context = ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=_CancelOnFirstConfirm(token),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=token,
    )
    plan = _plan(
        (
            _step("S-1", "a.op", requires_confirmation=True),
            _step("S-2", "b.op", requires_confirmation=True),
        )
    )
    registry = _registry(
        tmp_path,
        [
            {"name": "a.op", "kind": "read", "idempotent": True},
            {"name": "b.op", "kind": "read", "idempotent": True},
        ],
    )
    engine = ExecutionEngine(RetryPolicy(registry))

    result = engine.execute(plan, context)

    records = {r.step_id: r.state for r in result.step_records}
    assert records["S-1"] is StepExecutionState.SUCCEEDED  # already dispatched -- runs to completion
    assert records["S-2"] is StepExecutionState.SKIPPED  # never reached -- cancellation caught it first
    assert result.final_state is ExecutionRunState.CANCELLED
    assert invoker.calls == ["a.op"]


def test_cancellation_final_state_is_cancelled_even_if_an_earlier_step_failed(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE]})
    context = _context(invoker=invoker)
    plan = _plan((_step("S-1", "a.op"), _step("S-2", "a.op")))

    # A wrapping fake invoker signals cancellation right after S-1's own
    # invocation completes (and fails) -- S-2 has no dependency on S-1, so
    # its own cancellation check (not an unmet-dependency skip) is what
    # catches it here.
    class _CancelAfterFirstInvoke:
        def __init__(self, inner: _ScriptedConnectorInvoker, token: CancellationToken) -> None:
            self._inner = inner
            self._token = token
            self._invocations = 0

        def is_available(self, capability: str) -> bool:
            return self._inner.is_available(capability)

        def invoke(
            self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
        ) -> ConnectorResponse:
            self._invocations += 1
            if self._invocations == 1:
                self._token.request_cancellation()
            return self._inner.invoke(
                capability, parameters, correlation_id=correlation_id, requested_by=requested_by
            )

    wrapped = _CancelAfterFirstInvoke(invoker, context.cancellation_token)
    context = ExecutionContext(
        connector_invoker=wrapped,
        confirmation_provider=context.confirmation_provider,
        runtime_context=context.runtime_context,
        correlation_id=context.correlation_id,
        cancellation_token=context.cancellation_token,
    )

    result = engine.execute(plan, context)

    records = {r.step_id: r.state for r in result.step_records}
    assert records["S-1"] is StepExecutionState.FAILED
    assert records["S-2"] is StepExecutionState.SKIPPED
    assert result.final_state is ExecutionRunState.CANCELLED  # cancellation wins over the earlier failure


# -- Rollback (§19) -----------------------------------------------------------------------


class _AlwaysRollbackStrategy(RollbackStrategy):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def rollback(self, record: StepExecutionRecord, context: ExecutionContext) -> RollbackOutcome:
        self.calls.append(record.step_id)
        return RollbackOutcome(supported=True, detail="undone")


def test_rollback_not_attempted_when_the_default_strategy_is_used(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE]})
    context = _context(invoker=invoker)
    assert isinstance(context.rollback_strategy, UnsupportedRollbackStrategy)

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    assert result.rollback_attempted is False
    assert result.final_state is ExecutionRunState.FAILED
    assert result.step_records[0].rollback_outcome is None


def test_rollback_not_attempted_for_a_completed_or_cancelled_run(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    strategy = _AlwaysRollbackStrategy()
    context = ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=DenyAllConfirmationProvider(),
        rollback_strategy=strategy,
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    assert result.final_state is ExecutionRunState.COMPLETED
    assert result.rollback_attempted is False
    assert strategy.calls == []


def test_rollback_pass_attempted_and_honestly_unsupported(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE]})
    context = ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=DenyAllConfirmationProvider(),
        rollback_strategy=UnsupportedRollbackStrategy(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    # UnsupportedRollbackStrategy() constructed explicitly, not the field's
    # own default -- still recognized as "not opted in" by isinstance, so
    # this must behave identically to the default-field case above.
    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    assert result.rollback_attempted is False
    assert result.final_state is ExecutionRunState.FAILED


def test_rollback_pass_attempted_and_marks_supported_steps_rolled_back(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            {"name": "a.op", "kind": "write", "idempotent": False},
            {"name": "b.op", "kind": "read", "idempotent": True},
        ],
    )
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE], "b.op": [_SUCCESS]})
    strategy = _AlwaysRollbackStrategy()
    context = ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=DenyAllConfirmationProvider(),
        rollback_strategy=strategy,
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )
    plan = _plan((_step("S-1", "a.op"), _step("S-2", "b.op")))

    result = engine.execute(plan, context)

    assert result.rollback_attempted is True
    assert result.final_state is ExecutionRunState.ROLLED_BACK
    records = {r.step_id: r for r in result.step_records}
    assert records["S-1"].state is StepExecutionState.ROLLED_BACK
    assert records["S-1"].rollback_outcome == RollbackOutcome(supported=True, detail="undone")
    assert (
        records["S-2"].state is StepExecutionState.SUCCEEDED
    )  # untouched -- rollback only visits FAILED steps
    assert records["S-2"].rollback_outcome is None
    assert strategy.calls == ["S-1"]


def test_rollback_never_silently_promotes_an_unsupported_step_to_rolled_back(tmp_path: Path) -> None:
    class _NeverSupportedStrategy(RollbackStrategy):
        def rollback(self, record: StepExecutionRecord, context: ExecutionContext) -> RollbackOutcome:
            return RollbackOutcome(supported=False, detail="cannot undo a write")

    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE]})
    context = ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=DenyAllConfirmationProvider(),
        rollback_strategy=_NeverSupportedStrategy(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    assert result.rollback_attempted is True
    assert result.final_state is ExecutionRunState.ROLLED_BACK  # the pass ran to completion
    record = result.step_records[0]
    assert record.state is StepExecutionState.FAILED  # never promoted -- rollback was refused
    assert record.rollback_outcome == RollbackOutcome(supported=False, detail="cannot undo a write")


# -- Event publication (Sprint 6 Architecture Package §18, ADR Candidate C) ---------------


class _RecordingEventBus(EventBus):
    """A real `EventBus` subclass (`ExecutionContext.event_bus` is typed
    as the concrete class, validated by `isinstance`, per ADR Candidate
    C's own "not a narrowed interface" text) whose `publish()` is
    overridden to record rather than actually deliver -- `ExecutionEngine`
    must never call anything else on it (see the AST test below).
    """

    def __init__(self) -> None:
        super().__init__()
        self.published: list[Event] = []

    def publish(self, event: Event) -> int:
        self.published.append(event)
        return 0


class _AlwaysRaisesEventBus(EventBus):
    """A deterministic stand-in for `EventBus.publish()`'s own possible
    `EventBusBackpressureError` -- proves `ExecutionEngine`'s own guard
    swallows *any* publish() exception, without the timing-dependent
    flakiness a real, BLOCK-policy-queue-kept-full scenario would
    introduce for the identical guarantee.
    """

    def publish(self, event: Event) -> int:
        raise EventBusBackpressureError("queue full")


def test_publishes_execution_started_step_started_step_succeeded_and_execution_completed(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    bus = _RecordingEventBus()
    context = _context(invoker=invoker, event_bus=bus)

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    events = {e.event_type: e for e in bus.published}
    assert set(events) == {EXECUTION_STARTED, STEP_STARTED, STEP_SUCCEEDED, EXECUTION_COMPLETED}
    assert events[EXECUTION_STARTED].payload == {
        "execution_run_id": result.execution_run_id,
        "plan_id": "P-1",
        "goal_id": "G-1",
    }
    assert events[STEP_STARTED].payload == {
        "execution_run_id": result.execution_run_id,
        "step_id": "S-1",
        "attempt": 1,
    }
    assert events[STEP_SUCCEEDED].payload == {"execution_run_id": result.execution_run_id, "step_id": "S-1"}
    assert events[EXECUTION_COMPLETED].payload == {
        "execution_run_id": result.execution_run_id,
        "final_state": "completed",
    }
    assert all(e.correlation_id == "corr-1" for e in bus.published)
    assert all(e.emitted_by == "execution" for e in bus.published)


def test_publishes_step_failed_and_execution_failed_with_failed_step_ids(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE]})
    bus = _RecordingEventBus()
    context = _context(invoker=invoker, event_bus=bus)

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)

    events = {e.event_type: e for e in bus.published}
    assert events[STEP_FAILED].payload == {
        "execution_run_id": result.execution_run_id,
        "step_id": "S-1",
        "detail": "boom",
    }
    assert events[EXECUTION_FAILED].payload == {
        "execution_run_id": result.execution_run_id,
        "failed_step_ids": ("S-1",),
    }
    assert EXECUTION_COMPLETED not in events
    assert STEP_SUCCEEDED not in events


def test_publishes_step_skipped_for_an_unmet_dependency(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_FAILURE]})
    bus = _RecordingEventBus()
    context = _context(invoker=invoker, event_bus=bus)
    plan = _plan((_step("S-1", "a.op"), _step("S-2", "a.op", depends_on=("S-1",))))

    engine.execute(plan, context)

    skipped = [e for e in bus.published if e.event_type == STEP_SKIPPED]
    assert len(skipped) == 1
    assert skipped[0].payload["step_id"] == "S-2"
    assert skipped[0].payload["reason"] == "an upstream dependency did not succeed"


def test_publishes_step_awaiting_confirmation_then_skipped_for_a_denied_confirmation(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "write", "idempotent": False}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    bus = _RecordingEventBus()
    context = _context(invoker=invoker, confirmation_provider=DenyAllConfirmationProvider(), event_bus=bus)
    plan = _plan((_step("S-1", "a.op", requires_confirmation=True),))

    engine.execute(plan, context)

    relevant = [e for e in bus.published if e.event_type in (STEP_AWAITING_CONFIRMATION, STEP_SKIPPED)]
    assert [e.event_type for e in relevant] == [STEP_AWAITING_CONFIRMATION, STEP_SKIPPED]
    assert relevant[0].payload["capability"] == "a.op"
    assert relevant[1].payload["reason"] == "confirmation denied"
    assert invoker.calls == []  # never invoked -- denial short-circuits before invocation


def test_never_publishes_step_awaiting_confirmation_when_not_required(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    bus = _RecordingEventBus()
    context = _context(invoker=invoker, event_bus=bus)

    engine.execute(_plan((_step("S-1", "a.op", requires_confirmation=False),)), context)

    assert STEP_AWAITING_CONFIRMATION not in {e.event_type for e in bus.published}


def test_publishes_execution_cancelled_and_step_skipped_for_cancellation(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    bus = _RecordingEventBus()
    context = _context(invoker=invoker, event_bus=bus)
    context.cancellation_token.request_cancellation()

    engine.execute(_plan((_step("S-1", "a.op"),)), context)

    event_types = {e.event_type for e in bus.published}
    assert EXECUTION_CANCELLED in event_types
    assert EXECUTION_COMPLETED not in event_types
    assert EXECUTION_FAILED not in event_types
    skipped = [e for e in bus.published if e.event_type == STEP_SKIPPED]
    assert skipped[0].payload["reason"] == "the run was already cancelled"


def test_no_event_bus_publishes_nothing_and_behaves_identically(tmp_path: Path) -> None:
    # context.event_bus is None (the default, every pre-Sprint-6 caller) --
    # must be indistinguishable from Phase 5/6 behavior.
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    context = _context(invoker=invoker)

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)  # must not raise

    assert context.event_bus is None
    assert result.final_state is ExecutionRunState.COMPLETED


def test_a_publishing_failure_never_escapes_execute(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [{"name": "a.op", "kind": "read", "idempotent": True}])
    engine = ExecutionEngine(RetryPolicy(registry))
    invoker = _ScriptedConnectorInvoker({"a.op": [_SUCCESS]})
    context = _context(invoker=invoker, event_bus=_AlwaysRaisesEventBus())

    result = engine.execute(_plan((_step("S-1", "a.op"),)), context)  # must not raise

    assert result.final_state is ExecutionRunState.COMPLETED
    assert result.step_records[0].state is StepExecutionState.SUCCEEDED


def test_engine_source_only_ever_calls_publish_on_event_bus() -> None:
    # Sprint 6 Architecture Review 3's own documentation recommendation:
    # ExecutionEngine treats context.event_bus as publish-only, even though
    # the concrete EventBus type exposes subscribe()/unsubscribe()/stats()/
    # shutdown() too. A real AST check, not a convention taken on faith.
    source = Path(__file__).resolve().parents[2] / "execution" / "engine.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    violations = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "event_bus"
        and node.attr != "publish"
    ]

    assert violations == []
