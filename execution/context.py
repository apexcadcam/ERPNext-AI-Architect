"""`ExecutionContext` — Sprint 5 Architecture Package §11.

The Executor's complete, read-only input bundle, mirroring `planning.
context.PlanningContext`'s own "complete, immutable, read-only input
bundle" shape. Fields are exactly the approved §11 table — **no
`event_bus` field**: that addition is a still-open, unresolved architecture
clarification (see the Sprint 5 Implementation Plan's own Planning Notes
and the "Implementation Plan should not extend the approved architecture"
review comment) and this phase does not add it on its own authority.
Consequently, `execution/connector_invoker.py`'s `RegistryConnectorInvoker`
has no way to publish `ConnectorInvoked`/`Succeeded`/`Failed`, and nothing
in this phase publishes `execution/events.py`'s own identifiers either —
both remain contingent on that clarification being resolved in a later
phase.

Only `rollback_strategy` defaults — §19's own approved text explicitly
states "`ExecutionContext.rollback_strategy` defaults to
`UnsupportedRollbackStrategy`." `confirmation_provider` and
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
