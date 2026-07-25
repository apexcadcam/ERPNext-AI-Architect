"""The Runtime: orchestrates the eight-step boot sequence and owns shutdown.

Implements docs/runtime/RUNTIME_BOOT_SEQUENCE.md's exact ordering:

  1. Runtime Startup
  2. Plugin Discovery
  3. Dependency Validation
  4. Configuration Loading
  5. Pipeline Registration
  6. Connector Registration
  7. Health Checks
  8. Ready State

Implementation note (an explicit, disclosed interpretation, not a silent
deviation — flagged per the task's "propose the smallest possible change"
instruction rather than left implicit): RUNTIME_BOOT_SEQUENCE.md §4 says
Configuration Loading "may narrow the set of modules that proceed past this
point relative to what Step 3 validated structurally," but does not
explicitly say what happens if that narrowing itself breaks a dependency
(e.g. config disables a module something else requires). Silently
proceeding would violate the "Deterministic" / boot-blocking-error
discipline every other gate in this document set holds itself to, so this
implementation re-runs dependency validation after applying configuration's
enable/disable overrides, still within Step 4, before Step 5 begins. No
existing document is contradicted by this — RUNTIME_BOOT_SEQUENCE.md never
says validation runs *only* once, and CONFIGURATION_SYSTEM.md §4 already
establishes that a violation surfaced at this layer is boot-blocking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from runtime.config.loader import ConfigLoader, ResolvedConfig
from runtime.container.di import Container
from runtime.errors import DependencyValidationError, ModuleLifecycleError
from runtime.events.bus import EventBus
from runtime.lifecycle import (
    ModuleState,
    RuntimeState,
    StateMachine,
    new_module_lifecycle,
    new_runtime_lifecycle,
)
from runtime.modules.base import HealthCheckResult, Module
from runtime.observability.logging import configure_logging, get_logger
from runtime.pipeline.engine import PipelineEngine
from runtime.registry.plugin_registry import PluginRegistry

logger = get_logger(__name__)


@dataclass
class ModuleRuntimeRecord:
    """Everything the Runtime tracks about one instantiated module."""

    module_id: str
    instance: Module
    state: StateMachine[ModuleState]
    health: HealthCheckResult | None = None


@dataclass
class RuntimeInfo:
    """The summary `architect runtime info` and `architect doctor` report."""

    state: RuntimeState
    environment: str
    discovered_module_count: int
    enabled_module_count: int
    started_module_count: int
    registered_pipeline_count: int
    module_health: dict[str, HealthCheckResult] = field(default_factory=dict)
    dependency_order: tuple[str, ...] = ()


class Runtime:
    """The Core Runtime Platform. Knows modules, not domains — see
    docs/runtime/RUNTIME_ARCHITECTURE.md §1.
    """

    def __init__(
        self,
        *,
        config_dir: Path | str,
        plugin_search_paths: list[Path] | None = None,
        environment: str | None = None,
    ) -> None:
        self.config_loader = ConfigLoader(config_dir, environment=environment)
        self.plugin_search_paths = plugin_search_paths or []
        self.registry = PluginRegistry()
        self.container = Container()
        self.event_bus = EventBus()
        self.pipeline_engine = PipelineEngine(self.container, self.event_bus)

        # Well-known, Container-resolvable Runtime infrastructure capabilities
        # (Sprint 6 Architecture Package §18, ADR Candidate B) — registered
        # unconditionally, here at construction, so every module can resolve
        # either from its very first init() call onward, regardless of
        # whether boot() has run yet. Neither appears in any module's own
        # capabilities_provided/capabilities_required (§11): both are Runtime
        # infrastructure, not a contingent, module-provided capability.
        # "runtime.event_bus" is already referenced, defensively, by
        # knowledge/extraction/module.py and knowledge/validation/module.py —
        # this is the first place anything actually registers it.
        self.container.register("runtime.event_bus", lambda: self.event_bus)
        self.container.register("runtime.config", lambda: self.config_loader)

        self._lifecycle = new_runtime_lifecycle()
        self._module_records: dict[str, ModuleRuntimeRecord] = {}
        self._resolved_config: ResolvedConfig | None = None

    @property
    def state(self) -> RuntimeState:
        return self._lifecycle.state

    # -- boot ------------------------------------------------------------

    def boot(self) -> RuntimeInfo:
        """Run the full eight-step sequence. Raises on the first
        boot-blocking failure, per RUNTIME_BOOT_SEQUENCE.md §0: "a failure
        at step N halts the sequence at N."
        """

        logger.info("runtime boot starting")

        try:
            # Step 2 — Plugin Discovery
            self._lifecycle.transition(RuntimeState.PLUGIN_DISCOVERY)
            discovered = self.registry.discover(self.plugin_search_paths)
            self.registry.register_all(discovered)
            logger.info("plugin discovery complete", extra={"discovered_count": len(discovered)})

            # Step 3 — Dependency Validation (against manifest-default-enabled set)
            self._lifecycle.transition(RuntimeState.DEPENDENCY_VALIDATION)
            self.registry.validate_dependencies()

            # Step 4 — Configuration Loading
            self._lifecycle.transition(RuntimeState.CONFIG_LOADING)
            self._resolved_config = self.config_loader.resolve()
            configure_logging(
                level=str(self._resolved_config["log_level"]),
                log_format=str(self._resolved_config["log_format"]),
            )
            self._apply_module_enablement_overrides()
            try:
                self.registry.validate_dependencies()
            except DependencyValidationError as exc:
                # See module docstring: re-validated here because configuration's
                # enable/disable overrides can invalidate what Step 3 already
                # checked, and that must be boot-blocking too.
                raise DependencyValidationError(
                    f"configuration's module enable/disable overrides broke dependency validation: {exc}"
                ) from exc
            logger.info("configuration loaded", extra={"environment": self.config_loader.environment})

            # Step 5 — Pipeline Registration (no PipelineDefinitions exist to
            # register from any module in Sprint 1 — the engine itself is ready
            # to accept them, per Sprint 1 scope).
            self._lifecycle.transition(RuntimeState.PIPELINE_REGISTRATION)
            logger.info(
                "pipeline registration complete",
                extra={"registered_count": len(self.pipeline_engine.registered_pipelines())},
            )

            # Step 6 — Connector Registration (nested inside a Crawler module,
            # which does not exist in Sprint 1 — always a no-op today).
            self._lifecycle.transition(RuntimeState.CONNECTOR_REGISTRATION)

            # Step 7 — Health Checks (instantiate + init + start + health_check,
            # dependencies-first, per LIFECYCLE.md §3's shutdown-order rule
            # applied in reverse for startup).
            self._lifecycle.transition(RuntimeState.HEALTH_CHECKING)
            self._start_modules()

            # Step 8 — Ready State
            self._lifecycle.transition(RuntimeState.READY)
        except Exception:
            # RUNTIME_BOOT_SEQUENCE.md §0 / LIFECYCLE.md §1: "a failure at
            # step N halts the sequence at N" and every step may fail into
            # FAILED — this is the one place that guarantee is actually
            # enforced, regardless of which step raised.
            logger.exception("runtime boot failed")
            self._lifecycle.transition(RuntimeState.FAILED)
            raise

        logger.info("runtime boot complete", extra={"state": self._lifecycle.state.value})
        return self.info()

    def _apply_module_enablement_overrides(self) -> None:
        for plugin in self.registry.all_plugins():
            module_config = self.config_loader.load_module(plugin.manifest.module_id)
            if "enabled" in module_config:
                self.registry.set_enabled(plugin.manifest.module_id, bool(module_config["enabled"]))

    def _start_modules(self) -> None:
        for module_id in self.registry.dependency_order():
            record = self._start_one_module(module_id)
            self._module_records[module_id] = record

    def _start_one_module(self, module_id: str) -> ModuleRuntimeRecord:
        lifecycle = new_module_lifecycle()
        try:
            instance = self.registry.instantiate(module_id)
            instance.validate()
            lifecycle.transition(ModuleState.VALIDATED)

            instance.init(self.container)
            lifecycle.transition(ModuleState.INITIALIZED)

            def _provide(inst: Module = instance) -> Module:
                return inst

            for capability in instance.manifest.capabilities_provided:
                # Each module provides itself as the resolvable object for
                # any of its own declared capabilities it did not already
                # register something more specific for inside its own
                # init() (e.g. IntegrationModule registering the live
                # ConnectorRegistry it hosts, not itself) — a more granular
                # per-method capability mapping is Sprint 2 scope (see
                # IMPLEMENTATION summary); this generic fallback is enough
                # to prove the wiring end to end for a module with nothing
                # more specific to offer. Sprint 6 Architecture Package
                # §18, ADR Candidate A: a module's own, more specific
                # registration must never be silently overwritten here.
                if not self.container.is_registered(capability):
                    self.container.register(capability, _provide)

            instance.start()
            lifecycle.transition(ModuleState.STARTED)
            lifecycle.transition(ModuleState.RUNNING)

            health = instance.health_check()
        except Exception as exc:
            lifecycle.transition(ModuleState.FAILED)
            raise ModuleLifecycleError(f"module '{module_id}' failed to start: {exc}") from exc

        logger.info(
            "module started",
            extra={"module_id": module_id, "healthy": health.healthy, "detail": health.detail},
        )
        return ModuleRuntimeRecord(module_id=module_id, instance=instance, state=lifecycle, health=health)

    # -- shutdown --------------------------------------------------------

    def shutdown(self) -> None:
        """Stop every module in reverse dependency order (LIFECYCLE.md §3),
        then tear down the Event Bus.
        """

        if self._lifecycle.state is RuntimeState.READY:
            self._lifecycle.transition(RuntimeState.RUNNING)
        if self._lifecycle.state is RuntimeState.RUNNING:
            self._lifecycle.transition(RuntimeState.DRAINING)

        for module_id in reversed(self.registry.dependency_order()):
            record = self._module_records.get(module_id)
            if record is None:
                continue
            try:
                record.instance.stop()
                record.state.transition(ModuleState.STOPPING)
                record.state.transition(ModuleState.STOPPED)
            except Exception:
                logger.exception("module failed to stop cleanly", extra={"module_id": module_id})

        self.event_bus.shutdown()
        if self._lifecycle.state is RuntimeState.DRAINING:
            self._lifecycle.transition(RuntimeState.STOPPED)
        logger.info("runtime shutdown complete")

    # -- introspection -----------------------------------------------------

    def info(self) -> RuntimeInfo:
        environment = self.config_loader.environment
        return RuntimeInfo(
            state=self._lifecycle.state,
            environment=environment,
            discovered_module_count=len(self.registry.all_plugins()),
            enabled_module_count=len(self.registry.enabled_plugins()),
            started_module_count=len(self._module_records),
            registered_pipeline_count=len(self.pipeline_engine.registered_pipelines()),
            module_health={mid: r.health for mid, r in self._module_records.items() if r.health is not None},
            dependency_order=self.registry.dependency_order() if self.registry.validated else (),
        )

    def all_healthy(self) -> bool:
        return all(
            record.health is not None and record.health.healthy for record in self._module_records.values()
        )
