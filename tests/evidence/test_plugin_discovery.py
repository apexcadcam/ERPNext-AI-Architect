"""End-to-end: Evidence Extraction discovered and booted through the real,
top-level `PluginRegistry`, alongside every other registered plugin
(Evidence Extraction Engine Architecture Specification v1.1's own
Commit 8)."""

from __future__ import annotations

from pathlib import Path

from runtime.container.di import Container
from runtime.registry.plugin_registry import PluginRegistry

from evidence.module import CAPABILITY_EXTRACT_EVIDENCE, EvidenceModule

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"

_ALL_CAPABILITIES = {CAPABILITY_EXTRACT_EVIDENCE}


def test_evidence_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("evidence")

    assert plugin is not None
    assert set(plugin.manifest.capabilities_provided) == _ALL_CAPABILITIES
    assert plugin.manifest.capabilities_required == ()


def test_evidence_module_passes_dependency_validation_alongside_every_other_plugin() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_evidence_module_requires_nothing_so_has_no_forced_boot_order_dependency() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert "evidence" in order


def test_evidence_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    instance = registry.instantiate("evidence")
    instance.validate()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, EvidenceModule)
    assert health.healthy is True
    assert container.is_registered(CAPABILITY_EXTRACT_EVIDENCE)


def test_registering_evidence_does_not_disturb_the_existing_repository_intelligence_plugins() -> None:
    # Backward compatibility: the four Repository Intelligence plugins
    # must still discover, validate, and order exactly as before.
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    for module_id in ("discovery", "synthesis", "evaluation", "recommendation"):
        assert registry.get(module_id) is not None
        assert module_id in order
