"""`PlanningEngine` — the orchestration host for one `create_plan()` call.

Implements the approved Sprint 4 Architecture Package §3.2/§4.1's
`PlanningEngine`, scoped exactly to this phase's own Responsibilities list:

  1. Accept a `Goal` + `PlanningContext`.
  2. Resolve the configured strategy (a placeholder here — real
     Configuration-System-driven selection, §9.2 of the architecture
     package, is explicitly out of this phase's scope).
  3. Invoke the strategy.
  4. Invoke `validate_plan()` (Phase 3, unmodified).
  5. Return the validated `Plan`.

Nothing else. `PlanningEngine` contains no planning logic, no graph logic,
no capability-resolution logic, and no validation logic of its own — it
delegates (3) to whatever strategy is registered and (4) to
`planning.validation.validate_plan`, unmodified. It never imports
`integration/` or `secrets_management/`, never touches
`PlanningContext.graph`, and never mutates the `Goal`/`PlanningContext` it
is given.

**On `PlannerStrategy`:** the architecture package's §3.3/§4.2 describes a
`PlannerStrategy` "contract" — a swappable reasoning core. This phase's own
scope explicitly forbids "PlannerStrategy concrete implementations" and
restricts this phase to creating `engine.py` alone (no `planning/strategy.py`).
`PlannerStrategy` is therefore defined here as a plain
`Callable[[Goal, PlanningContext], Plan]` type alias — a fixed contract (a
function signature), not a class with anything to subclass or "implement."
This satisfies the architecture package's own description without adding a
class hierarchy this phase has no mandate to build; a future phase may
promote it to a formal `Protocol`/ABC in its own dedicated file without
changing `PlanningEngine`'s public API, since any callable object (including
one implementing `__call__`) already satisfies this type.

**On events:** this phase's Responsibilities list is a closed, five-item
list that does not mention publishing `PlanningStarted`/`PlanCreated`/
`PlanValidationFailed`/`PlanningFailed` (Phase 1, `planning/events.py`).
Event publication is therefore deliberately not wired into
`PlanningEngine` in this phase — not silently dropped, but out of this
phase's own stated scope. See this phase's deliverables notes.
"""

from __future__ import annotations

from collections.abc import Callable

from planning.contract import Goal, Plan
from planning.context import PlanningContext
from planning.errors import PlannerStrategyError
from planning.validation import validate_plan

#: See this module's own docstring for why this is a Callable type alias
#: rather than a formal class.
PlannerStrategy = Callable[[Goal, PlanningContext], Plan]


class PlanningEngine:
    """Orchestrates exactly one `create_plan()` call end to end. Contains
    no planning logic of its own — every actual planning decision is
    delegated to whichever `PlannerStrategy` is registered.
    """

    def __init__(self) -> None:
        self._strategy: PlannerStrategy | None = None

    def register_strategy(self, strategy: PlannerStrategy, *, override: bool = False) -> None:
        """Wires `strategy` in as the currently-active `PlannerStrategy`.
        Mirrors `secrets_management.resolver.SecretsResolver.register()`'s
        exact override-guarded shape: raises if a strategy is already
        registered, unless `override=True`.
        """

        if self._strategy is not None and not override:
            raise PlannerStrategyError(
                "a PlannerStrategy is already registered (pass override=True to replace it)"
            )
        self._strategy = strategy

    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        """Runs this phase's five-step orchestration exactly. Raises
        `PlannerStrategyError` if no strategy is configured, if the
        configured strategy raises, or if it returns something that is not
        a `Plan`; raises `PlanValidationError` (from `validate_plan`,
        unmodified) if the candidate `Plan` is structurally invalid.
        Neither `goal` nor `context` is ever mutated — both are frozen,
        pydantic models, and this method only ever reads from them or
        passes them through.
        """

        strategy = self._resolve_strategy()
        candidate = self._invoke_strategy(strategy, goal, context)
        validate_plan(candidate, context)
        return candidate

    def _resolve_strategy(self) -> PlannerStrategy:
        """Step 2 — a placeholder: returns whichever strategy was wired in
        via `register_strategy()`. Real, Configuration-System-driven
        strategy selection (the architecture package's §9.2) is explicitly
        out of this phase's scope.
        """

        if self._strategy is None:
            raise PlannerStrategyError("no PlannerStrategy is configured")
        return self._strategy

    def _invoke_strategy(self, strategy: PlannerStrategy, goal: Goal, context: PlanningContext) -> Plan:
        """Step 3. Wraps whatever the strategy raises as `PlannerStrategyError`,
        mirroring `integration.registry.ConnectorRegistry.instantiate()`'s
        identical "factory raised" wrapping discipline — and does the same
        for a strategy that returns something structurally unusable.
        """

        try:
            candidate = strategy(goal, context)
        except Exception as exc:
            raise PlannerStrategyError(f"PlannerStrategy raised while creating a plan: {exc}") from exc

        if not isinstance(candidate, Plan):
            raise PlannerStrategyError(
                f"PlannerStrategy returned {type(candidate).__name__}, which is not a Plan"
            )
        return candidate
