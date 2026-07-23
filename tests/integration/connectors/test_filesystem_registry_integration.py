"""End-to-end: the real `integration/connectors/filesystem/` directory,
discovered, registered, validated, and instantiated through the real
`ConnectorRegistry` — mirroring `tests/integration/test_module.py`'s
"discovered and booted through the real ... Registry" pattern, one level
down, for the first concrete connector.
"""

from __future__ import annotations

from pathlib import Path

from integration.contract import ConnectorManifest
from integration.lifecycle import ConnectorLifecycle
from integration.registry import ConnectorRegistry

_CONNECTORS_DIR = Path(__file__).resolve().parents[3] / "integration" / "connectors"


def test_discovers_the_real_filesystem_connector() -> None:
    registry = ConnectorRegistry()
    found = registry.discover([_CONNECTORS_DIR])

    assert [connector.manifest.connector_id for connector in found] == ["filesystem"]


def test_registers_and_validates_cleanly() -> None:
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([_CONNECTORS_DIR]))

    report = registry.validate()

    assert report.ok
    assert registry.validated


def test_capability_providers_resolve_to_the_filesystem_connector() -> None:
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([_CONNECTORS_DIR]))

    for capability in (
        "filesystem.read_text",
        "filesystem.write_text",
        "filesystem.exists",
        "filesystem.list_directory",
    ):
        assert registry.capability_providers(capability) == ("filesystem",)


def test_all_provided_capabilities_matches_the_manifest() -> None:
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([_CONNECTORS_DIR]))

    assert registry.all_provided_capabilities() == frozenset(
        {
            "filesystem.read_text",
            "filesystem.write_text",
            "filesystem.exists",
            "filesystem.list_directory",
        }
    )


def test_instantiate_dynamically_loads_the_real_connector_module() -> None:
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([_CONNECTORS_DIR]))

    instance = registry.instantiate("filesystem")

    # instantiate() dynamically loads connector.py under its own module
    # name (registry.py's own documented discipline), so the resulting
    # class is a distinct object from anything statically imported for
    # this test — isinstance(..., ConnectorLifecycle) plus the class name
    # is the correct way to assert this, not identity with a statically
    # imported FilesystemConnector.
    assert isinstance(instance, ConnectorLifecycle)
    assert type(instance).__name__ == "FilesystemConnector"
    assert isinstance(instance.manifest, ConnectorManifest)
    assert instance.manifest.connector_id == "filesystem"


def test_instantiated_connector_completes_a_full_lifecycle_sequence() -> None:
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([_CONNECTORS_DIR]))
    instance = registry.instantiate("filesystem")

    instance.initialize()
    instance.connect()  # endpoint_reference "." always resolves to an existing directory
    health = instance.health_check()
    instance.disconnect()

    assert health.healthy is True
