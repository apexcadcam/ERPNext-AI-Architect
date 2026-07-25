"""Goal Orchestration — Sprint 7, Phases 1-2.

Implements the approved Sprint 7 Architecture Package's foundational data
models — `PlanningFailure`, `GoalRunResult` (Phase 1) — and the pure
orchestration class that composes `PlanningEngine`/`ExecutionEngine` into
one `Goal`-to-result call, `GoalOrchestrator` (Phase 2). `OrchestrationModule`
is later-phase scope; it does not exist yet, and this module deliberately
never re-exports it, mirroring `planning/__init__.py`'s/`execution/
__init__.py`'s own established discipline of leaving the Runtime-facing
Module wrapper reachable only via its own file.

The one package this project has ever approved importing two sibling
domain packages directly (`planning/`, `execution/`) — Sprint 7
Architecture Package §5, ADR Candidate C — since composing exactly those
two, behind one `Goal`-to-result call, is this package's entire reason to
exist. Nothing in `planning/`/`execution/` imports `orchestration/`, or is
otherwise aware it exists.
"""

from __future__ import annotations

from orchestration.contract import GoalRunResult, PlanningFailure
from orchestration.orchestrator import GoalOrchestrator

__all__ = [
    "GoalOrchestrator",
    "GoalRunResult",
    "PlanningFailure",
]
