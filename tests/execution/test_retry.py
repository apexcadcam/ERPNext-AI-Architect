"""Tests for `RetryPolicy` (Sprint 5 Architecture Package §17).

Uses a real `ConnectorRegistry` for classification (proving `RetryPolicy`
genuinely reads `idempotent`/`max_attempts` from the live registry — its
own `invoke_with_retries()` has no other source to read from, since it
takes a capability string, never a `PlanStep`) and a small scripted
`ConnectorInvoker` double for controllable invocation outcomes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry

from execution.retry import RetryPolicy

_TRIVIAL_CONNECTOR_PY = (
    "from integration.contract import ConnectorResponse\n"
    "from integration.lifecycle import ConnectorHealth, ConnectorLifecycle\n"
    "class _T(ConnectorLifecycle):\n"
    "    def connect(self): pass\n"
    "    def health_check(self): return ConnectorHealth(healthy=True)\n"
    "    def invoke(self, request): return ConnectorResponse(status='success', correlation_id=request.correlation_id)\n"
    "def create(manifest): return _T(manifest)\n"
)


class _ScriptedInvoker:
    """Returns responses from a fixed script, one per call; the last
    scripted response repeats if `invoke()` is called more times than the
    script has entries.
    """

    def __init__(self, responses: list[ConnectorResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def is_available(self, capability: str) -> bool:
        return True

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _registry_with(
    tmp_path: Path, *, capability: str, idempotent: bool, max_attempts: int = 1, base_delay_ms: int = 0
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
        "operations": [{"name": capability, "kind": "read", "idempotent": idempotent}],
        "max_attempts": max_attempts,
        "base_delay_ms": base_delay_ms,
        "entry_point": "connector:create",
    }
    (connector_dir / "connector.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (connector_dir / "connector.py").write_text(_TRIVIAL_CONNECTOR_PY, encoding="utf-8")

    registry = ConnectorRegistry()
    registry.register_all(registry.discover([tmp_path / "connectors"]))
    registry.validate()
    return registry


_SUCCESS = ConnectorResponse(status="success", correlation_id="corr-1")
_FAILURE = ConnectorResponse(status="failure", diagnostics="boom", correlation_id="corr-1")


def test_first_attempt_success_makes_exactly_one_call(tmp_path: Path) -> None:
    registry = _registry_with(tmp_path, capability="test.op", idempotent=True, max_attempts=3)
    invoker = _ScriptedInvoker([_SUCCESS])
    policy = RetryPolicy(registry)

    response, attempts = policy.invoke_with_retries(
        invoker, "test.op", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert response.status == "success"
    assert attempts == 1
    assert invoker.calls == 1


def test_idempotent_failure_is_retried_up_to_max_attempts(tmp_path: Path) -> None:
    registry = _registry_with(tmp_path, capability="test.op", idempotent=True, max_attempts=3)
    invoker = _ScriptedInvoker([_FAILURE, _FAILURE, _FAILURE, _FAILURE])  # more failures than max_attempts
    policy = RetryPolicy(registry)

    response, attempts = policy.invoke_with_retries(
        invoker, "test.op", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert response.status == "failure"
    assert attempts == 3  # stopped exactly at max_attempts
    assert invoker.calls == 3


def test_idempotent_failure_that_recovers_stops_retrying_early(tmp_path: Path) -> None:
    registry = _registry_with(tmp_path, capability="test.op", idempotent=True, max_attempts=5)
    invoker = _ScriptedInvoker([_FAILURE, _FAILURE, _SUCCESS])
    policy = RetryPolicy(registry)

    response, attempts = policy.invoke_with_retries(
        invoker, "test.op", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert response.status == "success"
    assert attempts == 3
    assert invoker.calls == 3


def test_non_idempotent_failure_is_never_retried(tmp_path: Path) -> None:
    registry = _registry_with(tmp_path, capability="test.op", idempotent=False, max_attempts=5)
    invoker = _ScriptedInvoker([_FAILURE, _SUCCESS])  # would succeed on retry, but must never get there
    policy = RetryPolicy(registry)

    response, attempts = policy.invoke_with_retries(
        invoker, "test.op", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert response.status == "failure"
    assert attempts == 1
    assert invoker.calls == 1


def test_unknown_capability_is_never_retried(tmp_path: Path) -> None:
    registry = _registry_with(tmp_path, capability="test.op", idempotent=True, max_attempts=5)
    invoker = _ScriptedInvoker([_FAILURE, _SUCCESS])
    policy = RetryPolicy(registry)

    response, attempts = policy.invoke_with_retries(
        invoker, "unknown.capability", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert response.status == "failure"
    assert attempts == 1
    assert invoker.calls == 1


def test_reads_classification_from_the_live_registry_true_case(tmp_path: Path) -> None:
    # A different registry with the *same* capability name classified
    # differently produces different retry behavior -- proving the
    # classification genuinely comes from this registry, not any fixed
    # assumption.
    registry = _registry_with(tmp_path, capability="test.op", idempotent=True, max_attempts=4)
    invoker = _ScriptedInvoker([_FAILURE, _FAILURE, _FAILURE, _FAILURE])
    policy = RetryPolicy(registry)

    _, attempts = policy.invoke_with_retries(
        invoker, "test.op", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert attempts == 4


def test_reads_classification_from_the_live_registry_false_case(tmp_path: Path) -> None:
    registry = _registry_with(tmp_path, capability="test.op", idempotent=False, max_attempts=4)
    invoker = _ScriptedInvoker([_FAILURE, _FAILURE, _FAILURE, _FAILURE])
    policy = RetryPolicy(registry)

    _, attempts = policy.invoke_with_retries(
        invoker, "test.op", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert attempts == 1


def test_attempts_are_counted_regardless_of_final_outcome(tmp_path: Path) -> None:
    registry = _registry_with(tmp_path, capability="test.op", idempotent=True, max_attempts=2)
    invoker = _ScriptedInvoker([_FAILURE, _FAILURE])
    policy = RetryPolicy(registry)

    _, attempts = policy.invoke_with_retries(
        invoker, "test.op", {}, correlation_id="corr-1", requested_by="agent"
    )

    assert attempts == 2
