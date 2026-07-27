"""End-to-end: Architecture Evaluation discovered and booted through the
real, top-level `PluginRegistry`, alongside Repository Discovery and
Requirement Synthesis (Architecture Evaluation Engine Specification v1.0
§2, §9's Commit 7)."""

from __future__ import annotations

from pathlib import Path

from runtime.container.di import Container
from runtime.registry.plugin_registry import PluginRegistry

from evaluation.module import (
    CAPABILITY_ASSEMBLE_EVALUATION,
    CAPABILITY_EXECUTE_RULES,
    CAPABILITY_INDEX_FACTS,
    EvaluationModule,
)

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"

_ALL_CAPABILITIES = {CAPABILITY_INDEX_FACTS, CAPABILITY_EXECUTE_RULES, CAPABILITY_ASSEMBLE_EVALUATION}


def test_evaluation_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("evaluation")

    assert plugin is not None
    assert set(plugin.manifest.capabilities_provided) == _ALL_CAPABILITIES
    assert plugin.manifest.capabilities_required == ()


def test_evaluation_module_passes_dependency_validation_alongside_every_other_plugin() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_evaluation_module_requires_nothing_so_has_no_forced_boot_order_dependency() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert "evaluation" in order


def test_evaluation_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    instance = registry.instantiate("evaluation")
    instance.validate()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, EvaluationModule)
    assert health.healthy is True
    assert container.is_registered(CAPABILITY_INDEX_FACTS)
