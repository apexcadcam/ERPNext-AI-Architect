"""The Planning module — the Planning Engine's Runtime-facing host.

Implements Sprint 6 Architecture Package §5, §6.1, §7.1: exactly one new
entry in `docs/runtime/MODULE_SYSTEM.md §5`'s domain-module table,
declaring itself against the ordinary `runtime.modules.base.Module`
contract like Integration — nothing about the Runtime, the top-level
`PluginRegistry`, or the Container changes to accommodate it, per
`MODULE_SYSTEM.md §6`'s own "no edit to the Runtime's own code" guarantee.

**Sprint 12, Phase 2 — configuration-driven strategy selection.** Sprint
6 deferred this "until a second strategy exists to select between"
(`planning.strategy_intelligence.IntelligenceAwarePlannerStrategy`,
Sprint 12 Phase 1) — it now does. Selection reuses `IntelligenceModule`'s
own established `"runtime.config"` pattern exactly (`intelligence_engine`
there, `planner_strategy` here): read once, in `init()`, via the identical
`container.is_registered("runtime.config")` /
`container.resolve("runtime.config")` /
`config_loader.resolve(module_id=..., strict=False)` sequence. No new
configuration mechanism, no new Container capability, no change to
`Container`/`Module`/`ModuleManifest`/`PluginRegistry` — `plugins/planning/
module.py`'s existing `create(manifest) -> PlanningModule(manifest)` call
keeps working completely unchanged.

**Where this module's own construction differs from `IntelligenceModule`'s,
disclosed rather than glossed over:** `IntelligenceModule`'s own
`_ENGINE_FACTORIES` are all zero-argument callables — `NullIntelligenceEngine`
needs nothing external. `IntelligenceAwarePlannerStrategy` structurally
cannot be zero-argument: it requires a real `TradeoffAssessment` and a
real `created_at`, and this phase's own brief is explicit that neither may
be constructed or fabricated here — "all Intelligence-derived inputs must
be supplied by the caller." The caller in question is whoever constructs
this `PlanningModule` instance: `__init__` accepts both as optional,
keyword-only parameters, defaulting to `None`. If configuration selects
`"intelligence_aware"` *and* both were actually supplied, `init()`
constructs `IntelligenceAwarePlannerStrategy` from them, via dependency
injection, exactly as `IntelligenceAwarePlannerStrategy`'s own constructor
already requires. If configuration selects `"intelligence_aware"` but
either is missing, this module falls back to `RuleBasedPlannerStrategy` —
the same "never a boot-blocking error, fall back to the deterministic
default" discipline `IntelligenceModule` already established for an
unrecognized engine name, generalized one step further to "selected but
unsuppliable" as well. `RuleBasedPlannerStrategy` remains the strategy
`init()` uses whenever configuration is absent, unrecognized, or names
`"rule_based"` explicitly — unconditionally, exactly as before Phase 2,
so every existing caller's behavior is unchanged.

**`PlanningModule` is the only Planning component aware that more than
one `PlannerStrategy` exists.** `planning/engine.py` and `planning/
strategy.py` are both unmodified and remain fully unaware of
configuration, of `intelligence.contract`, or of which concrete strategy
is active — `PlanningEngine.register_strategy`/`create_plan` operate on
the `PlannerStrategy` abstraction alone, exactly as before.
"""

from __future__ import annotations

from collections.abc import Callable

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.modules.manifest import ModuleManifest

from planning.engine import PlanningEngine
from planning.strategy import PlannerStrategy, RuleBasedPlannerStrategy
from planning.strategy_intelligence import IntelligenceAwarePlannerStrategy

from intelligence.contract import TradeoffAssessment

#: The one capability this module provides — resolves to the
#: `PlanningEngine` instance itself, already wired with its own selected
#: `PlannerStrategy`, mirroring `integration.module.
#: CAPABILITY_CONNECTOR_REGISTRY`'s identical shape one layer up.
CAPABILITY_PLANNING_ENGINE = "planning.engine"

#: The configuration key `init()` reads from the `"runtime.config"`
#: capability, module-scoped to this module's own `manifest.module_id`.
_CONFIG_KEY_STRATEGY_NAME = "planner_strategy"

#: Selecting this name, an unrecognized name, or an absent key resolves to
#: `RuleBasedPlannerStrategy` — unconditionally, the same fallback
#: `RuleBasedPlannerStrategy` was registered with before Phase 2.
_DEFAULT_STRATEGY_NAME = "rule_based"

#: Selecting this name uses `IntelligenceAwarePlannerStrategy` — but only
#: when this module was actually constructed with a real
#: `TradeoffAssessment`/`created_at` to inject; see this module's own
#: docstring for the disclosed fallback when it wasn't.
_INTELLIGENCE_AWARE_STRATEGY_NAME = "intelligence_aware"

#: Zero-argument factories only — `IntelligenceAwarePlannerStrategy` is
#: deliberately not a member of this dict, since it cannot be constructed
#: with no arguments; `_build_strategy` handles it as a disclosed, separate
#: case instead of forcing it into this dict's uniform shape.
_STRATEGY_FACTORIES: dict[str, Callable[[], PlannerStrategy]] = {
    _DEFAULT_STRATEGY_NAME: RuleBasedPlannerStrategy,
}


class PlanningModule(Module):
    """Hosts a ready-to-use `PlanningEngine`, already wired with whichever
    `PlannerStrategy` configuration selected. Provides `planning.engine`;
    requires nothing.
    """

    def __init__(
        self,
        manifest: ModuleManifest,
        *,
        tradeoff_assessment: TradeoffAssessment | None = None,
        created_at: str | None = None,
    ) -> None:
        super().__init__(manifest)
        self.engine = PlanningEngine()
        self._tradeoff_assessment = tradeoff_assessment
        self._created_at = created_at

    def init(self, container: Container) -> None:
        strategy_name = _DEFAULT_STRATEGY_NAME
        if container.is_registered("runtime.config"):
            config_loader = container.resolve("runtime.config")
            resolved = config_loader.resolve(module_id=self.manifest.module_id, strict=False)
            strategy_name = resolved.get(_CONFIG_KEY_STRATEGY_NAME, _DEFAULT_STRATEGY_NAME)

        self.engine.register_strategy(self._build_strategy(strategy_name), override=True)
        container.register(CAPABILITY_PLANNING_ENGINE, lambda: self.engine, override=True)

    def _build_strategy(self, strategy_name: str) -> PlannerStrategy:
        if (
            strategy_name == _INTELLIGENCE_AWARE_STRATEGY_NAME
            and self._tradeoff_assessment is not None
            and self._created_at
        ):
            return IntelligenceAwarePlannerStrategy(self._tradeoff_assessment, created_at=self._created_at)
        factory = _STRATEGY_FACTORIES.get(strategy_name, _STRATEGY_FACTORIES[_DEFAULT_STRATEGY_NAME])
        return factory()

    def health_check(self) -> HealthCheckResult:
        # Always healthy: PlanningEngine.create_plan() is the only failure
        # mode PlanningEngine itself defines (PlannerStrategyError, if no
        # strategy is registered), and init() always registers one --
        # RuleBasedPlannerStrategy at minimum, even when "intelligence_aware"
        # was selected without a supplied TradeoffAssessment -- before this
        # could ever be reached in the real Module lifecycle (validate ->
        # init -> start -> health_check). Not read from PlanningEngine's own
        # private state -- there is no public way to ask "is a strategy
        # registered" short of calling create_plan().
        return HealthCheckResult(healthy=True, detail="PlanningEngine ready")
