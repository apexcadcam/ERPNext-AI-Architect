"""The Planning Engine — Sprint 4, Phase 1.

Implements the approved Sprint 4 Architecture Package's foundational data
models, error hierarchy, and event-type identifiers only. `PlanningEngine`,
`PlannerStrategy`, `CapabilityResolver`, `validate_plan`, `PlanningContext`,
`GraphReader`, and the Runtime module wrapper (`plugins/planning/`) are all
later-phase scope — none of them exist yet, and nothing in this package
imports `integration/`, `secrets_management/`, or any live Runtime
capability.
"""

from __future__ import annotations

from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep, RuntimeContextInfo
from planning.errors import (
    GoalDefinitionError,
    NoUsableCapabilityError,
    PlanningContextError,
    PlanningError_,
    PlannerStrategyError,
    PlanValidationError,
)
from planning.events import PLAN_CREATED, PLAN_VALIDATION_FAILED, PLANNING_FAILED, PLANNING_STARTED

__all__ = [
    "PLANNING_STARTED",
    "PLAN_CREATED",
    "PLAN_VALIDATION_FAILED",
    "PLANNING_FAILED",
    "CapabilityDescriptor",
    "Goal",
    "GoalDefinitionError",
    "NoUsableCapabilityError",
    "Plan",
    "PlanStep",
    "PlanValidationError",
    "PlanningContextError",
    "PlanningError_",
    "PlannerStrategyError",
    "RuntimeContextInfo",
]
