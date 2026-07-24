"""The Planning Engine — Sprint 4, Phases 1-2.

Implements the approved Sprint 4 Architecture Package's foundational data
models, error hierarchy, event-type identifiers (Phase 1), and read-only
input surface — `GraphReader` and `PlanningContext` (Phase 2). `PlanningEngine`,
`PlannerStrategy`, `CapabilityResolver`, `validate_plan`, and the Runtime
module wrapper (`plugins/planning/`) are all later-phase scope — none of
them exist yet, and nothing in this package imports `integration/` or
`secrets_management/`.
"""

from __future__ import annotations

from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep, RuntimeContextInfo
from planning.context import PlanningContext
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
    "PlanningContext",
    "PlanningContextError",
    "PlanningError_",
    "PlannerStrategyError",
    "RuntimeContextInfo",
]
