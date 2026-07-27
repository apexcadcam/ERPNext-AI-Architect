"""The Composition Root — Sprint 13, Phase 2.

Implements the approved Sprint 13 Phase 1 design exactly: one linear
sequence of calls into nine already-existing, frozen components, proving
the complete `Requirements -> ... -> GoalRunResult` chain works live, for
one `Goal`, through the real Runtime. Nothing here is a new abstraction —
every call below is to a public method or constructor that already
existed before this Sprint.

**Why this lives outside every frozen package.** `analysis/`, `knowledge/`,
`intelligence/`, `planning/`, `execution/`, `orchestration/`, and
`runtime/` are all frozen this Sprint; this module imports from all of
them but none of them import this module — confirmed by the sprint-level
architecture tests. It is a caller, not a component.

**Why `PlanningModule` is constructed directly instead of through
`PluginRegistry.instantiate("planning")`.** `plugins/planning/module.py`'s
own `create(manifest) -> PlanningModule(manifest)` factory has a fixed,
zero-extra-kwargs signature — there is no way to route a real
`TradeoffAssessment`/`created_at` through it. `PluginRegistry.get(module_id)`
already exposes the discovered `DiscoveredPlugin` (manifest + plugin_dir)
*without* invoking that factory, so this module uses that to obtain
Planning's real manifest, then constructs `PlanningModule` itself with the
same `(manifest, *, tradeoff_assessment=None, created_at=None)` seam
Sprint 12 Phase 2 built for exactly this purpose. Every other discovered
module is instantiated the ordinary way, through `PluginRegistry.
instantiate()`, unchanged.

**Why `Runtime.boot()` itself is not called.** Its internal
`_start_one_module()` always calls `PluginRegistry.instantiate()` for
every module, including Planning — the one substitution this module makes
has no expression through that convenience method. This module instead
replicates the relevant slice of `Runtime.boot()`'s own sequence
(discover -> register_all -> validate_dependencies -> dependency-ordered
instantiate/validate/init/start) using the same public
`PluginRegistry`/`Container` objects `Runtime` itself is built from —
`runtime/boot.py` is not imported, and nothing under `runtime/` is
modified.

**Why plugin discovery is filtered to four module ids, disclosed rather
than silently narrowed.** A real, genuine finding surfaced while
implementing this design, not assumed beforehand: the full `plugins/`
directory also contains `extractor` and `validator` (Sprint 2's own
Knowledge Factory pipeline modules, entirely unrelated to the Requirements
-> Execution chain this Composition Root demonstrates). `extractor`'s own
`init()` (`knowledge/extraction/module.py`) unconditionally resolves
`knowledge.conflict.providers.PRECEDENCE_PROVIDER_CAPABILITY` — and that
module's own docstring states explicitly: *"No default... implementation
is provided... a caller... supplies an explicit implementation."* No
production code anywhere in this repository supplies one; every existing
test that boots `extractor` supplies its own test-local fake. Booting the
complete, unfiltered `plugins/` directory therefore fails for a reason
that has nothing to do with this Sprint's own scope, and fabricating a
`PrecedenceProvider` here — a real, new implementation of a real Protocol
— would itself be introducing a new abstraction, which this phase's own
brief forbids. `knowledge/` is frozen; no file under it is touched. The
correct, minimal scope is what this function actually needs: `discover()`
returns a plain `list[DiscoveredPlugin]`, filtered here, by module_id,
to exactly the four modules this composition depends on — no filesystem
trick, no new capability, just selecting from data the existing API
already returned.

**`TradeoffAssessment`'s own lifecycle, restated precisely:** produced
exactly once (`evaluate_knowledge_snapshot`, below), injected exactly once
(into the one `PlanningModule` this function constructs), and never
registered as a Container capability or stored on `Container`/`Runtime`
itself — it is held only as a private attribute on that one `PlanningModule`
instance (and, transitively, the one `IntelligenceAwarePlannerStrategy` it
builds) for the duration of this one function call. It never becomes
global Runtime state, and nothing downstream of `create_plan()` — neither
`ExecutionEngine` nor `GoalOrchestrator` — ever references it again; only
the `Plan` it already shaped survives past the Planning stage.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.builder.builder import build_knowledge_snapshot
from knowledge.graph import InMemoryGraphStore
from knowledge.projection.projector import project_snapshot

from analysis.requirements.analyzer import build_analysis_result
from analysis.requirements.raw import RawRequirement

from intelligence.contract import TradeoffAssessment
from intelligence.null_engine import NullIntelligenceEngine
from intelligence.pipeline import evaluate_knowledge_snapshot
from intelligence.validating import ValidatingIntelligenceEngine

from planning.contract import CapabilityDescriptor, Goal, RuntimeContextInfo
from planning.module import PlanningModule

from execution.confirmation import DenyAllConfirmationProvider

from orchestration.contract import GoalRunResult
from orchestration.module import CAPABILITY_GOAL_RUNNER
from orchestration.orchestrator import GoalOrchestrator

from runtime.config.loader import ConfigLoader
from runtime.container.di import Container
from runtime.errors import ManifestError
from runtime.modules.base import Module
from runtime.registry.plugin_registry import PluginRegistry

#: The exact Container capability name `PlanningModule.init()` (and every
#: other module) already checks for — `Runtime.__init__` registers it the
#: identical way (`lambda: self.config_loader`); this Composition Root
#: replicates that one piece of Runtime infrastructure setup for the same
#: reason it replicates the rest of `Runtime.boot()`'s own sequence,
#: since `runtime.boot.Runtime` itself is never constructed here.
_RUNTIME_CONFIG_CAPABILITY = "runtime.config"

#: The one module_id this function constructs directly rather than through
#: `PluginRegistry.instantiate()` — see this module's own docstring.
_PLANNING_MODULE_ID = "planning"

#: Exactly the modules this composition depends on — see this module's
#: own docstring for why `extractor`/`validator` (also present under
#: `plugins/`, unrelated to this chain) are deliberately excluded.
_REQUIRED_MODULE_IDS = frozenset({"integration", _PLANNING_MODULE_ID, "execution", "orchestration"})


def run_goal_end_to_end(
    requirement: RawRequirement,
    goal: Goal,
    available_capabilities: tuple[CapabilityDescriptor, ...],
    *,
    plugin_search_paths: list[Path],
    config_dir: Path,
    created_at: str,
    correlation_id: str,
) -> GoalRunResult:
    """Runs the complete, approved Sprint 13 sequence for one `requirement`/
    `goal` pair and returns the real `GoalRunResult` — `Plan` and
    `ExecutionResult` both populated on success, `planning_failure`
    populated if Planning itself failed (`GoalOrchestrator`'s own,
    unmodified behavior). Any other exception (module boot failure, an
    `ExecutionEngine`-internal precondition violation) propagates
    uncaught, exactly as documented in the approved design.

    `config_dir` is a real, caller-supplied config directory resolvable by
    the existing `runtime.config.loader.ConfigLoader` — per Sprint 12's own
    established discipline, *configuration* decides whether
    `IntelligenceAwarePlannerStrategy` is actually selected, never this
    function's own code; supplying a real `TradeoffAssessment` alone is
    not sufficient (`planning.module`'s own, already-tested fallback
    behavior — unchanged, exercised here, not altered).
    """

    tradeoff_assessment = _compute_tradeoff_assessment(requirement, created_at=created_at)
    goal_runner = _boot_and_resolve_goal_runner(
        plugin_search_paths,
        config_dir=config_dir,
        tradeoff_assessment=tradeoff_assessment,
        created_at=created_at,
    )
    return goal_runner.run_goal(
        goal,
        graph=InMemoryGraphStore(),
        confirmation_provider=DenyAllConfirmationProvider(),
        runtime_context=RuntimeContextInfo(environment="production", requested_by="composition_root"),
        correlation_id=correlation_id,
        available_capabilities=available_capabilities,
    )


def _compute_tradeoff_assessment(requirement: RawRequirement, *, created_at: str) -> TradeoffAssessment:
    analysis_result = build_analysis_result(requirement)
    snapshot = build_knowledge_snapshot(analysis_result, created_at=created_at)
    snapshot = project_snapshot(snapshot)
    engine = ValidatingIntelligenceEngine(NullIntelligenceEngine())
    return evaluate_knowledge_snapshot(snapshot, engine)


def _boot_and_resolve_goal_runner(
    plugin_search_paths: list[Path],
    *,
    config_dir: Path,
    tradeoff_assessment: TradeoffAssessment,
    created_at: str,
) -> GoalOrchestrator:
    registry = PluginRegistry()
    discovered = [
        plugin
        for plugin in registry.discover(plugin_search_paths)
        if plugin.manifest.module_id in _REQUIRED_MODULE_IDS
    ]
    registry.register_all(discovered)
    registry.validate_dependencies()

    container = Container()
    container.register(_RUNTIME_CONFIG_CAPABILITY, lambda: ConfigLoader(config_dir))
    for module_id in registry.dependency_order():
        module: Module
        if module_id == _PLANNING_MODULE_ID:
            module = _construct_planning_module(registry, tradeoff_assessment, created_at)
        else:
            module = registry.instantiate(module_id)
        module.validate()
        module.init(container)
        module.start()

    goal_runner: GoalOrchestrator = container.resolve(CAPABILITY_GOAL_RUNNER)
    return goal_runner


def _construct_planning_module(
    registry: PluginRegistry, tradeoff_assessment: TradeoffAssessment, created_at: str
) -> PlanningModule:
    discovered = registry.get(_PLANNING_MODULE_ID)
    if discovered is None:  # pragma: no cover - structurally unreachable
        # This function is only ever called for a module_id drawn from
        # registry.dependency_order(), which by construction only contains
        # ids that were already successfully registered -- registry.get()
        # returning None here would mean the registry contradicted its own
        # dependency_order() output, a genuine Runtime defect, not a
        # reachable input state. Kept as a defensive, disclosed guard
        # rather than a silent assumption, mirroring execution/engine.py's
        # own identical "# pragma: no cover" precedent for the same
        # category of "should never happen given valid inputs" branch.
        raise ManifestError(f"no plugin registered with module_id '{_PLANNING_MODULE_ID}'")
    return PlanningModule(discovered.manifest, tradeoff_assessment=tradeoff_assessment, created_at=created_at)
