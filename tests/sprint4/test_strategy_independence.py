"""Sprint 4, Phase 6, §2 — Strategy Independence.

A second, completely independent `PlannerStrategy` implementation, defined
only here (never added to `planning/`), with deliberately different
internal logic from `RuleBasedPlannerStrategy` — proving `PlanningEngine`
depends only on the `PlannerStrategy` contract, not on anything specific to
the one reference implementation Phase 5 shipped.
"""

from __future__ import annotations

from planning.contract import Goal, Plan, PlanStep
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import PlannerStrategy


class AllAvailableCapabilitiesStrategy(PlannerStrategy):
    """Deliberately the opposite algorithm from `RuleBasedPlannerStrategy`:
    ignores `goal.desired_capabilities` entirely and emits one step per
    capability in `context.available_capabilities`, in that tuple's own
    order. A real strategy would never behave this way (it ignores the
    Goal!) — its only purpose is to be *unmistakably* independent of
    `RuleBasedPlannerStrategy`'s own decision logic, while still honoring
    the same rules (`PlannerStrategy` contract, no graph access, no
    mutation, no validate_plan call) every strategy must.
    """

    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        steps = tuple(
            PlanStep(
                step_id=f"all-{index}",
                capability=descriptor.capability,
                requires_confirmation=descriptor.requires_confirmation,
                rationale="emitted for every available capability, regardless of the goal",
            )
            for index, descriptor in enumerate(context.available_capabilities, start=1)
        )
        return Plan(
            plan_id=f"all-caps-plan-for-{goal.goal_id}",
            goal_id=goal.goal_id,
            steps=steps,
            created_at="1970-01-01T00:00:00Z",
            strategy_name="all_available_capabilities",
        )


def test_planning_engine_works_with_a_second_independent_strategy(
    goal: Goal, context: PlanningContext
) -> None:
    engine = PlanningEngine()
    engine.register_strategy(AllAvailableCapabilitiesStrategy())

    plan = engine.create_plan(goal, context)

    # Proves the *strategy's own* decision logic drove the result, not
    # PlanningEngine — three steps (one per available capability), not two
    # (which is what the same `goal`/`context` produces with
    # RuleBasedPlannerStrategy, per test_end_to_end_flow.py).
    assert [step.capability for step in plan.steps] == [
        "filesystem.read_text",
        "filesystem.write_text",
        "filesystem.list_directory",
    ]


def test_second_strategys_plan_still_passes_validate_plan_through_the_engine(
    goal: Goal, context: PlanningContext
) -> None:
    # If this strategy's output were invalid, PlanningEngine would raise --
    # it doesn't, proving validate_plan (Phase 3) applies uniformly
    # regardless of which strategy produced the candidate Plan.
    engine = PlanningEngine()
    engine.register_strategy(AllAvailableCapabilitiesStrategy())

    plan = engine.create_plan(goal, context)  # must not raise

    assert len(plan.steps) == 3


def test_second_strategy_satisfies_the_planner_strategy_contract() -> None:
    assert isinstance(AllAvailableCapabilitiesStrategy(), PlannerStrategy)
