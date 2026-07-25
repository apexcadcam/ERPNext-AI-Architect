"""Goal Orchestration — Sprint 7, Phase 1.

Implements the approved Sprint 7 Architecture Package's foundational data
models: `PlanningFailure`, `GoalRunResult` — pure data, zero orchestration
logic. `GoalOrchestrator` and `OrchestrationModule` are later-phase scope;
neither exists yet.

The one package this project has ever approved importing two sibling
domain packages directly (`planning/`, `execution/`) — Sprint 7
Architecture Package §5, ADR Candidate C — since composing exactly those
two, behind one `Goal`-to-result call, is this package's entire reason to
exist. Nothing in `planning/`/`execution/` imports `orchestration/`, or is
otherwise aware it exists.
"""

from __future__ import annotations

from orchestration.contract import GoalRunResult, PlanningFailure

__all__ = [
    "GoalRunResult",
    "PlanningFailure",
]
