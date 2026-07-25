"""The Execution module — the Execution Engine's Runtime-facing host.

Implements Sprint 6 Architecture Package §5, §6.2, §7.2: exactly one new
entry in `docs/runtime/MODULE_SYSTEM.md §5`'s domain-module table,
declaring itself against the ordinary `runtime.modules.base.Module`
contract like Integration and Planning — nothing about the Runtime, the
top-level `PluginRegistry`, or the Container changes to accommodate it,
per `MODULE_SYSTEM.md §6`'s own "no edit to the Runtime's own code"
guarantee.

Requires exactly `integration.connector_registry` — a real, Container-
validated dependency edge onto `IntegrationModule`, satisfying `ADR-0014`:
`RetryPolicy(registry)` is constructed first, from the resolved
`ConnectorRegistry`, then handed to `ExecutionEngine(retry_policy)`. This
module owns only the `ExecutionEngine` — never an `ExecutionContext`,
which stays a per-call concern outside any module's own boundary (§6.2)
— and never touches `event_bus`/`runtime.event_bus` (that remains
`ExecutionContext`'s own field, per ADR Candidate C, populated by whoever
assembles one, not by this module). Never imports `planning/`, preserving
Execution's dependency on Planning's frozen *contract types* only, never
on Planning as a live capability (Sprint 5 Architecture Package §6,
restated at Sprint 6 Architecture Package §17 item 3).
"""

from __future__ import annotations

from integration import CAPABILITY_CONNECTOR_REGISTRY, ConnectorRegistry
from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.modules.manifest import ModuleManifest

from execution.engine import ExecutionEngine
from execution.retry import RetryPolicy

#: The one capability this module provides — resolves to the
#: `ExecutionEngine` instance itself, already constructed with its own
#: `RetryPolicy`, mirroring `planning.module.CAPABILITY_PLANNING_ENGINE`'s
#: identical shape.
CAPABILITY_EXECUTION_ENGINE = "execution.engine"


class ExecutionModule(Module):
    """Hosts a ready-to-use `ExecutionEngine`. Provides `execution.engine`;
    requires `integration.connector_registry`.
    """

    def __init__(self, manifest: ModuleManifest) -> None:
        super().__init__(manifest)
        # Unlike IntegrationModule.registry/PlanningModule.engine (both
        # eagerly constructible with no external input), ExecutionEngine
        # requires a RetryPolicy built from a ConnectorRegistry this
        # module does not own and cannot obtain until init() resolves it
        # from the Container -- both fields stay None until then.
        self._registry: ConnectorRegistry | None = None
        self.engine: ExecutionEngine | None = None

    def init(self, container: Container) -> None:
        registry = container.resolve(CAPABILITY_CONNECTOR_REGISTRY)
        self._registry = registry
        retry_policy = RetryPolicy(registry)
        self.engine = ExecutionEngine(retry_policy)
        container.register(CAPABILITY_EXECUTION_ENGINE, lambda: self.engine, override=True)

    def health_check(self) -> HealthCheckResult:
        if self._registry is None:
            return HealthCheckResult(healthy=True, detail="ExecutionEngine not yet initialized")
        connector_count = len(self._registry.all_connectors())
        return HealthCheckResult(
            healthy=True, detail=f"ExecutionEngine ready ({connector_count} connector(s) available)"
        )
