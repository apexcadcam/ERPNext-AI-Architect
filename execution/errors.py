"""Shared Execution Engine exception hierarchy.

Mirrors `integration/errors.py`, `secrets_management/errors.py`, and
`planning/errors.py`'s established discipline: each new package owns its
own narrow exceptions, subclassing a single trailing-underscore base rather
than overloading another package's hierarchy, even where the failure
category is conceptually similar.
"""

from __future__ import annotations


class ExecutionError_(Exception):
    """Base class for every error raised by the Execution Engine.

    Named with a trailing underscore for the same reason
    `runtime.errors.RuntimeError_` is: to avoid shadowing a built-in-shaped
    name at a glance.
    """


class PlanNotExecutableError(ExecutionError_):
    """An `ExecutionEngine`-internal Intake precondition violation — a
    defensive, "should never happen given valid inputs" signal, the same
    category `runtime.errors.CapabilityResolutionError` already establishes
    for the Container ("a Runtime defect, not a configuration problem").
    Never raised for runtime capability availability, at any coverage
    level — that is always a per-step outcome (`StepExecutionError`),
    under the dependency-aware best-effort execution model (Sprint 5
    Architecture Package §15.5).
    """


class ConfirmationDeniedError(ExecutionError_):
    """Raised only if a caller invokes a single step's confirmation gate
    directly, outside `ExecutionEngine`'s own skip-on-denial flow. A normal
    run never raises this for a denial — that is recorded as a `SKIPPED`
    step, not thrown (§15.5).
    """


class StepExecutionError(ExecutionError_):
    """Wraps a connector's raised exception or failure response for one
    step, mirroring `planning.errors.PlannerStrategyError`'s "wrap what the
    delegate raised" discipline, one layer down.
    """


class RetryExhaustedError(ExecutionError_):
    """An idempotent operation's declared `max_attempts` was exhausted
    without success.
    """


class ExecutionCancelledError(ExecutionError_):
    """The run was cancelled before completion."""


class RollbackError(ExecutionError_):
    """A rollback pass itself failed."""
