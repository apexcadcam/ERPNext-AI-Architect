"""The Execution Engine — Sprint 5, Phases 2-4.

Implements the approved Sprint 5 Architecture Package's foundational data
models (§10), state machines (§12), error hierarchy (§16.1), and
event-type identifiers (§21.1) — Phase 2 — the read/invoke-only input
surface: `ExecutionContext` (§11), `ConnectorInvoker` + `RegistryConnectorInvoker`
(§9.3), `ConfirmationProvider` + `DenyAllConfirmationProvider` (§9.4),
`RollbackStrategy` + `UnsupportedRollbackStrategy` (§9.5, §19),
`CancellationToken` (§18), and `StepScheduler` (§7, §24) — Phase 3 — and
two pure-logic components, `ConfirmationGate` and `RetryPolicy` (§8, §14,
§17) — Phase 4. `ExecutionEngine` itself is still later-phase scope; none
of Phase 4's two components are wired into a full orchestration loop yet.

`ExecutionContext` has no `event_bus` field, `RegistryConnectorInvoker`
publishes no events, and `RetryPolicy` has no approved path to obtain a
`ConnectorRegistry` reference within `ExecutionEngine` — all three remain
open questions for Phase 5 (see `execution/context.py` and
`execution/retry.py`'s own docstrings).

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
