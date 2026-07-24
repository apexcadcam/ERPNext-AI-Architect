"""`ExecutionContext` — Sprint 5 Architecture Package §11, extended by
Sprint 6 Architecture Package §18 (ADR Candidate C).

The Executor's complete, read-only input bundle, mirroring `planning.
context.PlanningContext`'s own "complete, immutable, read-only input
bundle" shape. Fields are the approved Sprint 5 §11 table, plus one
optional, additive field this Sprint approved: `event_bus`. Sprint 5 left
this deliberately unresolved (see the Sprint 5 Implementation Plan's own
Planning Notes and the "Implementation Plan should not extend the approved
architecture" review comment) — `runtime.event_bus` (Sprint 6 ADR
Candidate B) is what finally gave this field something real to wire to.
`event_bus: EventBus | None = None` is optional and defaulted: every
`ExecutionContext(...)` construction that predates this Sprint remains
valid unchanged. `execution/connector_invoker.py`'s
`RegistryConnectorInvoker` still publishes nothing — `ConnectorInvoked`/
`Succeeded`/`Failed` remain a separate, still-undecided question,
deliberately not folded into this same extension (Sprint 6 Architecture
Package §18, ADR Candidate C's own Consequence paragraph).

Of the required-vs-optional fields, only `rollback_strategy` and (now)
`event_bus` default — §19's own approved text explicitly states
"`ExecutionContext.rollback_strategy` defaults to
`UnsupportedRollbackStrategy`," and `event_bus`'s own default of `None`
matches the same "safe to omit" shape. `confirmation_provider` and
`cancellation_token` are left **required**, not defaulted, even though
§9.4 separately calls `DenyAllConfirmationProvider` "the safest possible
default" — that sentence describes the reference *implementation*, not a
stated default for this field specifically, and inferring one here would
be the same kind of unapproved extension the "Implementation Plan should
not extend the approved architecture" review comment already flagged once
this phase. A caller must supply both explicitly.

`ExecutionContext` never carries a `GraphReader`. Every fact the Knowledge
Graph contributed already went into the `Plan` at planning time — Execution
has no legitimate reason to re-consult it, and no field exists through
which it could.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planning.contract import RuntimeContextInfo
from runtime.events.bus import EventBus

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider
from execution.connector_invoker import ConnectorInvoker
from execution.rollback import RollbackStrategy, UnsupportedRollbackStrategy


class ExecutionContext(BaseModel):
    """Assembled by a caller outside `execution/`'s own package boundary
    (a composition-root concern, the same kind Sprint 4's own §6.1 named
    for `PlanningContext`) — nothing in this phase constructs one itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    connector_invoker: ConnectorInvoker
    confirmation_provider: ConfirmationProvider
    rollback_strategy: RollbackStrategy = Field(default_factory=UnsupportedRollbackStrategy)
    runtime_context: RuntimeContextInfo
    correlation_id: str = Field(min_length=1)
    cancellation_token: CancellationToken
    #: Sprint 6 Architecture Package §18, ADR Candidate C. `ExecutionEngine`
    #: treats this as a publish-only collaboration -- the only method it
    #: ever calls on it is `publish()` -- even though `EventBus` itself
    #: exposes more (see execution/engine.py's own docstring).
    event_bus: EventBus | None = None
