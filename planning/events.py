"""Planning Engine event-type identifiers.

Follows this project's existing Event model exactly (`runtime.events.bus.
Event`: a single generic, frozen dataclass keyed by a plain `event_type`
string, with an opaque `payload` — see `knowledge/validation/gates.py` and
`knowledge/extraction/stage.py` for the established, ad hoc, inline
`Event(event_type="...", payload={...})` construction pattern this project
already uses everywhere). No new event framework, no `Event` subclasses, no
publish-time behavior: this phase defines only the four canonical
`event_type` values a later phase's `PlanningEngine` (not built here) will
construct and publish `Event` instances for.

Expected `payload` shape for each, for that later phase's reference —
descriptive only, not enforced by anything in this module:

    PLANNING_STARTED:         {"goal_id": str}
    PLAN_CREATED:              {"goal_id": str, "plan_id": str, "step_count": int}
    PLAN_VALIDATION_FAILED:    {"goal_id": str, "violations": list[str]}
    PLANNING_FAILED:           {"goal_id": str, "error_type": str, "detail": str}

Every publication also carries `Event.correlation_id`, per
`docs/runtime/LOGGING_AND_OBSERVABILITY.md §2`'s existing correlation
mechanism, reused rather than reinvented.
"""

from __future__ import annotations

#: Published at the start of a `PlanningEngine.create_plan()` call, before
#: any capability resolution or strategy delegation runs.
PLANNING_STARTED = "PlanningStarted"

#: Published once a candidate `Plan` has passed `validate_plan` and is
#: about to be returned to the caller.
PLAN_CREATED = "PlanCreated"

#: Published when a candidate `Plan` fails one or more `validate_plan`
#: rules — no `Plan` is returned to the caller when this fires.
PLAN_VALIDATION_FAILED = "PlanValidationFailed"

#: Published when planning fails for any reason other than a validation
#: failure — a malformed `Goal`/`PlanningContext`, no usable capability, or
#: a `PlannerStrategy` raising.
PLANNING_FAILED = "PlanningFailed"
