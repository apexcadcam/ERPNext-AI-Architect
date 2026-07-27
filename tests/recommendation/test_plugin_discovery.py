"""End-to-end: Recommendation Engine discovered and booted through the
real, top-level `PluginRegistry`, alongside Repository Discovery,
Requirement Synthesis, and Architecture Evaluation (Recommendation Engine
Architecture Specification v1.0's own Commit 7)."""

from __future__ import annotations

from pathlib import Path

from runtime.container.di import Container
from runtime.registry.plugin_registry import PluginRegistry

from recommendation.module import (
    CAPABILITY_ASSEMBLE_RECOMMENDATION_SET,
    CAPABILITY_BUILD_RECOMMENDATIONS,
    CAPABILITY_GROUP_FINDINGS,
    RecommendationModule,
)

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"

_ALL_CAPABILITIES = {
    CAPABILITY_GROUP_FINDINGS,
    CAPABILITY_BUILD_RECOMMENDATIONS,
    CAPABILITY_ASSEMBLE_RECOMMENDATION_SET,
}


def test_recommendation_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("recommendation")

    assert plugin is not None
    assert set(plugin.manifest.capabilities_provided) == _ALL_CAPABILITIES
    assert plugin.manifest.capabilities_required == ()


def test_recommendation_module_passes_dependency_validation_alongside_every_other_plugin() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_recommendation_module_requires_nothing_so_has_no_forced_boot_order_dependency() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert "recommendation" in order


def test_recommendation_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    instance = registry.instantiate("recommendation")
    instance.validate()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, RecommendationModule)
    assert health.healthy is True
    assert container.is_registered(CAPABILITY_GROUP_FINDINGS)
