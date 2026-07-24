"""Sprint 4, Phase 6, §5 — Determinism.

Repeated runs with an identical `Goal`, `PlanningContext`, and
`PlannerStrategy` must produce identical `Plan`s — verified both by model
equality and by byte-equivalent `model_dump_json()` output.
"""

from __future__ import annotations

from planning.contract import Goal
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import RuleBasedPlannerStrategy


def test_repeated_runs_produce_equal_plans(goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    first = engine.create_plan(goal, context)
    second = engine.create_plan(goal, context)
    third = engine.create_plan(goal, context)

    assert first == second == third


def test_repeated_runs_produce_byte_equivalent_model_dumps(goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    first = engine.create_plan(goal, context)
    second = engine.create_plan(goal, context)

    assert first.model_dump_json() == second.model_dump_json()


def test_repeated_runs_across_separate_engines_and_strategy_instances_are_identical(
    goal: Goal, context: PlanningContext
) -> None:
    # Not the same PlanningEngine/PlannerStrategy object -- fresh instances
    # each time, still deterministic given the same (goal, context).
    first_engine = PlanningEngine()
    first_engine.register_strategy(RuleBasedPlannerStrategy())
    first = first_engine.create_plan(goal, context)

    second_engine = PlanningEngine()
    second_engine.register_strategy(RuleBasedPlannerStrategy())
    second = second_engine.create_plan(goal, context)

    assert first.model_dump_json() == second.model_dump_json()


def test_determinism_holds_for_the_empty_plan_case(empty_goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    first = engine.create_plan(empty_goal, context)
    second = engine.create_plan(empty_goal, context)

    assert first.model_dump_json() == second.model_dump_json()
