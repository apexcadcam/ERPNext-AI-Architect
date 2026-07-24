"""`CancellationToken` — Sprint 5 Architecture Package §18.

Cooperative and step-granular, not operation-granular: `integration.
lifecycle.ConnectorLifecycle` (frozen) has no interrupt or timeout
primitive, so this token is checked once per step boundary, never mid
-invocation. A step already `RUNNING` always runs to completion.
"""

from __future__ import annotations

import threading


class CancellationToken:
    """A small, run-scoped, thread-safe flag. `request_cancellation()` sets
    it; `is_cancellation_requested` is read, never blocking.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def request_cancellation(self) -> None:
        self._event.set()

    @property
    def is_cancellation_requested(self) -> bool:
        return self._event.is_set()
