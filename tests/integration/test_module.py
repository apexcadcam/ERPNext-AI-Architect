"""Tests for `IntegrationModule` (SPRINT3_ARCHITECTURE_PACKAGE.md §5.1, §11.1)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from integration import CAPABILITY_CONNECTOR_REGISTRY, ConnectorRegistry, IntegrationModule
from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.registry.plugin_registry import PluginRegistry

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="integration",
        display_name="Integration",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_CONNECTOR_REGISTRY,),
        entry_point="module:create",
    )


def test_integration_module_is_a_module() -> None:
    module = IntegrationModule(_manifest())
    assert isinstance(module, Module)


def test_integration_module_starts_with_its_own_empty_connector_registry() -> None:
    module = IntegrationModule(_manifest())
    assert isinstance(module.registry, ConnectorRegistry)
    assert module.registry.all_connectors() == ()


def test_no_connectors_configured_is_a_valid_ready_state(make_connector: Callable[..., Path]) -> None:
    # "No actual connectors" is this phase's own scope — an
    # IntegrationModule with connector_search_paths == [] (the default)
    # must boot cleanly, not fail for having nothing to discover.
    module = IntegrationModule(_manifest())
    container = Container()

    module.init(container)

    assert module.registry.all_connectors() == ()
    assert module.health_check().healthy is True


def test_init_discovers_and_registers_configured_connectors(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    module = IntegrationModule(_manifest())
    module.connector_search_paths = [connectors_dir]
    container = Container()

    module.init(container)

    assert module.registry.get("erpnext") is not None


def test_init_registers_the_connector_registry_capability(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    module = IntegrationModule(_manifest())
    module.connector_search_paths = [connectors_dir]
    container = Container()

    module.init(container)
    resolved = container.resolve(CAPABILITY_CONNECTOR_REGISTRY)

    assert resolved is module.registry


def test_health_check_reports_the_registered_connector_count(
    make_connector: Callable[..., Path], connectors_dir: Path
) -> None:
    make_connector("erpnext")
    make_connector("github")
    module = IntegrationModule(_manifest())
    module.connector_search_paths = [connectors_dir]
    module.init(Container())

    health = module.health_check()

    assert health.healthy is True
    assert "2" in health.detail


def test_integration_module_never_imports_a_concrete_connector_module() -> None:
    # A structural guarantee, not just a convention: integration/module.py
    # has no import of anything ERPNext/GitHub/Docker/MCP-specific — the
    # only way a concrete connector's code ever runs is through
    # ConnectorRegistry.instantiate()'s dynamic import, exercised in
    # test_registry.py, never a static import anywhere in this package.
    import integration.module as module_source

    assert not hasattr(module_source, "erpnext")
    assert not hasattr(module_source, "github")


# -- End-to-end: discovered and booted through the real top-level PluginRegistry --


def test_integration_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("integration")

    assert plugin is not None
    assert plugin.manifest.capabilities_provided == (CAPABILITY_CONNECTOR_REGISTRY,)


def test_integration_module_passes_dependency_validation_alongside_other_modules() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_integration_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    instance = registry.instantiate("integration")
    instance.validate()
    container = Container()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, IntegrationModule)
    assert health.healthy is True
    assert container.resolve(CAPABILITY_CONNECTOR_REGISTRY) is instance.registry
