"""Orchestration's foundational data models — Sprint 7 Architecture Package
§3, `GoalRunResult`'s own `PlanningFailure` field as amended by Architecture
Review before implementation began.

`PlanningFailure` and `GoalRunResult` are pure, frozen pydantic value
objects — no methods, no cross-field validation, mirroring
`planning/contract.py`'s and `execution/contract.py`'s own
construction-only Phase 1/2 discipline exactly. `GoalOrchestrator`
(a later phase) is this Sprint's sole producer of `GoalRunResult`; this
module deliberately does not enforce the "exactly one of `plan`/
`planning_failure` is set" invariant itself — the same "pure data, the
engine validates" split already established for `Plan`/`PlanStep`,
`ExecutionRun`, and every other frozen model in this project, none of
which carry a cross-field validator either.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from execution.contract import ExecutionResult
from planning.contract import Plan


class PlanningFailure(BaseModel):
    """Sprint 7 Architecture Package §3/§5 (ADR Candidate B, as refined
    during Architecture Review): a structured, immutable capture of a
    Planning-phase failure. `GoalOrchestrator` catches `PlannerStrategyError`/
    `PlanValidationError` (`planning/errors.py`, frozen) and stores exactly
    the two facts available without reaching into either exception's own
    internals — neither carries structured data beyond a message.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The caught exception's own class name, e.g. `"PlannerStrategyError"` —
    #: lets a caller distinguish failure kinds without parsing `detail`.
    error_type: str = Field(min_length=1)
    #: `str(exc)`.
    detail: str = Field(min_length=1)


class GoalRunResult(BaseModel):
    """Sprint 7 Architecture Package §3. The uniform, always-obtainable
    outcome of one `GoalOrchestrator.run_goal()` call — exactly one of two
    valid shapes: Planning failed (`plan`/`execution_result` both `None`,
    `planning_failure` populated), or Planning succeeded and Execution ran
    to whatever terminal state it reached on its own (`plan`/
    `execution_result` both populated, `planning_failure` `None`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal_id: str = Field(min_length=1)
    plan: Plan | None = None
    execution_result: ExecutionResult | None = None
    planning_failure: PlanningFailure | None = None
