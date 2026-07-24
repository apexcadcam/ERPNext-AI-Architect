"""Sprint 4 Planning Engine — foundational data models.

Implements the approved Sprint 4 Architecture Package: `Goal` (§5.1),
`RuntimeContextInfo` (§5.4), `CapabilityDescriptor` (§5.3), `Plan` (§5.5),
and `PlanStep` (§5.6).

Phase 1 scope only: pure, frozen data shapes, nothing else. `PlanningContext`
(§5.2) and `GraphReader` (§5.7) are deliberately not defined here — both are
scoped to a later implementation phase per the architecture package's own
Migration Strategy (step 2), since both concern how the Planner is *called*,
not what its output *is*. No cross-field integrity checks live here either:
referential integrity of a `PlanStep.depends_on` reference and dependency-
cycle rejection are `validate_plan`'s job (Migration Strategy step 3), not
this module's.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Goal(BaseModel):
    """Sprint 4 Architecture Package §5.1. What a caller wants the Planner
    to plan toward. `intent` is opaque to every component built in this
    phase — meaningful only to a future `PlannerStrategy`, not built here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal_id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    desired_capabilities: tuple[str, ...] = ()
    context_refs: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()


class RuntimeContextInfo(BaseModel):
    """Sprint 4 Architecture Package §5.4. Environment/correlation metadata
    only. Never a credential, never a live object reference — no field here
    can carry one, by construction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    environment: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)


class CapabilityDescriptor(BaseModel):
    """Sprint 4 Architecture Package §5.3. A capability's shape, carried as
    plain data — never a live Connector or `ConnectorRegistry` reference.
    Field vocabulary deliberately echoes
    `integration.contract.ConnectorOperation` (kind/idempotent/
    requires_confirmation) without importing it — `planning/` has no import
    of `integration/` anywhere, per the architecture package's ADR-0010.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: str = Field(min_length=1)
    kind: Literal["read", "write"]
    idempotent: bool
    requires_confirmation: bool


class PlanStep(BaseModel):
    """Sprint 4 Architecture Package §5.6. One step in a `Plan`'s dependency
    graph (see the architecture package's ADR-0013 for why a Plan is a DAG
    rather than a flat list).

    `parameters` is an opaque payload, meaningful only to a future executor
    and the connector it will call — mirrors `runtime.events.bus.Event.
    payload`'s existing `dict[str, Any]` shape, including that precedent's
    same known consequence: because `dict` is categorically unhashable in
    Python, a `PlanStep` is not hashable — unconditionally, regardless of
    whether `parameters` is empty — exactly as an `Event` is not either. A
    `Plan` with at least one `PlanStep` inherits the same unhashability; a
    `Plan` with zero steps remains hashable. Disclosed here rather than
    worked around with a bespoke frozen-mapping type this project does not
    otherwise use anywhere.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    rationale: str = ""
    requires_confirmation: bool


class Plan(BaseModel):
    """Sprint 4 Architecture Package §5.5. The Planner's sole output —
    inert, frozen data; nothing in this phase (or the architecture package
    itself) ever executes it. `steps` may be empty: a structurally valid
    "goal already satisfied, nothing to do" plan. Re-planning produces a
    new `Plan` instance; this type is never mutated in place.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str = Field(min_length=1)
    goal_id: str = Field(min_length=1)
    steps: tuple[PlanStep, ...] = ()
    created_at: str = Field(min_length=1)
    strategy_name: str = Field(min_length=1)
