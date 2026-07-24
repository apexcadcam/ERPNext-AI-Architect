"""Tests for `ConnectorInvoker`/`RegistryConnectorInvoker`
(Sprint 5 Architecture Package §9.3), exercised against the real
`ConnectorRegistry` and the real Filesystem Connector (Sprint 3/5 Phase 1)
— no fakes, per the Sprint 5 Implementation Plan's own validation strategy
for this phase.
"""

from __future__ import annotations

from pathlib import Path

from integration.registry import ConnectorRegistry, DiscoveredConnector

from execution.connector_invoker import ConnectorInvoker, RegistryConnectorInvoker

_CONNECTORS_DIR = Path(__file__).resolve().parents[2] / "integration" / "connectors"


def _registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([_CONNECTORS_DIR]))
    registry.validate()
    return registry


def _registry_rooted_at(tmp_path: Path) -> ConnectorRegistry:
    """A registry identical to `_registry()`, except the real Filesystem
    connector's `endpoint_reference` is repointed at `tmp_path` — built
    entirely through `ConnectorRegistry`'s own public API (`discover()`
    returns a plain list of `DiscoveredConnector`, freely modifiable
    before `register_all()`), no private internals touched.
    """

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


def test_registry_connector_invoker_is_a_connector_invoker() -> None:
    assert isinstance(RegistryConnectorInvoker(_registry()), ConnectorInvoker)


def test_is_available_true_for_a_real_capability() -> None:
    invoker = RegistryConnectorInvoker(_registry())
    assert invoker.is_available("filesystem.read_text") is True


def test_is_available_false_for_an_unknown_capability() -> None:
    invoker = RegistryConnectorInvoker(_registry())
    assert invoker.is_available("erpnext.write_record") is False


def test_invoke_read_text_against_the_real_filesystem_connector(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    invoker = RegistryConnectorInvoker(_registry_rooted_at(tmp_path))

    response = invoker.invoke(
        "filesystem.read_text", {"path": "hello.txt"}, correlation_id="corr-1", requested_by="test-suite"
    )

    assert response.status == "success"
    assert response.result == {"content": "hi"}


def test_invoke_write_text_against_the_real_filesystem_connector(tmp_path: Path) -> None:
    invoker = RegistryConnectorInvoker(_registry_rooted_at(tmp_path))

    response = invoker.invoke(
        "filesystem.write_text",
        {"path": "new.txt", "content": "hello"},
        correlation_id="corr-1",
        requested_by="test-suite",
    )

    assert response.status == "success"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hello"


def test_invoke_unknown_capability_returns_failure_not_raise() -> None:
    invoker = RegistryConnectorInvoker(_registry())

    response = invoker.invoke("erpnext.write_record", {}, correlation_id="corr-1", requested_by="test-suite")

    assert response.status == "failure"
    assert "no registered connector" in response.diagnostics


def test_invoke_reuses_the_same_connected_instance_across_calls(tmp_path: Path) -> None:
    invoker = RegistryConnectorInvoker(_registry_rooted_at(tmp_path))

    invoker.invoke("filesystem.exists", {"path": "a"}, correlation_id="corr-1", requested_by="test-suite")
    first_instance = invoker._connected["filesystem"]  # accessing the cache directly to verify reuse
    invoker.invoke("filesystem.exists", {"path": "b"}, correlation_id="corr-2", requested_by="test-suite")
    second_instance = invoker._connected["filesystem"]

    assert first_instance is second_instance
