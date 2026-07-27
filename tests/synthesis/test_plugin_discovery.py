"""End-to-end: Requirement Synthesis discovered and booted through the
real, top-level `PluginRegistry`, alongside Repository Discovery
(Requirement Synthesis Engine Specification v1.1 §2, §9's Commit 6)."""

from __future__ import annotations

from pathlib import Path

from runtime.container.di import Container
from runtime.registry.plugin_registry import PluginRegistry

from synthesis.module import (
    CAPABILITY_ASSEMBLE_FACTS,
    CAPABILITY_EXTRACT_APIS,
    CAPABILITY_EXTRACT_COMPONENTS,
    CAPABILITY_EXTRACT_DEPENDENCIES,
    CAPABILITY_EXTRACT_HOOKS,
    CAPABILITY_IDENTIFY_MODULES,
    CAPABILITY_PARTITION_INVENTORY,
    CAPABILITY_RESOLVE_CONNECTOR,
    SynthesisModule,
)

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"

_ALL_CAPABILITIES = {
    CAPABILITY_PARTITION_INVENTORY,
    CAPABILITY_IDENTIFY_MODULES,
    CAPABILITY_RESOLVE_CONNECTOR,
    CAPABILITY_EXTRACT_HOOKS,
    CAPABILITY_EXTRACT_COMPONENTS,
    CAPABILITY_EXTRACT_APIS,
    CAPABILITY_EXTRACT_DEPENDENCIES,
    CAPABILITY_ASSEMBLE_FACTS,
}


def test_synthesis_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("synthesis")

    assert plugin is not None
    assert set(plugin.manifest.capabilities_provided) == _ALL_CAPABILITIES
    assert plugin.manifest.capabilities_required == ()


def test_synthesis_module_passes_dependency_validation_alongside_every_other_plugin() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_synthesis_module_requires_nothing_so_has_no_forced_boot_order_dependency() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert "synthesis" in order


def test_synthesis_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    instance = registry.instantiate("synthesis")
    instance.validate()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, SynthesisModule)
    assert health.healthy is True
    assert container.is_registered(CAPABILITY_PARTITION_INVENTORY)
