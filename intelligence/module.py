"""The Intelligence module — the Intelligence Abstraction Layer's
Runtime-facing host.

Implements the approved Sprint 8 Implementation Plan §4 Phase 3: exactly
one new entry in `docs/runtime/MODULE_SYSTEM.md §5`'s domain-module table,
declaring itself against the ordinary `runtime.modules.base.Module`
contract like Planning, Execution, Integration, and Orchestration —
nothing about the Runtime, the top-level `PluginRegistry`, or the
Container changes to accommodate it.

Requires nothing: this module constructs its own `IntelligenceEngine`
entirely from configuration (or its own built-in default) — there is no
other module's capability it depends on, mirroring `PlanningModule`'s
"requires nothing" shape.

Configuration-driven engine selection reuses `IntegrationModule`'s own
established `"runtime.config"` pattern (Sprint 6 Architecture Package
§7.3, ADR Candidate B) exactly — `connector_search_paths` there,
`intelligence_engine` here — read once, in `init()`, via the identical
`container.is_registered("runtime.config")` /
`container.resolve("runtime.config")` /
`config_loader.resolve(module_id=..., strict=False)` sequence already
established. No new configuration mechanism is introduced. An
unrecognized value falls back to the same `"null"` default a missing key
would have produced — never a boot-blocking error.

The engine this module provides is never unwrapped: regardless of which
inner implementation configuration selects, it is always
`ValidatingIntelligenceEngine`-wrapped before being registered — the one
place a caller can ever obtain an `IntelligenceEngine` from the Runtime
already carries Phase 2's non-bypassable citation enforcement.
"""

from __future__ import annotations

from collections.abc import Callable

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.modules.manifest import ModuleManifest

from intelligence.contract import IntelligenceEngine
from intelligence.null_engine import NullIntelligenceEngine
from intelligence.validating import ValidatingIntelligenceEngine

#: The one capability this module provides — resolves to a
#: `ValidatingIntelligenceEngine`-wrapped `IntelligenceEngine`, mirroring
#: `planning.module.CAPABILITY_PLANNING_ENGINE`'s identical shape.
CAPABILITY_INTELLIGENCE_ENGINE = "intelligence.engine"

#: The configuration key `init()` reads from the `"runtime.config"`
#: capability, module-scoped to this module's own `manifest.module_id`.
_CONFIG_KEY_ENGINE_NAME = "intelligence_engine"

#: Selecting this name, or any name absent from `_ENGINE_FACTORIES` below,
#: resolves to `NullIntelligenceEngine` — Sprint 8's one, deliberately
#: minimal reference implementation (Phase 2). A later phase's adapter
#: (e.g. Phase 4) only ever needs one new entry added here — nothing about
#: this module's own structure changes to support it.
_DEFAULT_ENGINE_NAME = "null"
_ENGINE_FACTORIES: dict[str, Callable[[], IntelligenceEngine]] = {
    _DEFAULT_ENGINE_NAME: NullIntelligenceEngine,
}


def _build_inner_engine(engine_name: str) -> IntelligenceEngine:
    factory = _ENGINE_FACTORIES.get(engine_name, _ENGINE_FACTORIES[_DEFAULT_ENGINE_NAME])
    return factory()


class IntelligenceModule(Module):
    """Hosts a ready-to-use, always-`ValidatingIntelligenceEngine`-wrapped
    `IntelligenceEngine`. Provides `intelligence.engine`; requires nothing.
    """

    def __init__(self, manifest: ModuleManifest) -> None:
        super().__init__(manifest)
        # Deferred to init(), like ExecutionModule.engine — unlike
        # PlanningModule's eagerly-constructible PlanningEngine, which
        # engine this module hosts depends on configuration only available
        # once init() resolves the Container.
        self.engine: IntelligenceEngine | None = None

    def init(self, container: Container) -> None:
        engine_name = _DEFAULT_ENGINE_NAME
        if container.is_registered("runtime.config"):
            config_loader = container.resolve("runtime.config")
            resolved = config_loader.resolve(module_id=self.manifest.module_id, strict=False)
            engine_name = resolved.get(_CONFIG_KEY_ENGINE_NAME, _DEFAULT_ENGINE_NAME)

        inner = _build_inner_engine(engine_name)
        self.engine = ValidatingIntelligenceEngine(inner)
        container.register(CAPABILITY_INTELLIGENCE_ENGINE, lambda: self.engine, override=True)

    def health_check(self) -> HealthCheckResult:
        if self.engine is None:
            return HealthCheckResult(healthy=True, detail="IntelligenceEngine not yet initialized")
        return HealthCheckResult(healthy=True, detail="IntelligenceEngine ready")
