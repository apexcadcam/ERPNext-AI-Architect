"""Sprint 4, Phase 6, §6 — Contract Stability.

`PlanningEngine` continues to work correctly across multiple, independently
-written `PlannerStrategy` implementations, with no assumption baked in
about `RuleBasedPlannerStrategy` specifically.
"""

from __future__ import annotations

from planning.contract import Goal, Plan
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import PlannerStrategy, RuleBasedPlannerStrategy
from tests.sprint4.test_strategy_independence import AllAvailableCapabilitiesStrategy


class AlwaysEmptyPlanStrategy(PlannerStrategy):
    """A third, trivial `PlannerStrategy`: always returns an empty `Plan`,
    regardless of `goal`/`context`. Used only to widen "multiple
    strategies" beyond two.
    """

    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        return Plan(
            plan_id=f"empty-plan-for-{goal.goal_id}",
            goal_id=goal.goal_id,
            created_at="1970-01-01T00:00:00Z",
            strategy_name="always_empty",
        )


def test_planning_engine_works_with_rule_based_strategy(goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    plan = engine.create_plan(goal, context)

    assert len(plan.steps) == 2


def test_planning_engine_works_with_all_available_capabilities_strategy(
    goal: Goal, context: PlanningContext
) -> None:
    engine = PlanningEngine()
    engine.register_strategy(AllAvailableCapabilitiesStrategy())

    plan = engine.create_plan(goal, context)

    assert len(plan.steps) == 3


def test_planning_engine_works_with_always_empty_plan_strategy(goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(AlwaysEmptyPlanStrategy())

    plan = engine.create_plan(goal, context)

    assert plan.steps == ()


def test_swapping_strategies_on_one_engine_changes_only_the_plan_content(
    goal: Goal, context: PlanningContext
) -> None:
    engine = PlanningEngine()

    engine.register_strategy(RuleBasedPlannerStrategy())
    rule_based_plan = engine.create_plan(goal, context)

    engine.register_strategy(AllAvailableCapabilitiesStrategy(), override=True)
    all_caps_plan = engine.create_plan(goal, context)

    engine.register_strategy(AlwaysEmptyPlanStrategy(), override=True)
    empty_plan = engine.create_plan(goal, context)

    assert len(rule_based_plan.steps) == 2
    assert len(all_caps_plan.steps) == 3
    assert len(empty_plan.steps) == 0
    # PlanningEngine's own contract (goal_id traceability, validity) held
    # for every one of them -- create_plan() never raised.
    for plan in (rule_based_plan, all_caps_plan, empty_plan):
        assert plan.goal_id == goal.goal_id
