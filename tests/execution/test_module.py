"""Tests for `ExecutionModule` (Sprint 6 Architecture Package §5, §6.2, §7.2)."""

from __future__ import annotations

from pathlib import Path

from integration import CAPABILITY_CONNECTOR_REGISTRY, IntegrationModule
from integration.registry import ConnectorRegistry
from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.registry.plugin_registry import PluginRegistry

from execution.engine import ExecutionEngine
from execution.module import CAPABILITY_EXECUTION_ENGINE, ExecutionModule

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="execution",
        display_name="Execution",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_EXECUTION_ENGINE,),
        capabilities_required=(CAPABILITY_CONNECTOR_REGISTRY,),
        entry_point="module:create",
    )


def _container_with_registry(registry: ConnectorRegistry) -> Container:
    container = Container()
    container.register(CAPABILITY_CONNECTOR_REGISTRY, lambda: registry)
    return container


def test_execution_module_is_a_module() -> None:
    module = ExecutionModule(_manifest())
    assert isinstance(module, Module)


def test_execution_module_has_no_engine_before_init() -> None:
    module = ExecutionModule(_manifest())
    assert module.engine is None


def test_health_check_is_healthy_before_init() -> None:
    module = ExecutionModule(_manifest())
    assert module.health_check().healthy is True


def test_init_resolves_the_connector_registry_and_builds_an_execution_engine() -> None:
    registry = ConnectorRegistry()
    module = ExecutionModule(_manifest())

    module.init(_container_with_registry(registry))

    assert isinstance(module.engine, ExecutionEngine)


def test_init_registers_the_execution_engine_capability() -> None:
    registry = ConnectorRegistry()
    module = ExecutionModule(_manifest())
    container = _container_with_registry(registry)

    module.init(container)
    resolved = container.resolve(CAPABILITY_EXECUTION_ENGINE)

    assert resolved is module.engine


def test_health_check_is_healthy_after_init() -> None:
    registry = ConnectorRegistry()
    module = ExecutionModule(_manifest())
    module.init(_container_with_registry(registry))

    assert module.health_check().healthy is True


def test_execution_module_manifest_requires_only_connector_registry() -> None:
    assert _manifest().capabilities_required == (CAPABILITY_CONNECTOR_REGISTRY,)


def test_execution_module_never_imports_planning() -> None:
    # Execution depends on Planning's frozen contract *types* only, never
    # on Planning as a live capability (Sprint 5 Architecture Package §6,
    # restated at Sprint 6 Architecture Package §17 item 3).
    import execution.module as module_source

    assert not hasattr(module_source, "planning")


def test_execution_module_constructs_no_execution_context() -> None:
    # ExecutionModule owns only the ExecutionEngine -- ExecutionContext
    # stays a per-call concern outside any module's own boundary (§6.2).
    import ast

    source = Path(__file__).resolve().parents[2] / "execution" / "module.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "ExecutionContext" not in calls


# -- End-to-end: discovered and booted through the real top-level PluginRegistry --


def test_execution_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("execution")

    assert plugin is not None
    assert plugin.manifest.capabilities_provided == (CAPABILITY_EXECUTION_ENGINE,)
    assert plugin.manifest.capabilities_required == (CAPABILITY_CONNECTOR_REGISTRY,)


def test_execution_module_passes_dependency_validation_alongside_integration() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_execution_module_depends_on_integration_in_dependency_order() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert order.index("integration") < order.index("execution")


def test_execution_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    integration_instance = registry.instantiate("integration")
    integration_instance.validate()
    integration_instance.init(container)
    assert isinstance(integration_instance, IntegrationModule)

    execution_instance = registry.instantiate("execution")
    execution_instance.validate()
    execution_instance.init(container)
    health = execution_instance.health_check()

    assert isinstance(execution_instance, ExecutionModule)
    assert health.healthy is True
    assert container.resolve(CAPABILITY_EXECUTION_ENGINE) is execution_instance.engine


def test_execution_engines_registry_is_the_same_object_integration_provides_after_a_real_boot(
    config_dir: Path,
) -> None:
    # The concrete, direct proof that Phase 1's ADR Candidate A fix is
    # what makes this correct: pre-fix, integration.connector_registry
    # would resolve to the IntegrationModule instance instead of the real
    # ConnectorRegistry, and this assertion would fail.
    import yaml
    from runtime.boot import Runtime

    modules_dir = config_dir / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    for module_id in ("extractor", "validator"):
        (modules_dir / f"{module_id}.yaml").write_text(yaml.safe_dump({"enabled": False}), encoding="utf-8")

    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[_PLUGINS_DIR])
    info = runtime.boot()

    assert info.state.value == "ready"
    engine = runtime.container.resolve(CAPABILITY_EXECUTION_ENGINE)
    registry = runtime.container.resolve(CAPABILITY_CONNECTOR_REGISTRY)
    assert isinstance(engine, ExecutionEngine)
    assert engine._retry_policy._registry is registry

    runtime.shutdown()
