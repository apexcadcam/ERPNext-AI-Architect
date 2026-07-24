"""Execution Engine — foundational data models.

Implements the Sprint 5 Architecture Package's Core Models (§10):
`StepExecutionRecord`, `ExecutionResult`, `RollbackOutcome` — frozen,
immutable pydantic value objects, mirroring `planning/contract.py`'s own
construction-only discipline exactly — and `ExecutionRun` (§10.1,
§11.5's Execution Ownership subsection), which is deliberately **not**
frozen: it is the one live, in-progress output `ExecutionEngine` (a later
phase) mutates as a run proceeds, mirroring `runtime.boot.RuntimeInfo`/
`ModuleRuntimeRecord`'s own established "plain, mutable dataclass for live
orchestration state" precedent, not `Plan`/`PlanStep`'s frozen shape — §20's
own disclosed departure from Planning's "never mutate" discipline applies
here, not the "everything is frozen" one.

`ExecutionRun.state`/`StepExecutionRecord.state` are plain `ExecutionRunState`/
`StepExecutionState` enum values (`execution.lifecycle`) in this phase —
deliberately not the full `StateMachine` object embedded as a field: that
would import real transition-validating *behavior* into what this phase's
own scope keeps to "pure data, zero live dependency beyond types" (mirroring
Planning Phase 1 exactly). Transition validation using
`execution.lifecycle.new_execution_run_lifecycle()`/
`new_step_execution_lifecycle()` is `ExecutionEngine`'s own concern (a later
phase), which validates a transition before writing the resulting enum
value onto the objects defined here.

Phase 2 scope only: no `ExecutionContext`, no `ConnectorInvoker`/
`ConfirmationProvider`/`RollbackStrategy` contracts, no `StepScheduler`, no
orchestration logic of any kind — all later phases.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from execution.lifecycle import ExecutionRunState, StepExecutionState
from integration.contract import ConnectorResponse


class RollbackOutcome(BaseModel):
    """Sprint 5 Architecture Package §19. Every rollback pass this Sprint
    ships resolves to `supported=False` — no connector shipped as of this
    Sprint declares a compensating action. This type exists so that always
    stays a truthful, structured statement rather than a silent omission.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    supported: bool
    detail: str = ""


class StepExecutionRecord(BaseModel):
    """Sprint 5 Architecture Package §10.2. The per-`PlanStep` record of
    what happened during one execution run.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str = Field(min_length=1)
    state: StepExecutionState
    attempts: int = Field(default=0, ge=0)
    started_at: str | None = None
    finished_at: str | None = None
    response: ConnectorResponse | None = None
    confirmation_granted: bool | None = None
    rollback_outcome: RollbackOutcome | None = None


class ExecutionResult(BaseModel):
    """Sprint 5 Architecture Package §10.3, §13. `ExecutionEngine`'s sole
    return value — immutable, produced once, after `ExecutionRun` reaches a
    terminal state (§11.5's Execution Ownership subsection).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_run_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    final_state: ExecutionRunState
    step_records: tuple[StepExecutionRecord, ...] = ()
    rollback_attempted: bool = False


@dataclass
class ExecutionRun:
    """Sprint 5 Architecture Package §10.1, §11.5. The single, mutable
    record of one `execute()` call's progress — see this module's own
    docstring for why this is a plain dataclass, not a frozen pydantic
    model. `ExecutionEngine` is its sole creator and mutator; every other
    component may only read it (§11.5).
    """

    execution_run_id: str
    plan_id: str
    goal_id: str
    state: ExecutionRunState
    started_at: str
    finished_at: str | None = None
    step_records: tuple[StepExecutionRecord, ...] = ()

    def __post_init__(self) -> None:
        if not self.execution_run_id:
            raise ValueError("execution_run_id must not be empty")
        if not self.plan_id:
            raise ValueError("plan_id must not be empty")
        if not self.goal_id:
            raise ValueError("goal_id must not be empty")
        if not self.started_at:
            raise ValueError("started_at must not be empty")
