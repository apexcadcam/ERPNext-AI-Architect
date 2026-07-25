"""`GoalOrchestrator` — Sprint 7 Architecture Package §3, §5 (ADR
Candidates A and B).

Orchestrates exactly one `run_goal()` call end to end — mirrors
`PlanningEngine`/`ExecutionEngine`'s own "contains no domain logic of its
own, only delegates" self-description, one layer up: it never re-derives,
filters, reorders, or second-guesses anything either engine returns, and
never mutates a `Goal`/`Plan`/`ExecutionResult` field (§4 invariant 9).

**Construction-time vs. per-call split (ADR Candidate A).** `PlanningEngine`,
`ExecutionEngine`, and the `ConnectorInvoker` are fixed for this
orchestrator's entire lifetime — construction-time collaborators, mirroring
`ADR-0014`'s own identical test applied one level up the stack. Everything
`run_goal()` takes is genuinely per-call: `available_capabilities` and
`graph` cannot be derived from anything Container-resolvable today
(`CapabilityResolver` remains unbuilt, Sprint 7 Architecture Package §1's
own Non-Goal); `confirmation_provider`/`runtime_context`/`correlation_id`
are required, matching `ExecutionContext`'s own identical "no default,
even though a safe one exists" discipline (Sprint 5 §11); `rollback_strategy`/
`cancellation_token`/`event_bus` are optional, mirroring `ExecutionContext`'s
own defaults exactly — `cancellation_token`, omitted, becomes a fresh, real
`CancellationToken()` internally rather than staying `None`, a caller
convenience that does not weaken `ExecutionContext.cancellation_token`'s
own still-required field.

**Never raises for either phase's own domain failure (ADR Candidate B).**
`PlannerStrategyError`/`PlanValidationError` (`planning/errors.py`, frozen)
are caught, narrowly — never a bare `except Exception` — and captured as a
`PlanningFailure` (`orchestration/contract.py`). Any other exception
(including `execution.errors.PlanNotExecutableError`, an engine-internal
precondition violation, not a domain failure — Sprint 5/6's own established
distinction) is not caught here, and propagates, exactly as it already
would from a direct `ExecutionEngine.execute()` call.
"""

from __future__ import annotations

from planning.contract import CapabilityDescriptor, Goal, RuntimeContextInfo
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.errors import PlannerStrategyError, PlanValidationError
from planning.graph_reader import GraphReader
from runtime.events.bus import EventBus

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider
from execution.connector_invoker import ConnectorInvoker
from execution.context import ExecutionContext
from execution.engine import ExecutionEngine
from execution.rollback import RollbackStrategy, UnsupportedRollbackStrategy

from orchestration.contract import GoalRunResult, PlanningFailure


class GoalOrchestrator:
    """Composes exactly one `PlanningEngine` and one `ExecutionEngine`
    into a single `Goal`-to-result call. See `ADR-0014` and this Sprint's
    own ADR Candidate A for why the two engines and the `ConnectorInvoker`
    are constructor arguments rather than `run_goal()` parameters.
    """

    def __init__(
        self,
        planning_engine: PlanningEngine,
        execution_engine: ExecutionEngine,
        connector_invoker: ConnectorInvoker,
    ) -> None:
        self._planning_engine = planning_engine
        self._execution_engine = execution_engine
        self._connector_invoker = connector_invoker

    def run_goal(
        self,
        goal: Goal,
        *,
        graph: GraphReader,
        confirmation_provider: ConfirmationProvider,
        runtime_context: RuntimeContextInfo,
        correlation_id: str,
        available_capabilities: tuple[CapabilityDescriptor, ...] = (),
        rollback_strategy: RollbackStrategy | None = None,
        cancellation_token: CancellationToken | None = None,
        event_bus: EventBus | None = None,
    ) -> GoalRunResult:
        """Plans `goal`, then executes the resulting `Plan` — never
        raising for either phase's own domain failure; see this module's
        own docstring for exactly which exceptions are caught.
        """

        planning_context = PlanningContext(
            graph=graph,
            available_capabilities=available_capabilities,
            runtime_context=runtime_context,
            correlation_id=correlation_id,
        )
        try:
            plan = self._planning_engine.create_plan(goal, planning_context)
        except (PlannerStrategyError, PlanValidationError) as exc:
            return GoalRunResult(
                goal_id=goal.goal_id,
                planning_failure=PlanningFailure(error_type=type(exc).__name__, detail=str(exc)),
            )

        execution_context = ExecutionContext(
            connector_invoker=self._connector_invoker,
            confirmation_provider=confirmation_provider,
            rollback_strategy=rollback_strategy or UnsupportedRollbackStrategy(),
            runtime_context=runtime_context,
            correlation_id=correlation_id,
            cancellation_token=cancellation_token or CancellationToken(),
            event_bus=event_bus,
        )
        result = self._execution_engine.execute(plan, execution_context)
        return GoalRunResult(goal_id=goal.goal_id, plan=plan, execution_result=result, planning_failure=None)
