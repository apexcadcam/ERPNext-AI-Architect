"""End-to-end: Repository Discovery discovered and booted through the real,
top-level `PluginRegistry` (Repository Discovery Engine Specification
v1.1 §2, §8's Commit 6)."""

from __future__ import annotations

from pathlib import Path

from runtime.container.di import Container
from runtime.registry.plugin_registry import PluginRegistry

from discovery.module import (
    CAPABILITY_ASSEMBLE_INVENTORY,
    CAPABILITY_CLASSIFY_ENTRIES,
    CAPABILITY_RESOLVE_ROOT,
    CAPABILITY_WALK_TREE,
    DiscoveryModule,
)

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def test_discovery_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("discovery")

    assert plugin is not None
    assert set(plugin.manifest.capabilities_provided) == {
        CAPABILITY_RESOLVE_ROOT,
        CAPABILITY_WALK_TREE,
        CAPABILITY_CLASSIFY_ENTRIES,
        CAPABILITY_ASSEMBLE_INVENTORY,
    }
    assert plugin.manifest.capabilities_required == ()


def test_discovery_module_passes_dependency_validation_alongside_every_other_plugin() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_discovery_module_requires_nothing_so_has_no_forced_boot_order_dependency() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert "discovery" in order


def test_discovery_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    instance = registry.instantiate("discovery")
    instance.validate()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, DiscoveryModule)
    assert health.healthy is True
    assert container.is_registered(CAPABILITY_RESOLVE_ROOT)
