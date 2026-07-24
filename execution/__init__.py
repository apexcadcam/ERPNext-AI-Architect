"""The Execution Engine — Sprint 5, Phase 2.

Implements the approved Sprint 5 Architecture Package's foundational data
models (§10), state machines (§12), error hierarchy (§16.1), and
event-type identifiers (§21.1). `ExecutionContext`, `ConnectorInvoker`,
`ConfirmationProvider`, `RollbackStrategy`, `CancellationToken`,
`StepScheduler`, and `ExecutionEngine` itself are all later-phase scope —
none of them exist yet.

Depends only on `execution/`'s own modules, `runtime.lifecycle`
(`StateMachine`, reused, not modified), and `integration.contract`
(`ConnectorResponse`, Sprint 5 Phase 1). Nothing in this package imports
`secrets_management/` or `knowledge/`.
"""

from __future__ import annotations

from execution.contract import ExecutionResult, ExecutionRun, RollbackOutcome, StepExecutionRecord
from execution.errors import (
    ConfirmationDeniedError,
    ExecutionCancelledError,
    ExecutionError_,
    PlanNotExecutableError,
    RollbackError,
    StepExecutionError,
    RetryExhaustedError,
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
    "ConfirmationDeniedError",
    "ExecutionCancelledError",
    "ExecutionError_",
    "ExecutionResult",
    "ExecutionRun",
    "ExecutionRunState",
    "PlanNotExecutableError",
    "RetryExhaustedError",
    "RollbackError",
    "RollbackOutcome",
    "StepExecutionError",
    "StepExecutionRecord",
    "StepExecutionState",
    "new_execution_run_lifecycle",
    "new_step_execution_lifecycle",
]
