"""Tests for `IntelligenceModule` (Sprint 8 Implementation Plan, Phase 3).
Capability registration, config-driven engine selection, and the
"always wrapped" guarantee — no adapter tests (Phase 4's own scope).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml
from runtime.boot import Runtime
from runtime.config.loader import ConfigLoader
from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest

from intelligence.contract import Requirement
from intelligence.module import (
    CAPABILITY_INTELLIGENCE_ENGINE,
    _CONFIG_KEY_ENGINE_NAME,
    _DEFAULT_ENGINE_NAME,
    _ENGINE_FACTORIES,
    IntelligenceModule,
)
from intelligence.null_engine import NullIntelligenceEngine
from intelligence.validating import ValidatingIntelligenceEngine

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="intelligence",
        display_name="Intelligence",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_INTELLIGENCE_ENGINE,),
        entry_point="module:create",
    )


# -- Basic Module shape -----------------------------------------------------------------------


def test_intelligence_module_is_a_module() -> None:
    module = IntelligenceModule(_manifest())
    assert isinstance(module, Module)


def test_engine_is_none_before_init() -> None:
    module = IntelligenceModule(_manifest())
    assert module.engine is None


def test_health_check_is_healthy_before_init() -> None:
    module = IntelligenceModule(_manifest())
    assert module.health_check().healthy is True


def test_health_check_is_healthy_after_init() -> None:
    module = IntelligenceModule(_manifest())
    module.init(Container())
    assert module.health_check().healthy is True


def test_intelligence_module_requires_nothing() -> None:
    assert _manifest().capabilities_required == ()


def test_intelligence_module_never_imports_a_vendor_sdk_or_a_domain_package() -> None:
    import intelligence.module as module_source

    for forbidden in (
        "anthropic",
        "openai",
        "knowledge",
        "analysis",
        "planning",
        "execution",
        "orchestration",
    ):
        assert not hasattr(module_source, forbidden)


# -- Capability registration -------------------------------------------------------------------


def test_init_registers_the_intelligence_engine_capability() -> None:
    module = IntelligenceModule(_manifest())
    container = Container()

    module.init(container)
    resolved = container.resolve(CAPABILITY_INTELLIGENCE_ENGINE)

    assert resolved is module.engine


def test_resolving_the_capability_multiple_times_returns_the_same_instance() -> None:
    # The Container's own SINGLETON scope (the default) already guarantees
    # this; asserted here as this module's own contract, not merely an
    # incidental consequence of the Container's implementation.
    module = IntelligenceModule(_manifest())
    container = Container()
    module.init(container)

    first = container.resolve(CAPABILITY_INTELLIGENCE_ENGINE)
    second = container.resolve(CAPABILITY_INTELLIGENCE_ENGINE)

    assert first is second


# -- Default configuration: ValidatingIntelligenceEngine(NullIntelligenceEngine()) -------------


def test_default_configuration_wraps_a_null_intelligence_engine() -> None:
    module = IntelligenceModule(_manifest())
    module.init(Container())

    assert isinstance(module.engine, ValidatingIntelligenceEngine)
    assert isinstance(module.engine._inner, NullIntelligenceEngine)


def test_no_runtime_config_registered_still_produces_the_default() -> None:
    # No "runtime.config" capability at all (a bare Container()) must
    # behave identically to an explicit "null" configuration.
    module = IntelligenceModule(_manifest())
    module.init(Container())

    assert isinstance(module.engine, ValidatingIntelligenceEngine)
    assert isinstance(module.engine._inner, NullIntelligenceEngine)


def test_resolved_engine_genuinely_works() -> None:
    # Not just "init() didn't raise" -- the registered engine actually
    # answers, mirroring tests/planning/test_module.py's own "resolved is
    # the real, working thing" discipline.
    module = IntelligenceModule(_manifest())
    container = Container()
    module.init(container)
    engine = container.resolve(CAPABILITY_INTELLIGENCE_ENGINE)

    understanding = engine.interpret_requirement(
        Requirement(requirement_id="R-1", description="track patients")
    )

    assert understanding.restated_requirement == "track patients"


# -- Configuration-driven selection, mirroring IntegrationModule's own established pattern -----


def test_explicit_null_configuration_resolves_to_the_null_engine(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    (config_dir / "modules").mkdir(parents=True)
    (config_dir / "modules" / "intelligence.yaml").write_text(
        yaml.safe_dump({_CONFIG_KEY_ENGINE_NAME: "null"}), encoding="utf-8"
    )
    container = Container()
    container.register("runtime.config", lambda: ConfigLoader(config_dir))
    module = IntelligenceModule(_manifest())

    module.init(container)

    assert isinstance(module.engine, ValidatingIntelligenceEngine)
    assert isinstance(module.engine._inner, NullIntelligenceEngine)


def test_an_unknown_configured_engine_name_safely_falls_back_to_the_null_engine(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    (config_dir / "modules").mkdir(parents=True)
    (config_dir / "modules" / "intelligence.yaml").write_text(
        yaml.safe_dump({_CONFIG_KEY_ENGINE_NAME: "some-future-provider-not-yet-registered"}),
        encoding="utf-8",
    )
    container = Container()
    container.register("runtime.config", lambda: ConfigLoader(config_dir))
    module = IntelligenceModule(_manifest())

    module.init(container)

    assert isinstance(module.engine, ValidatingIntelligenceEngine)
    assert isinstance(module.engine._inner, NullIntelligenceEngine)


def test_configuration_key_absent_from_the_module_layer_falls_back_to_the_default(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    (config_dir / "modules").mkdir(parents=True)
    (config_dir / "modules" / "intelligence.yaml").write_text(yaml.safe_dump({}), encoding="utf-8")
    container = Container()
    container.register("runtime.config", lambda: ConfigLoader(config_dir))
    module = IntelligenceModule(_manifest())

    module.init(container)

    assert isinstance(module.engine, ValidatingIntelligenceEngine)
    assert isinstance(module.engine._inner, NullIntelligenceEngine)


# -- Never expose an unwrapped engine ------------------------------------------------------------


class _FixedResolvedConfigLoader:
    """A minimal fake standing in for `ConfigLoader`, exposing only the one
    method `IntelligenceModule.init()` actually calls — proves the module
    depends on `resolve()`'s shape, not on `ConfigLoader` as a concrete
    class.
    """

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def resolve(self, *, module_id: str, strict: bool) -> _FixedResolvedConfigLoader:
        return self

    def get(self, key: str, default: str) -> str:
        return self._values.get(key, default)


def _fixed_config_loader_provider(engine_name: str) -> Callable[[], _FixedResolvedConfigLoader]:
    def _provide() -> _FixedResolvedConfigLoader:
        return _FixedResolvedConfigLoader({_CONFIG_KEY_ENGINE_NAME: engine_name})

    return _provide


def test_the_registered_engine_is_always_validating_wrapped_regardless_of_configuration() -> None:
    for engine_name in (_DEFAULT_ENGINE_NAME, "unknown-provider", ""):
        module = IntelligenceModule(_manifest())
        container = Container()
        container.register("runtime.config", _fixed_config_loader_provider(engine_name))
        module.init(container)
        assert isinstance(container.resolve(CAPABILITY_INTELLIGENCE_ENGINE), ValidatingIntelligenceEngine)


# -- No vendor adapter is instantiated in this phase ---------------------------------------------


def test_only_the_null_engine_is_registered_as_a_factory_in_this_phase() -> None:
    assert set(_ENGINE_FACTORIES) == {"null"}
    assert _ENGINE_FACTORIES["null"] is NullIntelligenceEngine


# -- Boot succeeds without any change to any other module ----------------------------------------


def test_the_real_plugin_directory_still_boots_unaffected_by_this_new_package(tmp_path: Path) -> None:
    # intelligence/module.py is not wired into plugins/ in this phase --
    # this proves its mere existence in the repository does not disturb
    # the existing, real boot sequence in any way. extractor/validator are
    # disabled here for the same reason every prior sprint's own conftest
    # (e.g. tests/sprint7/conftest.py's booted_runtime) already disables
    # them for a bare boot with no further configuration -- orthogonal to
    # what this phase validates.
    config_dir = tmp_path / "config"
    modules_dir = config_dir / "modules"
    modules_dir.mkdir(parents=True)
    for module_id in ("extractor", "validator"):
        (modules_dir / f"{module_id}.yaml").write_text(yaml.safe_dump({"enabled": False}), encoding="utf-8")
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[_PLUGINS_DIR])

    runtime.boot()
    try:
        assert "intelligence.engine" not in runtime.registry.all_provided_capabilities()
    finally:
        runtime.shutdown()
