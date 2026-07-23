"""The Event Bus: routes events by topic, interprets none of them.

Implements docs/runtime/EVENT_BUS.md:

  §1 The Bus knows topics, not meaning — publish/subscribe key only on
     `event_type`; payload is opaque.
  §2 Publish/Subscribe — a subscription binds a handler to an event_type.
  §3 Delivery guarantees — at-least-once, ordered within one subscription's
     queue (which is what "per-correlation-id-ordered" reduces to when a
     given correlation_id's events are all published by one logical flow).
  §5 Backpressure — a bounded queue per subscription with an explicit,
     per-subscription overflow policy (`block` vs `drop_oldest`), never a
     bus-wide default silently applied everywhere.

Sprint 1 note: no module publishes or subscribes to a *business* event yet
(EVENT_BUS.md's own `DocumentDiscovered`-style examples all belong to
modules out of this sprint's scope). This module is exercised directly, and
by the Configuration/boot infrastructure, to prove the mechanism itself
works — see docs/runtime/RUNTIME_ARCHITECTURE.md's Sprint 2 backlog note in
the top-level implementation summary for wiring module manifests'
events_published/events_subscribed declarations automatically.
"""

from __future__ import annotations

import contextlib
import enum
import logging
import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class OverflowPolicy(enum.Enum):
    """See EVENT_BUS.md §5."""

    #: Tolerate blocking the publisher (up to `block_timeout_seconds`) rather
    #: than lose an event — for state-transition-class events where a missed
    #: delivery would silently corrupt a subscriber's view of the world.
    BLOCK = "block"
    #: Silently discard the oldest queued event to make room — for
    #: high-frequency telemetry where losing one sample is invisible.
    DROP_OLDEST = "drop_oldest"


class EventBusBackpressureError(Exception):
    """A BLOCK-policy subscription's queue stayed full past its timeout."""


@dataclass(frozen=True)
class Event:
    """See EVENT_BUS.md §1. `payload` is never inspected by the Bus itself."""

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    emitted_by: str = "runtime"
    correlation_id: str | None = None
    pipeline_run_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


EventHandler = Callable[[Event], None]


@dataclass
class _SubscriptionStats:
    delivered: int = 0
    dropped: int = 0
    handler_errors: int = 0


@dataclass(frozen=True)
class SubscriptionStatsView:
    """A point-in-time, read-only snapshot of one subscription's counters —
    what `EventBus.stats()` and, later, `LOGGING_AND_OBSERVABILITY.md`'s
    metrics surface actually report.
    """

    event_type: str
    delivered: int
    dropped: int
    handler_errors: int
    queue_depth: int


class Subscription:
    """One (event_type, handler) binding, with its own bounded queue and
    a dedicated consumer thread — so one slow or misbehaving subscriber can
    never delay delivery to any other subscriber, on any event type.
    """

    def __init__(
        self,
        subscription_id: str,
        event_type: str,
        handler: EventHandler,
        *,
        overflow_policy: OverflowPolicy,
        queue_size: int,
        block_timeout_seconds: float,
    ) -> None:
        self.subscription_id = subscription_id
        self.event_type = event_type
        self.handler = handler
        self.overflow_policy = overflow_policy
        self.block_timeout_seconds = block_timeout_seconds
        self.stats = _SubscriptionStats()

        self._queue: queue.Queue[Event] = queue.Queue(maxsize=queue_size)
        self._stop_requested = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name=f"event-bus-sub-{subscription_id}", daemon=True
        )
        self._thread.start()

    def enqueue(self, event: Event) -> None:
        if self.overflow_policy is OverflowPolicy.BLOCK:
            try:
                self._queue.put(event, block=True, timeout=self.block_timeout_seconds)
            except queue.Full as exc:
                raise EventBusBackpressureError(
                    f"subscription '{self.subscription_id}' (event_type={self.event_type!r}) "
                    f"did not drain within {self.block_timeout_seconds}s"
                ) from exc
        else:  # DROP_OLDEST
            while True:
                try:
                    self._queue.put_nowait(event)
                    return
                except queue.Full:
                    with contextlib.suppress(queue.Empty):
                        self._queue.get_nowait()
                        self.stats.dropped += 1

    def _run(self) -> None:
        while not self._stop_requested.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.handler(event)
                self.stats.delivered += 1
            except Exception:
                self.stats.handler_errors += 1
                logger.exception(
                    "event handler raised",
                    extra={"subscription_id": self.subscription_id, "event_type": self.event_type},
                )
            finally:
                self._queue.task_done()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop_requested.set()
        self._thread.join(timeout=timeout)

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()


class EventBus:
    """Topic-routed publish/subscribe. Holds zero knowledge of what any
    event_type means — see module docstring.
    """

    def __init__(self, *, default_queue_size: int = 1000) -> None:
        self.default_queue_size = default_queue_size
        self._subscriptions: dict[str, list[Subscription]] = {}
        self._lock = threading.Lock()

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        *,
        overflow_policy: OverflowPolicy = OverflowPolicy.BLOCK,
        queue_size: int | None = None,
        block_timeout_seconds: float = 5.0,
    ) -> Subscription:
        subscription = Subscription(
            subscription_id=str(uuid.uuid4()),
            event_type=event_type,
            handler=handler,
            overflow_policy=overflow_policy,
            queue_size=queue_size or self.default_queue_size,
            block_timeout_seconds=block_timeout_seconds,
        )
        with self._lock:
            self._subscriptions.setdefault(event_type, []).append(subscription)
        logger.debug("subscribed", extra={"event_type": event_type, "subscription_id": subscription.subscription_id})
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            bucket = self._subscriptions.get(subscription.event_type, [])
            if subscription in bucket:
                bucket.remove(subscription)
        subscription.stop()

    def publish(self, event: Event) -> int:
        """Route `event` to every subscription bound to its event_type.

        Returns the number of subscriptions the event was enqueued to (0 is
        a valid, unremarkable result per EVENT_BUS.md §2 — not every event
        needs a listener).
        """

        with self._lock:
            targets = list(self._subscriptions.get(event.event_type, ()))
        for subscription in targets:
            subscription.enqueue(event)
        return len(targets)

    def subscription_count(self, event_type: str | None = None) -> int:
        with self._lock:
            if event_type is not None:
                return len(self._subscriptions.get(event_type, ()))
            return sum(len(subs) for subs in self._subscriptions.values())

    def stats(self) -> dict[str, "SubscriptionStatsView"]:
        with self._lock:
            all_subs = [sub for subs in self._subscriptions.values() for sub in subs]
        return {
            sub.subscription_id: SubscriptionStatsView(
                event_type=sub.event_type,
                delivered=sub.stats.delivered,
                dropped=sub.stats.dropped,
                handler_errors=sub.stats.handler_errors,
                queue_depth=sub.queue_depth,
            )
            for sub in all_subs
        }

    def shutdown(self) -> None:
        with self._lock:
            all_subs = [sub for subs in self._subscriptions.values() for sub in subs]
            self._subscriptions.clear()
        for sub in all_subs:
            sub.stop()
