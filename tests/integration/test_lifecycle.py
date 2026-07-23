"""Tests for the Connector Lifecycle interface (Sprint 3 Phase 3's own
"initialize / connect / disconnect / health_check" requirement).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from integration import ConnectorHealth, ConnectorLifecycle, ConnectorManifest


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


def test_connector_lifecycle_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ConnectorLifecycle(_manifest())  # type: ignore[abstract]


def test_a_subclass_missing_connect_cannot_be_instantiated() -> None:
    class _MissingConnect(ConnectorLifecycle):
        def health_check(self) -> ConnectorHealth:
            return ConnectorHealth(healthy=True)

    with pytest.raises(TypeError):
        _MissingConnect(_manifest())  # type: ignore[abstract]


def test_a_subclass_missing_health_check_cannot_be_instantiated() -> None:
    class _MissingHealthCheck(ConnectorLifecycle):
        def connect(self) -> None:
            pass

    with pytest.raises(TypeError):
        _MissingHealthCheck(_manifest())  # type: ignore[abstract]


def test_a_minimal_compliant_subclass_constructs_and_carries_its_manifest() -> None:
    class _Minimal(ConnectorLifecycle):
        def connect(self) -> None:
            pass

        def health_check(self) -> ConnectorHealth:
            return ConnectorHealth(healthy=True, detail="ok")

    manifest = _manifest()
    connector = _Minimal(manifest)

    assert connector.manifest is manifest


def test_initialize_defaults_to_a_no_op() -> None:
    class _Minimal(ConnectorLifecycle):
        def connect(self) -> None:
            pass

        def health_check(self) -> ConnectorHealth:
            return ConnectorHealth(healthy=True)

    connector = _Minimal(_manifest())
    connector.initialize()  # must not raise, must not require overriding


def test_disconnect_defaults_to_a_no_op() -> None:
    class _Minimal(ConnectorLifecycle):
        def connect(self) -> None:
            pass

        def health_check(self) -> ConnectorHealth:
            return ConnectorHealth(healthy=True)

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

    connector = _Tracking(_manifest())
    connector.initialize()
    connector.connect()
    connector.health_check()
    connector.disconnect()

    assert calls == ["initialize", "connect", "health_check", "disconnect"]


def test_health_check_result_is_frozen() -> None:
    health = ConnectorHealth(healthy=True, detail="ok")
    with pytest.raises(ValidationError):
        health.healthy = False
