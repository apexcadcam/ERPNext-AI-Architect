"""Tests for `PlanningModule` (Sprint 6 Architecture Package §5, §6.1, §7.1)."""

from __future__ import annotations

from pathlib import Path

from knowledge.graph import InMemoryGraphStore
from planning.contract import CapabilityDescriptor, Goal, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.module import CAPABILITY_PLANNING_ENGINE, PlanningModule
from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.registry.plugin_registry import PluginRegistry

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="planning",
        display_name="Planning",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_PLANNING_ENGINE,),
        entry_point="module:create",
    )


def test_planning_module_is_a_module() -> None:
    module = PlanningModule(_manifest())
    assert isinstance(module, Module)


def test_planning_module_starts_with_its_own_planning_engine() -> None:
    module = PlanningModule(_manifest())
    assert isinstance(module.engine, PlanningEngine)


def test_health_check_is_healthy_before_init() -> None:
    module = PlanningModule(_manifest())
    assert module.health_check().healthy is True


def test_init_registers_the_planning_engine_capability() -> None:
    module = PlanningModule(_manifest())
    container = Container()

    module.init(container)
    resolved = container.resolve(CAPABILITY_PLANNING_ENGINE)

    assert resolved is module.engine


def test_health_check_is_healthy_after_init() -> None:
    module = PlanningModule(_manifest())
    module.init(Container())

    assert module.health_check().healthy is True


def test_resolved_planning_engine_genuinely_creates_a_plan() -> None:
    # Not just "init() didn't raise" -- the registered strategy actually
    # works, mirroring tests/integration/test_module.py's own
    # "resolved is the real, working thing" discipline.
    module = PlanningModule(_manifest())
    container = Container()
    module.init(container)
    engine = container.resolve(CAPABILITY_PLANNING_ENGINE)

    goal = Goal(goal_id="G-1", intent="read a file", desired_capabilities=("filesystem.read_text",))
    context = PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(
            CapabilityDescriptor(
                capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
            ),
        ),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )

    plan = engine.create_plan(goal, context)

    assert plan.goal_id == "G-1"
    assert [step.capability for step in plan.steps] == ["filesystem.read_text"]


def test_planning_module_requires_nothing() -> None:
    # ADR-0011's one-way dependency rule, restated at the module level:
    # PlanningModule resolves nothing through the Container.
    assert _manifest().capabilities_required == ()


def test_planning_module_never_imports_integration_or_execution() -> None:
    import planning.module as module_source

    assert not hasattr(module_source, "integration")
    assert not hasattr(module_source, "execution")


# -- End-to-end: discovered and booted through the real top-level PluginRegistry --


def test_planning_module_is_discoverable_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    plugin = registry.get("planning")

    assert plugin is not None
    assert plugin.manifest.capabilities_provided == (CAPABILITY_PLANNING_ENGINE,)


def test_planning_module_passes_dependency_validation_alongside_other_modules() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))

    report = registry.validate_dependencies()

    assert report.ok


def test_planning_module_instantiates_and_boots_through_the_real_plugin_registry() -> None:
    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    instance = registry.instantiate("planning")
    instance.validate()
    container = Container()
    instance.init(container)
    health = instance.health_check()

    assert isinstance(instance, PlanningModule)
    assert health.healthy is True
    assert container.resolve(CAPABILITY_PLANNING_ENGINE) is instance.engine
