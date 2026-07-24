"""Integration Layer event-type identifiers.

Follows `planning/events.py`'s exact convention: plain `event_type` string
constants for `runtime.events.bus.Event`, no new framework. Closes
`ADR-0009`'s M3 finding — these names were previously undeclared because no
invocation path existed to publish them from; Sprint 5 Phase 1 completes
that path (`integration.lifecycle.ConnectorLifecycle.invoke()`).

Publication itself is **not** this module's concern, and does not happen in
`integration/` at all: per the Sprint 5 Implementation Plan's own Planning
Notes, `IntegrationModule` has no `EventBus` reference, and Sprint 5
Architecture Package §21.2 explicitly allows publication to happen in "the
thin dispatch wrapper around" `invoke()` rather than inside it — Sprint 5
Phase 3's `ConnectorInvoker` is that wrapper, and is where these constants
are actually used to call `EventBus.publish()`. They are declared here,
not there, because they name a fact about a Connector invocation, the same
reasoning `planning/events.py` already applies to its own event names.

Expected payload shape for each, for that future caller's reference —
descriptive only, not enforced by anything in this module:

    CONNECTOR_INVOKED:    {"connector_id": str, "operation": str}
    CONNECTOR_SUCCEEDED:  {"connector_id": str, "operation": str}
    CONNECTOR_FAILED:     {"connector_id": str, "operation": str, "diagnostics": str}

Every publication also carries `Event.correlation_id`, threading into the
same correlation mechanism `ConnectorRequest.correlation_id` already
establishes.
"""

from __future__ import annotations

#: Published immediately before a connector's `invoke()` is called.
CONNECTOR_INVOKED = "ConnectorInvoked"

#: Published after `invoke()` returns a `ConnectorResponse` with
#: `status` of `"success"` or `"partial"`.
CONNECTOR_SUCCEEDED = "ConnectorSucceeded"

#: Published after `invoke()` returns `status="failure"`, or raises.
CONNECTOR_FAILED = "ConnectorFailed"
