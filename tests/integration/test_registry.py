"""Tests for the nested Connector Registry
(SPRINT3_ARCHITECTURE_PACKAGE.md §5.2, §5.4, §6.3, §11.1).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from integration import (
    ConnectorLifecycle,
    ConnectorLifecycleError,
    ConnectorManifestError,
    ConnectorRegistry,
    ConnectorValidationError,
)
from runtime.registry.plugin_registry import PluginRegistry

from tests.integration.conftest import RAISES_ON_IMPORT_CONNECTOR_PY, WRONG_RETURN_TYPE_CONNECTOR_PY


# -- Discovery -----------------------------------------------------------------


def test_discovery_of_empty_directory_returns_empty_list_not_an_error(connectors_dir: Path) -> None:
    registry = ConnectorRegistry()
    assert registry.discover([connectors_dir]) == []


def test_discovery_of_nonexistent_path_is_gracefully_skipped(tmp_path: Path) -> None:
    registry = ConnectorRegistry()
    assert registry.discover([tmp_path / "does_not_exist"]) == []


def test_discover_finds_a_valid_connector_manifest(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    registry = ConnectorRegistry()

    found = registry.discover([connectors_dir])

    assert [connector.manifest.connector_id for connector in found] == ["erpnext"]


def test_discover_does_not_register_anything(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    registry = ConnectorRegistry()

    registry.discover([connectors_dir])

    assert registry.all_connectors() == ()  # discover() alone never registers


# -- Registration ----------------------------------------------------------------


def test_register_all_makes_connectors_visible(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    make_connector("github")
    registry = ConnectorRegistry()

    registry.register_all(registry.discover([connectors_dir]))

    assert {connector.manifest.connector_id for connector in registry.all_connectors()} == {
        "erpnext",
        "github",
    }


def test_get_returns_none_for_an_unregistered_connector() -> None:
    registry = ConnectorRegistry()
    assert registry.get("nope") is None


def test_registering_the_same_connector_id_from_a_different_path_raises(
    make_connector: Callable[..., Path], connectors_dir: Path, tmp_path: Path
) -> None:
    make_connector("erpnext")
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    # A second, differently-located "erpnext" connector — same connector_id,
    # different directory — mirrors PluginRegistry's identical duplicate
    # module_id rejection.
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    make_connector_elsewhere = other_dir / "erpnext"
    make_connector_elsewhere.mkdir()
    (make_connector_elsewhere / "connector.yaml").write_text(
        (connectors_dir / "erpnext" / "connector.yaml").read_text()
    )
    (make_connector_elsewhere / "connector.py").write_text(
        (connectors_dir / "erpnext" / "connector.py").read_text()
    )

    with pytest.raises(ConnectorManifestError, match="duplicate connector_id"):
        registry.register_all(registry.discover([other_dir]))


# -- §5.4 Validation: ambiguous capability detection ------------------------------


def test_validate_passes_when_no_capability_is_duplicated(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector(
        "erpnext", operations=[{"name": "erpnext.read_record", "kind": "read", "idempotent": True}]
    )
    make_connector("github", operations=[{"name": "github.read_issue", "kind": "read", "idempotent": True}])
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    report = registry.validate()

    assert report.ok
    assert registry.validated


def test_validate_detects_a_capability_provided_by_two_connectors(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext-a", operations=[{"name": "read_record", "kind": "read", "idempotent": True}])
    make_connector("erpnext-b", operations=[{"name": "read_record", "kind": "read", "idempotent": True}])
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    with pytest.raises(ConnectorValidationError, match="read_record"):
        registry.validate()


def test_validate_raise_on_failure_false_returns_the_report_instead(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext-a", operations=[{"name": "read_record", "kind": "read", "idempotent": True}])
    make_connector("erpnext-b", operations=[{"name": "read_record", "kind": "read", "idempotent": True}])
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    report = registry.validate(raise_on_failure=False)

    assert not report.ok
    assert any("read_record" in issue for issue in report.ambiguous_capabilities)
    assert not registry.validated


def test_a_connector_with_no_operations_never_triggers_ambiguous_capability(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    make_connector("github")
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    report = registry.validate()

    assert report.ok


# -- §6.3 Capability Discovery -----------------------------------------------------


def test_capability_providers_lists_the_owning_connector(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector(
        "erpnext", operations=[{"name": "erpnext.read_record", "kind": "read", "idempotent": True}]
    )
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    assert registry.capability_providers("erpnext.read_record") == ("erpnext",)


def test_capability_providers_empty_for_an_unprovided_capability(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    assert registry.capability_providers("nothing.here") == ()


def test_all_provided_capabilities_aggregates_every_connector(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector(
        "erpnext", operations=[{"name": "erpnext.read_record", "kind": "read", "idempotent": True}]
    )
    make_connector("github", operations=[{"name": "github.read_issue", "kind": "read", "idempotent": True}])
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    assert registry.all_provided_capabilities() == {"erpnext.read_record", "github.read_issue"}


def test_the_registry_never_learns_a_concrete_connector_name_beyond_what_was_registered(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    # Capability discovery is a pure lookup over whatever was registered —
    # nothing in ConnectorRegistry hardcodes "erpnext"/"github"/"docker"/
    # "mcp" anywhere in its own implementation; asking about a system this
    # test never registered returns nothing, exactly like any other unknown
    # capability.
    make_connector(
        "erpnext", operations=[{"name": "erpnext.read_record", "kind": "read", "idempotent": True}]
    )
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    assert registry.capability_providers("docker.run_container") == ()
    assert registry.capability_providers("mcp.execute_tool") == ()


# -- Instantiation -----------------------------------------------------------------


def test_instantiate_dynamically_loads_and_constructs_the_connector(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    instance = registry.instantiate("erpnext")

    assert isinstance(instance, ConnectorLifecycle)
    assert instance.manifest.connector_id == "erpnext"


def test_instantiate_unknown_connector_raises() -> None:
    registry = ConnectorRegistry()
    with pytest.raises(ConnectorManifestError):
        registry.instantiate("nope")


def test_instantiate_wrong_return_type_raises(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext", connector_py=WRONG_RETURN_TYPE_CONNECTOR_PY)
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    with pytest.raises(ConnectorManifestError, match="not a ConnectorLifecycle"):
        registry.instantiate("erpnext")


def test_instantiate_entry_point_raising_on_import_is_reported(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext", connector_py=RAISES_ON_IMPORT_CONNECTOR_PY)
    registry = ConnectorRegistry()
    registry.register_all(registry.discover([connectors_dir]))

    with pytest.raises(ConnectorLifecycleError):
        registry.instantiate("erpnext")


# -- Registry isolation ------------------------------------------------------------


def test_two_registries_never_share_state(make_connector: Callable[..., Path], connectors_dir: Path) -> None:
    make_connector("erpnext")
    first = ConnectorRegistry()
    second = ConnectorRegistry()

    first.register_all(first.discover([connectors_dir]))

    assert first.all_connectors() != ()
    assert second.all_connectors() == ()


def test_connector_registry_is_invisible_to_the_top_level_plugin_registry(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    # §11.1: the nested Connector Registry is "invisible to the Runtime's
    # own Plugin Registry, which only ever sees one entry" — proven here by
    # the fact that discovering/registering connectors never touches, and
    # is never visible through, an unrelated PluginRegistry instance.
    make_connector("erpnext")
    connector_registry = ConnectorRegistry()
    connector_registry.register_all(connector_registry.discover([connectors_dir]))

    plugin_registry = PluginRegistry()

    assert plugin_registry.all_plugins() == ()
    assert plugin_registry.get("erpnext") is None
