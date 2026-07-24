"""Tests for the Planning Engine's event-type identifiers
(approved Sprint 4 Architecture Package §3.1, §7 workflow §6.1-§6.3
citations for PlanningStarted/PlanCreated/PlanValidationFailed/
PlanningFailed).

No publish-time behavior is tested because none exists yet — `planning/`
defines the four event_type identifiers only, per this phase's own scope.
"""

from __future__ import annotations

from runtime.events.bus import Event, EventBus

from planning.events import PLAN_CREATED, PLAN_VALIDATION_FAILED, PLANNING_FAILED, PLANNING_STARTED


def test_every_event_identifier_is_a_distinct_non_empty_string() -> None:
    identifiers = {PLANNING_STARTED, PLAN_CREATED, PLAN_VALIDATION_FAILED, PLANNING_FAILED}
    assert len(identifiers) == 4
    assert all(isinstance(identifier, str) and identifier for identifier in identifiers)


def test_event_identifiers_match_the_four_names_the_architecture_package_specifies() -> None:
    assert PLANNING_STARTED == "PlanningStarted"
    assert PLAN_CREATED == "PlanCreated"
    assert PLAN_VALIDATION_FAILED == "PlanValidationFailed"
    assert PLANNING_FAILED == "PlanningFailed"


def test_event_identifiers_construct_a_real_event_via_the_existing_event_model() -> None:
    # Proves these identifiers work as ordinary event_type values against
    # the project's real, existing runtime.events.bus.Event/EventBus — no
    # new event framework, exactly as required.
    event = Event(event_type=PLANNING_STARTED, payload={"goal_id": "G-1"}, emitted_by="planning")
    assert event.event_type == PLANNING_STARTED
    assert event.payload == {"goal_id": "G-1"}


def test_event_identifiers_are_routable_through_a_real_event_bus() -> None:
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(PLAN_CREATED, received.append)

    delivered_to = bus.publish(
        Event(event_type=PLAN_CREATED, payload={"plan_id": "P-1"}, emitted_by="planning")
    )

    assert delivered_to == 1
    bus.shutdown()
