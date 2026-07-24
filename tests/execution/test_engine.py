"""Tests for `ExecutionEngine` (Sprint 5 Architecture Package §8, §9.2,
§15), Phase 5.

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

from pathlib import Path
from typing import Any

import pytest
import yaml
from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry, DiscoveredConnector
from planning.contract import Plan, PlanStep, RuntimeContextInfo

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider, DenyAllConfirmationProvider
from execution.context import ExecutionContext
from execution.contract import ExecutionRun
from execution.engine import ExecutionEngine
from execution.errors import PlanNotExecutableError
from execution.lifecycle import ExecutionRunState, StepExecutionState
from execution.retry import RetryPolicy


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
) -> ExecutionContext:
    return ExecutionContext(
        connector_invoker=invoker,
        confirmation_provider=confirmation_provider or DenyAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
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
