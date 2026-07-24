"""The Execution Engine — Sprint 5, Phases 2-5.

Implements the approved Sprint 5 Architecture Package's foundational data
models (§10), state machines (§12), error hierarchy (§16.1), and
event-type identifiers (§21.1) — Phase 2 — the read/invoke-only input
surface: `ExecutionContext` (§11), `ConnectorInvoker` + `RegistryConnectorInvoker`
(§9.3), `ConfirmationProvider` + `DenyAllConfirmationProvider` (§9.4),
`RollbackStrategy` + `UnsupportedRollbackStrategy` (§9.5, §19),
`CancellationToken` (§18), and `StepScheduler` (§7, §24) — Phase 3 — two
pure-logic components, `ConfirmationGate` and `RetryPolicy` (§8, §14, §17)
— Phase 4 — and `ExecutionEngine` itself (§8, §9.2, §15), wiring all of the
above into a full orchestration loop for `execute(plan, context) ->
ExecutionResult` — Phase 5. Rollback (§19) and `cancellation_token`
checks (§18) are not wired into the loop yet; both are Phase 6 scope.

`RetryPolicy`'s `ConnectorRegistry` access is resolved: `ExecutionEngine`
takes a `RetryPolicy` at construction (`ADR-0014`), mirroring
`RegistryConnectorInvoker`'s own constructor-injection shape one layer
down. `ExecutionContext` still has no `event_bus` field, so
`RegistryConnectorInvoker` and `ExecutionEngine` both publish no events —
still an open question, orthogonal to `ADR-0014`, for a future phase (see
`execution/context.py`, `execution/connector_invoker.py`, and
`execution/engine.py`'s own docstrings).

Depends on `execution/`'s own modules, `runtime.lifecycle` (`StateMachine`,
reused, not modified), `integration.contract`/`integration.lifecycle`/
`integration.registry` (Sprint 3, extended by Sprint 5 Phase 1), and
`planning.contract` (Sprint 4, frozen, reused). Nothing in this package
imports `secrets_management/` or `knowledge/`.
"""

from __future__ import annotations

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider, DenyAllConfirmationProvider
from execution.confirmation_gate import ConfirmationGate
from execution.connector_invoker import ConnectorInvoker, RegistryConnectorInvoker
from execution.context import ExecutionContext
from execution.contract import ExecutionResult, ExecutionRun, RollbackOutcome, StepExecutionRecord
from execution.engine import ExecutionEngine
from execution.errors import (
    ConfirmationDeniedError,
    ExecutionCancelledError,
    ExecutionError_,
    PlanNotExecutableError,
    RetryExhaustedError,
    RollbackError,
    StepExecutionError,
)
from execution.events import (
    EXECUTION_CANCELLED,
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
    EXECUTION_STARTED,
    STEP_AWAITING_CONFIRMATION,
    STEP_FAILED,
    STEP_SKIPPED,
    STEP_STARTED,
    STEP_SUCCEEDED,
)
from execution.lifecycle import (
    ExecutionRunState,
    StepExecutionState,
    new_execution_run_lifecycle,
    new_step_execution_lifecycle,
)
from execution.retry import RetryPolicy
from execution.rollback import RollbackStrategy, UnsupportedRollbackStrategy
from execution.scheduler import StepScheduler

__all__ = [
    "EXECUTION_CANCELLED",
    "EXECUTION_COMPLETED",
    "EXECUTION_FAILED",
    "EXECUTION_STARTED",
    "STEP_AWAITING_CONFIRMATION",
    "STEP_FAILED",
    "STEP_SKIPPED",
    "STEP_STARTED",
    "STEP_SUCCEEDED",
    "CancellationToken",
    "ConfirmationDeniedError",
    "ConfirmationGate",
    "ConfirmationProvider",
    "ConnectorInvoker",
    "DenyAllConfirmationProvider",
    "ExecutionCancelledError",
    "ExecutionContext",
    "ExecutionEngine",
    "ExecutionError_",
    "ExecutionResult",
    "ExecutionRun",
    "ExecutionRunState",
    "PlanNotExecutableError",
    "RegistryConnectorInvoker",
    "RetryExhaustedError",
    "RetryPolicy",
    "RollbackError",
    "RollbackOutcome",
    "RollbackStrategy",
    "StepExecutionError",
    "StepExecutionRecord",
    "StepExecutionState",
    "StepScheduler",
    "UnsupportedRollbackStrategy",
    "new_execution_run_lifecycle",
    "new_step_execution_lifecycle",
]
