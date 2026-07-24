"""Tests for `StepScheduler` (Sprint 5 Architecture Package §7, §24's
Scheduling Tie-Breaking subsection).
"""

from __future__ import annotations

from planning.contract import Plan, PlanStep

from execution.scheduler import StepScheduler


def _plan(*steps: PlanStep) -> Plan:
    return Plan(
        plan_id="P-1", goal_id="G-1", steps=steps, created_at="2026-01-01T00:00:00Z", strategy_name="test"
    )


def _step(step_id: str, *, depends_on: tuple[str, ...] = ()) -> PlanStep:
    return PlanStep(
        step_id=step_id, capability="filesystem.read_text", depends_on=depends_on, requires_confirmation=False
    )


def test_empty_plan_orders_to_nothing() -> None:
    assert StepScheduler().order(_plan()) == ()


def test_single_step_orders_to_itself() -> None:
    step = _step("S-1")
    assert StepScheduler().order(_plan(step)) == (step,)


def test_linear_chain_preserves_dependency_order() -> None:
    a = _step("A")
    b = _step("B", depends_on=("A",))
    c = _step("C", depends_on=("B",))

    result = StepScheduler().order(_plan(c, b, a))  # deliberately out of dependency order in the Plan

    assert [step.step_id for step in result] == ["A", "B", "C"]


def test_two_independent_roots_tie_break_by_plan_order() -> None:
    a = _step("A")
    b = _step("B")

    result_ab = StepScheduler().order(_plan(a, b))
    result_ba = StepScheduler().order(_plan(b, a))

    assert [step.step_id for step in result_ab] == ["A", "B"]
    assert [step.step_id for step in result_ba] == ["B", "A"]


def test_diamond_shape_orders_correctly() -> None:
    a = _step("A")
    b = _step("B", depends_on=("A",))
    c = _step("C", depends_on=("A",))
    d = _step("D", depends_on=("B", "C"))

    result = StepScheduler().order(_plan(a, b, c, d))

    assert [step.step_id for step in result] == ["A", "B", "C", "D"]


def test_ordering_is_never_derived_from_a_sets_iteration_order() -> None:
    # Many independent roots -- a naive set-based scheduler could produce a
    # different order across runs; the Plan-order tie-break must not.
    steps = tuple(_step(f"S-{i}") for i in range(20))
    plan = _plan(*steps)

    first = StepScheduler().order(plan)
    second = StepScheduler().order(plan)

    assert [s.step_id for s in first] == [s.step_id for s in second] == [f"S-{i}" for i in range(20)]


def test_result_contains_every_step_exactly_once() -> None:
    a = _step("A")
    b = _step("B", depends_on=("A",))
    c = _step("C", depends_on=("A",))

    result = StepScheduler().order(_plan(a, b, c))

    assert len(result) == 3
    assert {step.step_id for step in result} == {"A", "B", "C"}
