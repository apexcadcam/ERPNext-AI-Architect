"""End-to-end: Pattern Aggregation discovered and booted through the real,
top-level `PluginRegistry`, alongside every other registered plugin
(Pattern Aggregation Engine Architecture Specification v1.0's own
Commit 9)."""

from __future__ import annotations

from pathlib import Path

from runtime.container.di import Container
from runtime.registry.plugin_registry import PluginRegistry

from aggregation.module import CAPABILITY_AGGREGATE_PATTERNS, AggregationModule

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"

_ALL_CAPABILITIES = {CAPABILITY_AGGREGATE_PATTERNS}


def test_aggregation_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("aggregation")

    assert plugin is not None
    assert set(plugin.manifest.capabilities_provided) == _ALL_CAPABILITIES
    assert plugin.manifest.capabilities_required == ()


def test_aggregation_module_passes_dependency_validation_alongside_every_other_plugin() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_aggregation_module_requires_nothing_so_has_no_forced_boot_order_dependency() -> None:
    # The EvidenceSet arrives inside the AggregationRequest, read from
    # disk by the caller -- never resolved from the evidence module at
    # runtime. So consuming Evidence imposes no boot ordering.
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert "aggregation" in order


def test_aggregation_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    instance = registry.instantiate("aggregation")
    instance.validate()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, AggregationModule)
    assert health.healthy is True
    assert container.is_registered(CAPABILITY_AGGREGATE_PATTERNS)


def test_registering_aggregation_does_not_disturb_the_existing_plugins() -> None:
    # Backward compatibility: every previously-shipped plugin must still
    # discover, validate, and order exactly as before.
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    for module_id in ("discovery", "synthesis", "evaluation", "recommendation", "evidence"):
        assert registry.get(module_id) is not None, module_id
        assert module_id in order, module_id
