"""Tests for `OrchestrationModule` (Sprint 7 Architecture Package §3, §5 —
ADR Candidate A), Phase 3.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml
from execution.engine import ExecutionEngine
from execution.module import CAPABILITY_EXECUTION_ENGINE
from execution.retry import RetryPolicy
from integration import CAPABILITY_CONNECTOR_REGISTRY
from integration.registry import ConnectorRegistry
from planning.engine import PlanningEngine
from planning.module import CAPABILITY_PLANNING_ENGINE
from runtime.boot import Runtime
from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.registry.plugin_registry import PluginRegistry

from orchestration.module import CAPABILITY_GOAL_RUNNER, OrchestrationModule
from orchestration.orchestrator import GoalOrchestrator

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="orchestration",
        display_name="Orchestration",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_GOAL_RUNNER,),
        capabilities_required=(
            CAPABILITY_CONNECTOR_REGISTRY,
            CAPABILITY_PLANNING_ENGINE,
            CAPABILITY_EXECUTION_ENGINE,
        ),
        entry_point="module:create",
    )


def _fully_populated_container() -> Container:
    container = Container()
    container.register(CAPABILITY_CONNECTOR_REGISTRY, lambda: ConnectorRegistry())
    container.register(CAPABILITY_PLANNING_ENGINE, lambda: PlanningEngine())
    container.register(CAPABILITY_EXECUTION_ENGINE, lambda: ExecutionEngine(RetryPolicy(ConnectorRegistry())))
    return container


def test_orchestration_module_is_a_module() -> None:
    module = OrchestrationModule(_manifest())
    assert isinstance(module, Module)


def test_orchestration_module_has_no_orchestrator_before_init() -> None:
    module = OrchestrationModule(_manifest())
    assert module.orchestrator is None


def test_health_check_is_healthy_before_init() -> None:
    module = OrchestrationModule(_manifest())
    assert module.health_check().healthy is True


def test_init_resolves_all_three_and_builds_a_goal_orchestrator() -> None:
    module = OrchestrationModule(_manifest())

    module.init(_fully_populated_container())

    assert isinstance(module.orchestrator, GoalOrchestrator)


def test_init_registers_the_goal_runner_capability() -> None:
    module = OrchestrationModule(_manifest())
    container = _fully_populated_container()

    module.init(container)
    resolved = container.resolve(CAPABILITY_GOAL_RUNNER)

    assert resolved is module.orchestrator


def test_repeated_resolution_returns_the_same_orchestrator_instance() -> None:
    # Architecture Review's own non-blocking recommendation 2: the same
    # singleton-within-one-boot shape tests/execution/test_module.py
    # already proves for execution.engine, applied here to a module
    # resolving three upstream capabilities instead of one.
    module = OrchestrationModule(_manifest())
    container = _fully_populated_container()
    module.init(container)

    first = container.resolve(CAPABILITY_GOAL_RUNNER)
    second = container.resolve(CAPABILITY_GOAL_RUNNER)

    assert first is second
    assert first is module.orchestrator


def test_health_check_is_healthy_after_init() -> None:
    module = OrchestrationModule(_manifest())
    module.init(_fully_populated_container())

    assert module.health_check().healthy is True


def test_orchestration_module_manifest_requires_all_three_capabilities() -> None:
    assert _manifest().capabilities_required == (
        CAPABILITY_CONNECTOR_REGISTRY,
        CAPABILITY_PLANNING_ENGINE,
        CAPABILITY_EXECUTION_ENGINE,
    )


def test_orchestration_module_constructs_no_planning_or_execution_context() -> None:
    # OrchestrationModule owns only the GoalOrchestrator -- both Contexts
    # stay per-call concerns for whoever resolves orchestration.goal_runner
    # (Sprint 7 Architecture Package §3).
    source = Path(__file__).resolve().parents[2] / "orchestration" / "module.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "PlanningContext" not in calls
    assert "ExecutionContext" not in calls


# -- End-to-end: discovered and booted through the real top-level PluginRegistry --


def test_orchestration_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("orchestration")

    assert plugin is not None
    assert plugin.manifest.capabilities_provided == (CAPABILITY_GOAL_RUNNER,)
    assert plugin.manifest.capabilities_required == (
        CAPABILITY_CONNECTOR_REGISTRY,
        CAPABILITY_PLANNING_ENGINE,
        CAPABILITY_EXECUTION_ENGINE,
    )


def test_orchestration_module_passes_dependency_validation_alongside_the_others() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_orchestration_module_depends_on_all_three_providers_in_dependency_order() -> None:
    # The new, explicit three-precedes-one case named in the Sprint 7
    # Implementation Plan's own Phase 3 risk mitigation -- not assumed to
    # generalize from Sprint 6's own single/two-dependency tests.
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    order = registry.dependency_order()

    assert order.index("integration") < order.index("orchestration")
    assert order.index("planning") < order.index("orchestration")
    assert order.index("execution") < order.index("orchestration")


def test_orchestration_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()
    container = Container()

    for module_id in ("integration", "planning", "execution"):
        instance = registry.instantiate(module_id)
        instance.validate()
        instance.init(container)
        assert instance.health_check().healthy is True

    orchestration_instance = registry.instantiate("orchestration")
    orchestration_instance.validate()
    orchestration_instance.init(container)

    assert isinstance(orchestration_instance, OrchestrationModule)
    assert container.resolve(CAPABILITY_GOAL_RUNNER) is orchestration_instance.orchestrator


def test_real_boot_wires_orchestrator_to_the_same_engines_and_registry(config_dir: Path) -> None:
    modules_dir = config_dir / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    for module_id in ("extractor", "validator"):
        (modules_dir / f"{module_id}.yaml").write_text(yaml.safe_dump({"enabled": False}), encoding="utf-8")

    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[_PLUGINS_DIR])
    info = runtime.boot()

    assert info.state.value == "ready"
    orchestrator = runtime.container.resolve(CAPABILITY_GOAL_RUNNER)
    planning_engine = runtime.container.resolve(CAPABILITY_PLANNING_ENGINE)
    execution_engine = runtime.container.resolve(CAPABILITY_EXECUTION_ENGINE)
    assert isinstance(orchestrator, GoalOrchestrator)
    assert orchestrator._planning_engine is planning_engine
    assert orchestrator._execution_engine is execution_engine

    runtime.shutdown()
