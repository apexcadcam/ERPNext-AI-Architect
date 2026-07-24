"""Sprint 4, Phase 6, §4 — Layer Isolation.

Four specific claims, each verified two ways: a precise AST check (so a
docstring merely *mentioning* "graph" or "validate_plan" can never produce
a false pass — only a real `ast.Attribute`/`ast.Call` node counts), and a
runtime check using `ForbiddenGraph` (a `GraphReader` double whose every
method raises) or `monkeypatch` — proving, not merely asserting, that the
call path in question never actually touches what it must not.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from planning.contract import Goal, Plan, PlanStep
from planning.context import PlanningContext
from planning.engine import PlanningEngine
from planning.strategy import RuleBasedPlannerStrategy
from planning.validation import validate_plan

PLANNING_DIR = Path(__file__).resolve().parents[2] / "planning"


def _attribute_accesses(py_file: Path, attr_name: str) -> list[int]:
    """Line numbers of every `<expr>.<attr_name>` access in `py_file` —
    immune to docstring/comment false positives, since string literals
    never parse as `ast.Attribute` nodes.
    """

    tree = ast.parse((PLANNING_DIR / py_file).read_text(encoding="utf-8"), filename=py_file.name)
    return [
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == attr_name
    ]


def _calls_to(py_file: Path, function_name: str) -> list[int]:
    """Line numbers of every call to a function/method named `function_name`
    in `py_file`."""

    tree = ast.parse((PLANNING_DIR / py_file).read_text(encoding="utf-8"), filename=py_file.name)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = (
            target.id
            if isinstance(target, ast.Name)
            else target.attr
            if isinstance(target, ast.Attribute)
            else None
        )
        if name == function_name:
            lines.append(node.lineno)
    return lines


# -- 1. PlanningEngine never accesses GraphReader directly --------------------------------


def test_engine_source_never_accesses_dot_graph() -> None:
    assert _attribute_accesses(Path("engine.py"), "graph") == []


def test_engine_runtime_never_touches_a_forbidden_graph(
    goal: Goal, forbidden_graph_context: PlanningContext
) -> None:
    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())

    engine.create_plan(goal, forbidden_graph_context)  # must not raise GraphAccessForbidden


# -- 2. RuleBasedPlannerStrategy never calls validate_plan ---------------------------------


def test_strategy_source_never_calls_validate_plan() -> None:
    assert _calls_to(Path("strategy.py"), "validate_plan") == []


def test_strategy_runtime_never_calls_validate_plan(
    goal: Goal, context: PlanningContext, monkeypatch: MonkeyPatch
) -> None:
    def exploding_validate_plan(plan: Plan, ctx: PlanningContext, *, raise_on_failure: bool = True) -> None:
        raise AssertionError("validate_plan must never be called by RuleBasedPlannerStrategy")

    monkeypatch.setattr("planning.strategy.validate_plan", exploding_validate_plan, raising=False)

    RuleBasedPlannerStrategy().create_plan(goal, context)  # must not raise


# -- 3. validate_plan never performs graph traversal -----------------------------------------


def test_validation_source_never_accesses_dot_graph() -> None:
    assert _attribute_accesses(Path("validation.py"), "graph") == []


def test_validation_source_never_calls_traverse() -> None:
    assert _calls_to(Path("validation.py"), "traverse") == []


def test_validate_plan_runtime_never_touches_a_forbidden_graph(
    forbidden_graph_context: PlanningContext,
) -> None:
    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False),),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="test",
    )

    validate_plan(plan, forbidden_graph_context)  # must not raise GraphAccessForbidden


# -- 4. No mutation across the full pipeline -----------------------------------------------


def test_full_pipeline_never_mutates_goal_or_context(goal: Goal, context: PlanningContext) -> None:
    goal_before = goal.model_copy(deep=True)
    context_capabilities_before = context.available_capabilities
    context_correlation_before = context.correlation_id

    engine = PlanningEngine()
    engine.register_strategy(RuleBasedPlannerStrategy())
    plan = engine.create_plan(goal, context)

    assert goal == goal_before
    assert context.available_capabilities == context_capabilities_before
    assert context.correlation_id == context_correlation_before
    # The returned Plan is itself frozen -- attempting to mutate it must raise.
    with pytest.raises(ValidationError):
        plan.goal_id = "different"
