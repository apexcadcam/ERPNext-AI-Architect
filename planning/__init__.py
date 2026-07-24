"""The Planning Engine — Sprint 4, Phases 1-5.

Implements the approved Sprint 4 Architecture Package's foundational data
models, error hierarchy, event-type identifiers (Phase 1), read-only input
surface — `GraphReader` and `PlanningContext` (Phase 2) — Plan Validation —
`validate_plan`/`PlanValidationReport` (Phase 3) — the orchestration host,
`PlanningEngine` (Phase 4) — and the permanent `PlannerStrategy` contract
plus its one reference implementation, `RuleBasedPlannerStrategy` (Phase 5).
`CapabilityResolver` and the Runtime module wrapper (`plugins/planning/`)
are still later-phase scope — neither exists yet, and nothing in this
package imports `integration/` or `secrets_management/`.
"""

from __future__ import annotations

from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.errors import (
    GoalDefinitionError,
    NoUsableCapabilityError,
    PlanningContextError,
    PlanningError_,
    PlannerStrategyError,
    PlanValidationError,
)
from planning.events import PLAN_CREATED, PLAN_VALIDATION_FAILED, PLANNING_FAILED, PLANNING_STARTED
from planning.graph_reader import GraphReader
from planning.strategy import PlannerStrategy, RuleBasedPlannerStrategy
from planning.validation import PlanValidationReport, validate_plan

__all__ = [
    "PLANNING_STARTED",
    "PLAN_CREATED",
    "PLAN_VALIDATION_FAILED",
    "PLANNING_FAILED",
    "CapabilityDescriptor",
    "Goal",
    "GoalDefinitionError",
    "GraphReader",
    "NoUsableCapabilityError",
    "Plan",
    "PlanStep",
    "PlanValidationError",
    "PlanValidationReport",
    "PlanningContext",
    "PlanningContextError",
    "PlanningEngine",
    "PlanningError_",
    "PlannerStrategy",
    "PlannerStrategyError",
    "RuleBasedPlannerStrategy",
    "RuntimeContextInfo",
    "validate_plan",
]
