"""Tests for the Event Bus (docs/runtime/EVENT_BUS.md)."""

from __future__ import annotations

import threading
import time

import pytest

from runtime.events.bus import Event, EventBus, EventBusBackpressureError, OverflowPolicy


def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.01) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("condition not met before timeout")


@pytest.fixture
def bus():
    b = EventBus(default_queue_size=100)
    yield b
    b.shutdown()


def test_publish_delivers_to_a_matching_subscriber(bus: EventBus) -> None:
    received: list[dict] = []
    bus.subscribe("Thing", lambda e: received.append(e.payload))

    count = bus.publish(Event(event_type="Thing", payload={"x": 1}, emitted_by="test"))

    assert count == 1
    _wait_until(lambda: received == [{"x": 1}])


def test_publish_with_no_subscribers_returns_zero_and_does_not_raise(bus: EventBus) -> None:
    assert bus.publish(Event(event_type="Nobody", emitted_by="test")) == 0


def test_the_bus_never_routes_across_different_event_types(bus: EventBus) -> None:
    received: list[str] = []
    bus.subscribe("TypeA", lambda e: received.append(e.event_type))

    bus.publish(Event(event_type="TypeB", emitted_by="test"))
    time.sleep(0.1)

    assert received == []


def test_events_are_delivered_in_publish_order_within_one_subscription(bus: EventBus) -> None:
    received: list[int] = []
    bus.subscribe("Ordered", lambda e: received.append(e.payload["i"]))

    for i in range(20):
        bus.publish(Event(event_type="Ordered", payload={"i": i}, emitted_by="test"))

    _wait_until(lambda: len(received) == 20)
    assert received == list(range(20))


def test_multiple_subscribers_to_the_same_event_type_each_receive_it(bus: EventBus) -> None:
    a_received: list[int] = []
    b_received: list[int] = []
    bus.subscribe("Fanout", lambda e: a_received.append(1))
    bus.subscribe("Fanout", lambda e: b_received.append(1))

    bus.publish(Event(event_type="Fanout", emitted_by="test"))

    _wait_until(lambda: len(a_received) == 1 and len(b_received) == 1)


def test_a_handler_that_raises_does_not_stop_the_subscription(bus: EventBus) -> None:
    received: list[int] = []

    def flaky_handler(event: Event) -> None:
        if event.payload["i"] == 0:
            raise ValueError("boom")
        received.append(event.payload["i"])

    sub = bus.subscribe("Flaky", flaky_handler)
    bus.publish(Event(event_type="Flaky", payload={"i": 0}, emitted_by="test"))
    bus.publish(Event(event_type="Flaky", payload={"i": 1}, emitted_by="test"))

    _wait_until(lambda: received == [1])
    _wait_until(lambda: bus.stats()[sub.subscription_id].handler_errors == 1)


def test_drop_oldest_policy_bounds_queue_depth_under_overflow(bus: EventBus) -> None:
    gate = threading.Event()
    sub = bus.subscribe("Metric", lambda e: gate.wait(), overflow_policy=OverflowPolicy.DROP_OLDEST, queue_size=3)

    for i in range(20):
        bus.publish(Event(event_type="Metric", payload={"i": i}, emitted_by="test"))

    stats = bus.stats()[sub.subscription_id]
    assert stats.queue_depth <= 3
    assert stats.dropped > 0
    gate.set()


def test_block_policy_raises_once_queue_stays_full_past_timeout(bus: EventBus) -> None:
    gate = threading.Event()
    bus.subscribe(
        "Critical",
        lambda e: gate.wait(),
        overflow_policy=OverflowPolicy.BLOCK,
        queue_size=1,
        block_timeout_seconds=0.2,
    )

    bus.publish(Event(event_type="Critical", emitted_by="test"))  # picked up by the (blocked) handler thread
    time.sleep(0.05)
    bus.publish(Event(event_type="Critical", emitted_by="test"))  # fills the queue (size 1)

    with pytest.raises(EventBusBackpressureError):
        bus.publish(Event(event_type="Critical", emitted_by="test"))

    gate.set()


def test_unsubscribe_stops_further_delivery(bus: EventBus) -> None:
    received: list[int] = []
    sub = bus.subscribe("Thing", lambda e: received.append(1))
    bus.unsubscribe(sub)

    count = bus.publish(Event(event_type="Thing", emitted_by="test"))

    assert count == 0
    time.sleep(0.1)
    assert received == []
