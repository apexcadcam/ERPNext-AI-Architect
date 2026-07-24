"""Execution Engine event-type identifiers.

Follows `planning/events.py`'s exact convention: plain `event_type` string
constants for `runtime.events.bus.Event`, no new framework. Unlike Planning
Phase 4 (which deliberately deferred event publication since no invocation
path existed yet to make it meaningful), Sprint 5 Architecture Package §21
commits to these being wired in from an early implementation phase — this
phase defines the nine identifiers only; publication itself is
`ExecutionEngine`'s concern (a later phase), via `ExecutionContext.
event_bus`.

Expected payload shape for each, for that later phase's reference —
descriptive only, not enforced by anything in this module:

    EXECUTION_STARTED:            {"execution_run_id", "plan_id", "goal_id"}
    STEP_STARTED:                 {"execution_run_id", "step_id", "attempt"}
    STEP_AWAITING_CONFIRMATION:   {"execution_run_id", "step_id", "capability"}
    STEP_SUCCEEDED:                {"execution_run_id", "step_id"}
    STEP_FAILED:                   {"execution_run_id", "step_id", "detail"}
    STEP_SKIPPED:                  {"execution_run_id", "step_id", "reason"}
    EXECUTION_COMPLETED:          {"execution_run_id", "final_state"}
    EXECUTION_CANCELLED:          {"execution_run_id"}
    EXECUTION_FAILED:             {"execution_run_id", "failed_step_ids"}

Every publication also carries `Event.correlation_id`, threading into the
same correlation mechanism `ConnectorRequest.correlation_id` and
`PlanningContext.correlation_id` already establish.
"""

from __future__ import annotations

#: Published at Intake, before StepScheduler orders the Plan's steps.
EXECUTION_STARTED = "ExecutionStarted"

#: Published immediately before a step's connector call is attempted.
STEP_STARTED = "StepStarted"

#: Published when a step's confirmation gate is reached, before a
#: ConfirmationProvider is consulted.
STEP_AWAITING_CONFIRMATION = "StepAwaitingConfirmation"

#: Published when a step's ConnectorResponse.status is "success" or "partial".
STEP_SUCCEEDED = "StepSucceeded"

#: Published when a step's ConnectorResponse.status is "failure", or its
#: Retry Policy is exhausted.
STEP_FAILED = "StepFailed"

#: Published when a step is skipped for any of the three reasons named in
#: §15.5 — an unmet dependency, a denied confirmation, or a run already
#: under cancellation.
STEP_SKIPPED = "StepSkipped"

#: Published once every step has reached a terminal state and the run
#: itself reaches COMPLETED.
EXECUTION_COMPLETED = "ExecutionCompleted"

#: Published when the run reaches CANCELLED.
EXECUTION_CANCELLED = "ExecutionCancelled"

#: Published when the run reaches FAILED.
EXECUTION_FAILED = "ExecutionFailed"
