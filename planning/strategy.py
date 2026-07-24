"""`PlannerStrategy` — the permanent, swappable reasoning-core contract —
and its one reference implementation, `RuleBasedPlannerStrategy`.

Implements the approved Sprint 4 Architecture Package §3.3/§4.2:
`PlannerStrategy` is "one fixed contract, many backends, chosen by
configuration" — the fourth application of this project's own established
pattern (`SecretsBackend`, `GraphStoreAdapter`, `ConnectorLifecycle`).
Modeled as an `ABC` with a single abstract method, mirroring
`integration.lifecycle.ConnectorLifecycle`'s exact shape rather than
`planning.graph_reader.GraphReader`'s structural `Protocol` shape — unlike
`GraphReader` (which had to retroactively match an already-existing,
independently-implemented `GraphStoreAdapter`), no pre-existing
"PlannerStrategy-shaped" object exists anywhere else in the codebase for
this contract to structurally match; every strategy is written *as* a
`PlannerStrategy` from the start, the same reason `ConnectorLifecycle` is
an ABC rather than a `Protocol`.

This replaces the temporary `Callable[[Goal, PlanningContext], Plan]` type
alias `planning/engine.py` defined for itself during Phase 4 (documented
there, at the time, as exactly that: a placeholder pending this phase).
`planning/engine.py` is updated in this same phase to import and use this
permanent contract instead — `PlanningEngine`'s own orchestration logic is
otherwise unchanged.

`RuleBasedPlannerStrategy` is the one, minimal, deterministic reference
implementation named in the architecture package's Migration Strategy
(§11, step 5) — chosen first for the same reason the Filesystem Connector
was chosen first among connectors in Sprint 3: lowest risk, no external
dependency, proves the framework end to end. It is deliberately not
intelligent: no graph search, no AI, no ERPNext awareness, no heuristics,
no optimization. It reads only `Goal.desired_capabilities` and
`PlanningContext.available_capabilities` — nothing else on either object —
and it never touches `PlanningContext.graph`, never calls `validate_plan`
(that remains `PlanningEngine`'s job), and never publishes an event.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep
from planning.context import PlanningContext


class PlannerStrategy(ABC):
    """The swappable reasoning core `PlanningEngine` delegates to. Exposes
    exactly one method — no configuration logic, no Runtime wiring, no
    additional public surface.
    """

    @abstractmethod
    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        """Proposes a candidate `Plan` for `goal`, given `context`. Must be
        side-effect-free: no I/O, no graph writes, no connector calls — the
        same structural guarantee `PlanningContext.graph` being a
        `GraphReader` already gives every strategy with respect to the
        Knowledge Graph specifically (ADR-0011).
        """


class RuleBasedPlannerStrategy(PlannerStrategy):
    """The reference `PlannerStrategy`: for every capability `goal` desires
    that also appears in `context.available_capabilities`, emits exactly
    one dependency-free `PlanStep`, in `goal.desired_capabilities`'s own
    order. Nothing more — see this module's own docstring.
    """

    #: A fixed, disclosed placeholder rather than a wall-clock timestamp —
    #: using `datetime.now()` here would make `create_plan()` produce a
    #: different `Plan` on every call for the identical `(goal, context)`,
    #: contradicting this Sprint's own "deterministic" design goal and the
    #: "repeated calls produce identical plans" requirement this strategy
    #: is specifically tested against.
    _CREATED_AT_PLACEHOLDER = "1970-01-01T00:00:00Z"
    _STRATEGY_NAME = "rule_based"

    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        capabilities_by_name = {
            descriptor.capability: descriptor for descriptor in context.available_capabilities
        }

        steps: list[PlanStep] = []
        already_planned: set[str] = set()
        for capability in goal.desired_capabilities:
            if capability in already_planned:
                continue
            descriptor = capabilities_by_name.get(capability)
            if descriptor is None:
                continue
            already_planned.add(capability)
            steps.append(self._step_for(descriptor, index=len(steps) + 1))

        return Plan(
            plan_id=f"plan-for-{goal.goal_id}",
            goal_id=goal.goal_id,
            steps=tuple(steps),
            created_at=self._CREATED_AT_PLACEHOLDER,
            strategy_name=self._STRATEGY_NAME,
        )

    def _step_for(self, descriptor: CapabilityDescriptor, *, index: int) -> PlanStep:
        return PlanStep(
            step_id=f"step-{index}",
            capability=descriptor.capability,
            requires_confirmation=descriptor.requires_confirmation,
            rationale=f"goal desires capability '{descriptor.capability}'",
        )
