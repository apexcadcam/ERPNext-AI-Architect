"""`PlanningContext` — the Planner's complete, read-only input bundle.

Implements the approved Sprint 4 Architecture Package §5.2: exactly the
four approved fields (`graph`, `available_capabilities`, `runtime_context`,
`correlation_id`), immutable, with no methods, no cross-field validation,
and no helper logic — the same "pure data, nothing else" discipline
`planning/contract.py`'s Phase 1 models already establish, extended here to
the one remaining input shape the architecture package defines.

Per ADR-0010, `available_capabilities` is a plain-data `CapabilityDescriptor`
snapshot, never a live `integration.registry.ConnectorRegistry` reference —
`planning/` has no import of `integration/` anywhere, including here. Per
ADR-0011, `graph` is typed as `GraphReader` (§5.7), never the full
`knowledge.graph.GraphStoreAdapter` — no write method is reachable through
a `PlanningContext`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planning.contract import CapabilityDescriptor, RuntimeContextInfo
from planning.graph_reader import GraphReader


class PlanningContext(BaseModel):
    """Assembled by a caller outside `planning/`'s own package boundary
    (the architecture package's own §6.1 names this a composition-root
    concern) — nothing in this phase constructs one itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    graph: GraphReader
    available_capabilities: tuple[CapabilityDescriptor, ...] = ()
    runtime_context: RuntimeContextInfo
    correlation_id: str = Field(min_length=1)
