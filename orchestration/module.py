"""The Orchestration module — `GoalOrchestrator`'s Runtime-facing host.

Implements Sprint 7 Architecture Package §3, §5 (ADR Candidate A):
exactly one new entry in `docs/runtime/MODULE_SYSTEM.md §5`'s domain-module
table, declaring itself against the ordinary `runtime.modules.base.Module`
contract like Integration, Planning, and Execution — nothing about the
Runtime, the top-level `PluginRegistry`, or the Container changes to
accommodate it, per `MODULE_SYSTEM.md §6`'s own "no edit to the Runtime's
own code" guarantee.

Requires `integration.connector_registry`, `planning.engine`, and
`execution.engine` — the first module in this project to depend on three
capabilities across three different providing modules simultaneously
(Sprint 7 Architecture Package §4 invariant 6). `init()` constructs a
`RegistryConnectorInvoker(registry)` internally, mirroring `ExecutionModule`'s
own already-approved pattern for the identical dependency (Sprint 6 §6.2),
and hands it plus both resolved engines to a `GoalOrchestrator` it
constructs and owns. This module owns only the `GoalOrchestrator` — it
never assembles a `PlanningContext`/`ExecutionContext` or calls
`run_goal()` itself, both remain per-call concerns for whoever resolves
`orchestration.goal_runner` (Sprint 7 Architecture Package §3).
"""

from __future__ import annotations

from integration import CAPABILITY_CONNECTOR_REGISTRY
from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.modules.manifest import ModuleManifest

from execution.connector_invoker import RegistryConnectorInvoker
from execution.module import CAPABILITY_EXECUTION_ENGINE
from orchestration.orchestrator import GoalOrchestrator
from planning.module import CAPABILITY_PLANNING_ENGINE

#: The one capability this module provides — resolves to the
#: `GoalOrchestrator` instance itself, already constructed with its own
#: `PlanningEngine`/`ExecutionEngine`/`ConnectorInvoker`, mirroring
#: `execution.module.CAPABILITY_EXECUTION_ENGINE`'s identical shape.
CAPABILITY_GOAL_RUNNER = "orchestration.goal_runner"


class OrchestrationModule(Module):
    """Hosts a ready-to-use `GoalOrchestrator`. Provides
    `orchestration.goal_runner`; requires `integration.connector_registry`,
    `planning.engine`, and `execution.engine`.
    """

    def __init__(self, manifest: ModuleManifest) -> None:
        super().__init__(manifest)
        # Like ExecutionModule.engine, GoalOrchestrator cannot be built
        # until init() resolves all three of its own real dependencies --
        # stays None until then.
        self.orchestrator: GoalOrchestrator | None = None

    def init(self, container: Container) -> None:
        registry = container.resolve(CAPABILITY_CONNECTOR_REGISTRY)
        planning_engine = container.resolve(CAPABILITY_PLANNING_ENGINE)
        execution_engine = container.resolve(CAPABILITY_EXECUTION_ENGINE)
        connector_invoker = RegistryConnectorInvoker(registry)
        self.orchestrator = GoalOrchestrator(planning_engine, execution_engine, connector_invoker)
        container.register(CAPABILITY_GOAL_RUNNER, lambda: self.orchestrator, override=True)

    def health_check(self) -> HealthCheckResult:
        if self.orchestrator is None:
            return HealthCheckResult(healthy=True, detail="GoalOrchestrator not yet initialized")
        return HealthCheckResult(healthy=True, detail="GoalOrchestrator ready")
