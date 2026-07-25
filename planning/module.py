"""The Planning module — the Planning Engine's Runtime-facing host.

Implements Sprint 6 Architecture Package §5, §6.1, §7.1: exactly one new
entry in `docs/runtime/MODULE_SYSTEM.md §5`'s domain-module table,
declaring itself against the ordinary `runtime.modules.base.Module`
contract like Integration — nothing about the Runtime, the top-level
`PluginRegistry`, or the Container changes to accommodate it, per
`MODULE_SYSTEM.md §6`'s own "no edit to the Runtime's own code" guarantee.

Requires nothing: `PlanningEngine`'s own one-way dependency rule (`ADR-0011`
— `planning/` never imports `integration/`) means this module resolves
nothing through the Container either. `RuleBasedPlannerStrategy` is
registered unconditionally — it remains the only `PlannerStrategy` that
exists; configuration-driven strategy selection is explicitly out of this
Sprint's scope (§3) until a second strategy exists to select between.
"""

from __future__ import annotations

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.modules.manifest import ModuleManifest

from planning.engine import PlanningEngine
from planning.strategy import RuleBasedPlannerStrategy

#: The one capability this module provides — resolves to the
#: `PlanningEngine` instance itself, already wired with its own
#: `RuleBasedPlannerStrategy`, mirroring `integration.module.
#: CAPABILITY_CONNECTOR_REGISTRY`'s identical shape one layer up.
CAPABILITY_PLANNING_ENGINE = "planning.engine"


class PlanningModule(Module):
    """Hosts a ready-to-use `PlanningEngine`. Provides `planning.engine`;
    requires nothing.
    """

    def __init__(self, manifest: ModuleManifest) -> None:
        super().__init__(manifest)
        self.engine = PlanningEngine()

    def init(self, container: Container) -> None:
        self.engine.register_strategy(RuleBasedPlannerStrategy())
        container.register(CAPABILITY_PLANNING_ENGINE, lambda: self.engine, override=True)

    def health_check(self) -> HealthCheckResult:
        # Always healthy: PlanningEngine.create_plan() is the only failure
        # mode PlanningEngine itself defines (PlannerStrategyError, if no
        # strategy is registered), and init() always registers one before
        # this could ever be reached in the real Module lifecycle
        # (validate -> init -> start -> health_check). Not read from
        # PlanningEngine's own private state -- there is no public way to
        # ask "is a strategy registered" short of calling create_plan().
        return HealthCheckResult(healthy=True, detail="PlanningEngine ready")
