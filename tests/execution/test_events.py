"""Tests for the Execution Engine's event-type identifiers
(Sprint 5 Architecture Package §21.1).

No publish-time behavior is tested because none exists yet — `execution/`
defines the nine event_type identifiers only, per this phase's own scope;
publication is a later phase's concern (`ExecutionEngine`, via
`ExecutionContext.event_bus`).
"""

from __future__ import annotations

from runtime.events.bus import Event, EventBus

from execution.events import (
    EXECUTION_CANCELLED,
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
    EXECUTION_STARTED,
    STEP_AWAITING_CONFIRMATION,
    STEP_FAILED,
    STEP_SKIPPED,
    STEP_STARTED,
    STEP_SUCCEEDED,
)

_ALL = (
    EXECUTION_STARTED,
    STEP_STARTED,
    STEP_AWAITING_CONFIRMATION,
    STEP_SUCCEEDED,
    STEP_FAILED,
    STEP_SKIPPED,
    EXECUTION_COMPLETED,
    EXECUTION_CANCELLED,
    EXECUTION_FAILED,
)


def test_every_event_identifier_is_a_distinct_non_empty_string() -> None:
    assert len(set(_ALL)) == 9
    assert all(isinstance(identifier, str) and identifier for identifier in _ALL)


def test_event_identifiers_match_the_nine_names_the_architecture_package_specifies() -> None:
    assert EXECUTION_STARTED == "ExecutionStarted"
    assert STEP_STARTED == "StepStarted"
    assert STEP_AWAITING_CONFIRMATION == "StepAwaitingConfirmation"
    assert STEP_SUCCEEDED == "StepSucceeded"
    assert STEP_FAILED == "StepFailed"
    assert STEP_SKIPPED == "StepSkipped"
    assert EXECUTION_COMPLETED == "ExecutionCompleted"
    assert EXECUTION_CANCELLED == "ExecutionCancelled"
    assert EXECUTION_FAILED == "ExecutionFailed"


def test_event_identifiers_construct_a_real_event_via_the_existing_event_model() -> None:
    event = Event(event_type=EXECUTION_STARTED, payload={"execution_run_id": "R-1"}, emitted_by="execution")
    assert event.event_type == EXECUTION_STARTED
    assert event.payload == {"execution_run_id": "R-1"}


def test_event_identifiers_are_routable_through_a_real_event_bus() -> None:
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(STEP_SUCCEEDED, received.append)

    delivered_to = bus.publish(
        Event(event_type=STEP_SUCCEEDED, payload={"step_id": "S-1"}, emitted_by="execution")
    )

    assert delivered_to == 1
    bus.shutdown()
