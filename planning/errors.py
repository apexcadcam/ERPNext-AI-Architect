"""Shared Planning Engine exception hierarchy.

Mirrors `integration/errors.py` and `secrets_management/errors.py`'s
established discipline this project has used for every package since
Sprint 3: each new package owns its own narrow exceptions, subclassing a
single trailing-underscore base rather than overloading `runtime.errors.
RuntimeError_` or another package's hierarchy, even where the failure
category is conceptually similar.
"""

from __future__ import annotations


class PlanningError_(Exception):
    """Base class for every error raised by the Planning Engine.

    Named with a trailing underscore for the same reason
    `runtime.errors.RuntimeError_` is: to avoid shadowing a built-in-shaped
    name at a glance.
    """


class GoalDefinitionError(PlanningError_):
    """A `Goal` is malformed or cannot be planned toward as given — e.g.
    the caller supplied no way to express intent at all. Raised before any
    planning logic runs (a later phase's `PlanningEngine.create_plan`
    concern; this phase defines only the error type itself).
    """


class PlanningContextError(PlanningError_):
    """A `PlanningContext` (a later phase's concern — not defined in this
    phase) is missing a required input or carries a malformed one.
    """


class NoUsableCapabilityError(PlanningError_):
    """No available capability serves a `Goal`'s declared
    `desired_capabilities`. Named distinctly from `runtime.errors.
    CapabilityResolutionError` (the Dependency Injection Container's own,
    unrelated concept) to avoid confusing the two.
    """


class PlannerStrategyError(PlanningError_):
    """A configured `PlannerStrategy` (a later phase's concern — not
    defined in this phase) raised, or returned something structurally
    unusable, while proposing a candidate `Plan`.
    """


class PlanValidationError(PlanningError_):
    """A candidate `Plan` failed one or more `validate_plan` rules (a later
    phase's concern — not defined in this phase). Carries every violation
    found, never only the first, mirroring `integration.errors.
    ConnectorValidationError`'s identical "report all, not just the first"
    discipline.
    """
