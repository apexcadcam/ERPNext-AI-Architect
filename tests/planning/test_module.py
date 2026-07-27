"""Tests for `PlanningModule` (Sprint 6 Architecture Package §5, §6.1, §7.1;
Sprint 12 Phase 2 config-driven strategy selection).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml
from knowledge.graph import InMemoryGraphStore
from runtime.config.loader import ConfigLoader
from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.registry.plugin_registry import PluginRegistry

from planning.contract import CapabilityDescriptor, Goal, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.module import (
    _CONFIG_KEY_STRATEGY_NAME,
    _DEFAULT_STRATEGY_NAME,
    _INTELLIGENCE_AWARE_STRATEGY_NAME,
    _STRATEGY_FACTORIES,
    CAPABILITY_PLANNING_ENGINE,
    PlanningModule,
)
from planning.validation import validate_plan

from intelligence.contract import TradeoffAssessment

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"
_CREATED_AT = "2026-01-01T00:00:00Z"


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


# == Sprint 12, Phase 2 — configuration-driven strategy selection =================================


class _FixedResolvedConfigLoader:
    """A minimal fake standing in for `ConfigLoader`, exposing only the one
    method `PlanningModule.init()` actually calls — mirrors
    `tests/intelligence/test_module.py`'s own identical fixture, proving
    this module depends on `resolve()`'s shape, not on `ConfigLoader` as a
    concrete class.
    """

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def resolve(self, *, module_id: str, strict: bool) -> _FixedResolvedConfigLoader:
        return self

    def get(self, key: str, default: str) -> str:
        return self._values.get(key, default)


def _fixed_config_loader_provider(strategy_name: str) -> Callable[[], _FixedResolvedConfigLoader]:
    def _provide() -> _FixedResolvedConfigLoader:
        return _FixedResolvedConfigLoader({_CONFIG_KEY_STRATEGY_NAME: strategy_name})

    return _provide


def _goal_and_context() -> tuple[Goal, PlanningContext]:
    goal = Goal(goal_id="G-1", intent="x")
    context = PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(
            CapabilityDescriptor(
                capability="WF-1", kind="read", idempotent=True, requires_confirmation=False
            ),
        ),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )
    return goal, context


def _tradeoff_assessment() -> TradeoffAssessment:
    return TradeoffAssessment(ranked_candidate_ids=("WF-1",), rationale="scripted", cited_evidence_ids=())


# -- Default strategy selection --------------------------------------------------------------------


def test_default_strategy_selection_with_no_runtime_config_registered() -> None:
    module = PlanningModule(_manifest())
    module.init(Container())

    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


def test_explicit_rule_based_configuration_selects_rule_based() -> None:
    module = PlanningModule(_manifest())
    container = Container()
    container.register("runtime.config", _fixed_config_loader_provider(_DEFAULT_STRATEGY_NAME))

    module.init(container)
    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


def test_configuration_key_absent_falls_back_to_rule_based(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    (config_dir / "modules").mkdir(parents=True)
    (config_dir / "modules" / "planning.yaml").write_text(yaml.safe_dump({}), encoding="utf-8")
    container = Container()
    container.register("runtime.config", lambda: ConfigLoader(config_dir))
    module = PlanningModule(_manifest())

    module.init(container)
    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


# -- IntelligenceAware strategy selection -----------------------------------------------------------


def test_intelligence_aware_configuration_with_supplied_data_selects_intelligence_aware(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    (config_dir / "modules").mkdir(parents=True)
    (config_dir / "modules" / "planning.yaml").write_text(
        yaml.safe_dump({_CONFIG_KEY_STRATEGY_NAME: _INTELLIGENCE_AWARE_STRATEGY_NAME}), encoding="utf-8"
    )
    container = Container()
    container.register("runtime.config", lambda: ConfigLoader(config_dir))
    module = PlanningModule(_manifest(), tradeoff_assessment=_tradeoff_assessment(), created_at=_CREATED_AT)

    module.init(container)
    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "intelligence_aware"
    assert plan.created_at == _CREATED_AT


def test_intelligence_aware_configuration_without_supplied_data_falls_back_to_rule_based() -> None:
    # Configuration alone cannot select IntelligenceAware -- the caller
    # must also have supplied real data via the constructor. This is the
    # "never a boot-blocking error" fallback, not a silent contradiction.
    module = PlanningModule(_manifest())  # no tradeoff_assessment/created_at supplied
    container = Container()
    container.register("runtime.config", _fixed_config_loader_provider(_INTELLIGENCE_AWARE_STRATEGY_NAME))

    module.init(container)
    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


def test_supplying_data_alone_without_configuration_does_not_select_intelligence_aware() -> None:
    # The reverse of the above: supplying real data through the
    # constructor does not, by itself, select IntelligenceAware --
    # configuration is what decides.
    module = PlanningModule(_manifest(), tradeoff_assessment=_tradeoff_assessment(), created_at=_CREATED_AT)
    module.init(Container())  # no "runtime.config" registered at all

    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


# -- Invalid strategy configuration ------------------------------------------------------------------


def test_unrecognized_strategy_configuration_falls_back_to_rule_based() -> None:
    module = PlanningModule(_manifest())
    container = Container()
    container.register("runtime.config", _fixed_config_loader_provider("some-future-strategy-not-yet-built"))

    module.init(container)
    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


def test_empty_string_strategy_configuration_falls_back_to_rule_based() -> None:
    module = PlanningModule(_manifest())
    container = Container()
    container.register("runtime.config", _fixed_config_loader_provider(""))

    module.init(container)
    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


# -- Backwards compatibility -------------------------------------------------------------------------


def test_construction_without_the_new_keyword_arguments_still_works() -> None:
    # Exactly the pre-Phase-2 call shape -- plugins/planning/module.py's
    # own create(manifest) never changed and must keep working unmodified.
    module = PlanningModule(_manifest())
    module.init(Container())

    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert plan.strategy_name == "rule_based"


def test_only_rule_based_is_a_zero_argument_factory() -> None:
    assert set(_STRATEGY_FACTORIES) == {"rule_based"}


# -- Dependency injection behavior ----------------------------------------------------------------------


def test_the_supplied_tradeoff_assessment_is_injected_verbatim_not_reconstructed() -> None:
    assessment = _tradeoff_assessment()
    module = PlanningModule(_manifest(), tradeoff_assessment=assessment, created_at=_CREATED_AT)

    assert module._tradeoff_assessment is assessment


def test_the_supplied_rationale_reaches_the_produced_plan() -> None:
    assessment = TradeoffAssessment(
        ranked_candidate_ids=("WF-1",), rationale="a specific, distinctive rationale", cited_evidence_ids=()
    )
    module = PlanningModule(_manifest(), tradeoff_assessment=assessment, created_at=_CREATED_AT)
    container = Container()
    container.register("runtime.config", _fixed_config_loader_provider(_INTELLIGENCE_AWARE_STRATEGY_NAME))
    module.init(container)

    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)

    assert "a specific, distinctive rationale" in plan.steps[0].rationale


# -- PlanningEngine integration -----------------------------------------------------------------------


def test_resolved_engine_genuinely_creates_an_intelligence_aware_plan_through_the_container() -> None:
    module = PlanningModule(_manifest(), tradeoff_assessment=_tradeoff_assessment(), created_at=_CREATED_AT)
    container = Container()
    container.register("runtime.config", _fixed_config_loader_provider(_INTELLIGENCE_AWARE_STRATEGY_NAME))
    module.init(container)
    engine = container.resolve(CAPABILITY_PLANNING_ENGINE)

    goal, context = _goal_and_context()
    plan = engine.create_plan(goal, context)

    assert plan.strategy_name == "intelligence_aware"
    assert [step.capability for step in plan.steps] == ["WF-1"]


# -- Deterministic repeated construction -----------------------------------------------------------------


def test_deterministic_repeated_construction_produces_identical_plans() -> None:
    assessment = _tradeoff_assessment()
    goal, context = _goal_and_context()

    first_module = PlanningModule(_manifest(), tradeoff_assessment=assessment, created_at=_CREATED_AT)
    first_container = Container()
    first_container.register(
        "runtime.config", _fixed_config_loader_provider(_INTELLIGENCE_AWARE_STRATEGY_NAME)
    )
    first_module.init(first_container)
    first_plan = first_module.engine.create_plan(goal, context)

    second_module = PlanningModule(_manifest(), tradeoff_assessment=assessment, created_at=_CREATED_AT)
    second_container = Container()
    second_container.register(
        "runtime.config", _fixed_config_loader_provider(_INTELLIGENCE_AWARE_STRATEGY_NAME)
    )
    second_module.init(second_container)
    second_plan = second_module.engine.create_plan(goal, context)

    assert first_plan == second_plan


# -- validate_plan behavior is unchanged -------------------------------------------------------------


def test_validate_plan_still_applies_normally_to_an_intelligence_aware_plan() -> None:
    module = PlanningModule(_manifest(), tradeoff_assessment=_tradeoff_assessment(), created_at=_CREATED_AT)
    container = Container()
    container.register("runtime.config", _fixed_config_loader_provider(_INTELLIGENCE_AWARE_STRATEGY_NAME))
    module.init(container)

    goal, context = _goal_and_context()
    plan = module.engine.create_plan(goal, context)  # PlanningEngine already calls validate_plan internally

    report = validate_plan(plan, context, raise_on_failure=False)
    assert report.ok


# -- Dependency boundaries ------------------------------------------------------------------------------


def test_planning_module_still_never_imports_knowledge_analysis_pipeline_or_bridge() -> None:
    import planning.module as module_source

    assert not hasattr(module_source, "knowledge")
    assert not hasattr(module_source, "analysis")
