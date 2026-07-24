"""Tests for the Connector Lifecycle interface (Sprint 3 Phase 3's own
"initialize / connect / disconnect / health_check" requirement, extended by
Sprint 5 Phase 1's `invoke()`).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from integration import (
    ConnectorHealth,
    ConnectorLifecycle,
    ConnectorManifest,
    ConnectorRequest,
    ConnectorResponse,
)


def _manifest() -> ConnectorManifest:
    return ConnectorManifest(
        connector_id="erpnext",
        display_name="ERPNext",
        maintained_by="integration-layer",
        target_system_type="erpnext-site",
        version="0.1.0",
        endpoint_kind="url",
        endpoint_reference="https://example.invalid",
        entry_point="connector:create",
    )


def _request(operation: str = "erpnext.read_record") -> ConnectorRequest:
    return ConnectorRequest(operation=operation, correlation_id="corr-1", requested_by="test-suite")


class _Minimal(ConnectorLifecycle):
    def connect(self) -> None:
        pass

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(healthy=True, detail="ok")

    def invoke(self, request: ConnectorRequest) -> ConnectorResponse:
        return ConnectorResponse(status="success", correlation_id=request.correlation_id)


def test_connector_lifecycle_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ConnectorLifecycle(_manifest())  # type: ignore[abstract]


def test_a_subclass_missing_connect_cannot_be_instantiated() -> None:
    class _MissingConnect(ConnectorLifecycle):
        def health_check(self) -> ConnectorHealth:
            return ConnectorHealth(healthy=True)

        def invoke(self, request: ConnectorRequest) -> ConnectorResponse:
            return ConnectorResponse(status="success", correlation_id=request.correlation_id)

    with pytest.raises(TypeError):
        _MissingConnect(_manifest())  # type: ignore[abstract]


def test_a_subclass_missing_health_check_cannot_be_instantiated() -> None:
    class _MissingHealthCheck(ConnectorLifecycle):
        def connect(self) -> None:
            pass

        def invoke(self, request: ConnectorRequest) -> ConnectorResponse:
            return ConnectorResponse(status="success", correlation_id=request.correlation_id)

    with pytest.raises(TypeError):
        _MissingHealthCheck(_manifest())  # type: ignore[abstract]


def test_a_subclass_missing_invoke_cannot_be_instantiated() -> None:
    class _MissingInvoke(ConnectorLifecycle):
        def connect(self) -> None:
            pass

        def health_check(self) -> ConnectorHealth:
            return ConnectorHealth(healthy=True)

    with pytest.raises(TypeError):
        _MissingInvoke(_manifest())  # type: ignore[abstract]


def test_a_minimal_compliant_subclass_constructs_and_carries_its_manifest() -> None:
    manifest = _manifest()
    connector = _Minimal(manifest)

    assert connector.manifest is manifest


def test_initialize_defaults_to_a_no_op() -> None:
    connector = _Minimal(_manifest())
    connector.initialize()  # must not raise, must not require overriding


def test_disconnect_defaults_to_a_no_op() -> None:
    connector = _Minimal(_manifest())
    connector.disconnect()  # must not raise, must not require overriding


def test_full_lifecycle_sequence_runs_in_declared_order() -> None:
    calls: list[str] = []

    class _Tracking(ConnectorLifecycle):
        def initialize(self) -> None:
            calls.append("initialize")

        def connect(self) -> None:
            calls.append("connect")

        def disconnect(self) -> None:
            calls.append("disconnect")

        def health_check(self) -> ConnectorHealth:
            calls.append("health_check")
            return ConnectorHealth(healthy=True)

        def invoke(self, request: ConnectorRequest) -> ConnectorResponse:
            calls.append("invoke")
            return ConnectorResponse(status="success", correlation_id=request.correlation_id)

    connector = _Tracking(_manifest())
    connector.initialize()
    connector.connect()
    connector.health_check()
    connector.invoke(_request())
    connector.disconnect()

    assert calls == ["initialize", "connect", "health_check", "invoke", "disconnect"]


def test_health_check_result_is_frozen() -> None:
    health = ConnectorHealth(healthy=True, detail="ok")
    with pytest.raises(ValidationError):
        health.healthy = False


# -- invoke() itself -------------------------------------------------------------------


def test_invoke_returns_a_connector_response() -> None:
    connector = _Minimal(_manifest())
    response = connector.invoke(_request())

    assert isinstance(response, ConnectorResponse)
    assert response.status == "success"


def test_invoke_response_carries_the_requests_correlation_id() -> None:
    connector = _Minimal(_manifest())
    response = connector.invoke(_request())

    assert response.correlation_id == "corr-1"
