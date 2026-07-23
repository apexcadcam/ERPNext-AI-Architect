"""Tests for the Plugin Registry (docs/runtime/PLUGIN_REGISTRY.md)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from runtime.errors import DependencyValidationError, ManifestError
from runtime.modules.base import Module
from runtime.registry.plugin_registry import PluginRegistry, _find_cycle


def test_discovery_of_empty_directory_returns_empty_list_not_an_error(plugins_dir: Path) -> None:
    registry = PluginRegistry()
    assert registry.discover([plugins_dir]) == []


def test_discovery_of_nonexistent_path_is_gracefully_skipped(tmp_path: Path) -> None:
    registry = PluginRegistry()
    assert registry.discover([tmp_path / "does_not_exist"]) == []


def test_discover_finds_a_valid_manifest(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("demo")
    registry = PluginRegistry()
    found = registry.discover([plugins_dir])
    assert [p.manifest.module_id for p in found] == ["demo"]


def test_register_then_enabled_plugins_reflects_enabled_by_default(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("on", enabled_by_default=True)
    make_plugin("off", enabled_by_default=False)
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    enabled_ids = {p.manifest.module_id for p in registry.enabled_plugins()}
    assert enabled_ids == {"on"}


def test_set_enabled_overrides_the_manifest_default(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("demo", enabled_by_default=True)
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    registry.set_enabled("demo", False)
    assert registry.enabled_plugins() == ()


def test_validate_dependencies_passes_for_a_satisfied_graph(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("provider", capabilities_provided=["thing"])
    make_plugin("consumer", capabilities_required=["thing"])
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    report = registry.validate_dependencies()
    assert report.ok
    assert registry.validated


def test_validate_dependencies_reports_unsatisfied_requirement(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("consumer", capabilities_required=["thing"])
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    with pytest.raises(DependencyValidationError, match="thing"):
        registry.validate_dependencies()


def test_validate_dependencies_reports_ambiguous_capability(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("provider_a", capabilities_provided=["thing"])
    make_plugin("provider_b", capabilities_provided=["thing"])
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    report = registry.validate_dependencies(raise_on_failure=False)
    assert not report.ok
    assert any("thing" in issue for issue in report.ambiguous_capabilities)


def test_validate_dependencies_reports_a_cycle(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("a", capabilities_provided=["a.cap"], capabilities_required=["b.cap"])
    make_plugin("b", capabilities_provided=["b.cap"], capabilities_required=["a.cap"])
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    report = registry.validate_dependencies(raise_on_failure=False)
    assert not report.ok
    assert report.cycle is not None


def test_disabling_a_depended_upon_module_is_caught_by_revalidation(
    make_plugin: Callable[..., Path], plugins_dir: Path
) -> None:
    make_plugin("provider", capabilities_provided=["thing"])
    make_plugin("consumer", capabilities_required=["thing"])
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))
    registry.validate_dependencies()  # passes while provider is enabled

    registry.set_enabled("provider", False)
    with pytest.raises(DependencyValidationError):
        registry.validate_dependencies()


def test_dependency_order_places_providers_before_consumers(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("c", capabilities_required=["b.cap"])
    make_plugin("b", capabilities_provided=["b.cap"], capabilities_required=["a.cap"])
    make_plugin("a", capabilities_provided=["a.cap"])
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))
    registry.validate_dependencies()

    order = registry.dependency_order()
    assert order.index("a") < order.index("b") < order.index("c")


def test_capability_providers_lists_only_enabled_modules(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("provider", capabilities_provided=["thing"], enabled_by_default=False)
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    assert registry.capability_providers("thing") == ()
    registry.set_enabled("provider", True)
    assert registry.capability_providers("thing") == ("provider",)


def test_instantiate_dynamically_loads_and_constructs_the_module(
    make_plugin: Callable[..., Path], plugins_dir: Path
) -> None:
    make_plugin("demo")
    registry = PluginRegistry()
    registry.register_all(registry.discover([plugins_dir]))

    instance = registry.instantiate("demo")
    assert isinstance(instance, Module)
    assert instance.manifest.module_id == "demo"


def test_instantiate_unknown_module_raises(plugins_dir: Path) -> None:
    registry = PluginRegistry()
    with pytest.raises(ManifestError):
        registry.instantiate("nope")


def test_manifest_missing_required_field_raises_on_discovery(plugins_dir: Path) -> None:
    bad_dir = plugins_dir / "bad"
    bad_dir.mkdir()
    (bad_dir / "module.yaml").write_text("module_id: bad\n")  # missing required fields
    registry = PluginRegistry()
    with pytest.raises(ManifestError):
        registry.discover([plugins_dir])


def test_find_cycle_returns_none_for_acyclic_graph() -> None:
    assert _find_cycle({"a": {"b"}, "b": {"c"}, "c": set()}) is None


def test_find_cycle_returns_the_cycle_path() -> None:
    cycle = _find_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}})
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"a", "b", "c"}
