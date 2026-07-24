"""Sprint 4, Phase 6, §1 — End-to-End Planning Flow.

Goal -> PlanningEngine -> PlannerStrategy -> validate_plan -> Plan, using
the real, already-frozen Phase 1-5 code as-is. Both a non-empty and an
empty resulting `Plan` are verified.
"""

from __future__ import annotations

from planning.contract import Goal
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import RuleBasedPlannerStrategy


def test_end_to_end_flow_produces_a_non_empty_validated_plan(goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    plan = engine.create_plan(goal, context)

    assert plan.goal_id == goal.goal_id
    assert [step.capability for step in plan.steps] == ["filesystem.read_text", "filesystem.write_text"]
    assert plan.steps[1].requires_confirmation is True  # write_text's descriptor requires it


def test_end_to_end_flow_produces_a_valid_empty_plan(empty_goal: Goal, context: PlanningContext) -> None:
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    plan = engine.create_plan(empty_goal, context)

    assert plan.goal_id == empty_goal.goal_id
    assert plan.steps == ()


def test_end_to_end_flow_with_no_available_capabilities_produces_an_empty_plan(goal: Goal) -> None:
    from knowledge.graph import InMemoryGraphStore

    from planning.contract import RuntimeContextInfo

    context_with_nothing_available = PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    plan = engine.create_plan(goal, context_with_nothing_available)

    assert plan.steps == ()
