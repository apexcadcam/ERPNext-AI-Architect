"""Tests for the Integration Layer's event-type identifiers
(Sprint 5 Phase 1, closing `ADR-0009`'s M3 finding).

No publish-time behavior is tested here because none happens in
`integration/` — per the Sprint 5 Implementation Plan's own Planning Notes,
publication is Phase 3's `ConnectorInvoker`'s responsibility, not this
package's; `integration/events.py` defines the three `event_type`
identifiers only.
"""

from __future__ import annotations

from runtime.events.bus import Event, EventBus

from integration.events import CONNECTOR_FAILED, CONNECTOR_INVOKED, CONNECTOR_SUCCEEDED


def test_every_event_identifier_is_a_distinct_non_empty_string() -> None:
    identifiers = {CONNECTOR_INVOKED, CONNECTOR_SUCCEEDED, CONNECTOR_FAILED}
    assert len(identifiers) == 3
    assert all(isinstance(identifier, str) and identifier for identifier in identifiers)


def test_event_identifiers_match_the_three_names_sprint3_architecture_package_names() -> None:
    assert CONNECTOR_INVOKED == "ConnectorInvoked"
    assert CONNECTOR_SUCCEEDED == "ConnectorSucceeded"
    assert CONNECTOR_FAILED == "ConnectorFailed"


def test_event_identifiers_construct_a_real_event_via_the_existing_event_model() -> None:
    # Proves these identifiers work as ordinary event_type values against
    # the project's real, existing runtime.events.bus.Event/EventBus — no
    # new event framework, exactly as planning/events.py already
    # established for Planning's own events.
    event = Event(
        event_type=CONNECTOR_INVOKED,
        payload={"connector_id": "filesystem", "operation": "filesystem.read_text"},
        emitted_by="integration",
    )
    assert event.event_type == CONNECTOR_INVOKED
    assert event.payload["connector_id"] == "filesystem"


def test_event_identifiers_are_routable_through_a_real_event_bus() -> None:
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(CONNECTOR_SUCCEEDED, received.append)

    delivered_to = bus.publish(
        Event(
            event_type=CONNECTOR_SUCCEEDED, payload={"connector_id": "filesystem"}, emitted_by="integration"
        )
    )

    assert delivered_to == 1
    bus.shutdown()
