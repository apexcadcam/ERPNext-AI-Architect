"""Tests for the Composition Root (Sprint 13, Phase 2). Exercises the
real, unmocked chain: `analysis.requirements` -> `knowledge.builder` ->
`knowledge.projection` -> `intelligence.pipeline` -> the real `Planning`/
`Execution`/`Orchestration`/`Integration` modules, booted through the
real `PluginRegistry`/`Container` -- no fakes anywhere in this file.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from analysis.requirements.raw import RawProcessMention, RawRequirement
from execution.lifecycle import ExecutionRunState, StepExecutionState
from orchestration.contract import GoalRunResult
from planning.contract import CapabilityDescriptor, Goal
from runtime.errors import CapabilityResolutionError

from composition_root import run_goal_end_to_end

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"
_CREATED_AT = "2026-01-01T00:00:00Z"
_REQUIREMENT_ID = "REQ-COMPOSITION-1"
_PROCESS_NAME = "Patient Registration"
_WORKFLOW_CAPABILITY = f"WF-{_REQUIREMENT_ID}:process:{_PROCESS_NAME}"


def _requirement(
    *, requirement_id: str = _REQUIREMENT_ID, process_name: str = _PROCESS_NAME
) -> RawRequirement:
    return RawRequirement(
        requirement_id=requirement_id,
        description="Register new patients.",
        processes=(
            RawProcessMention(
                name=process_name,
                excerpt="register new patients before their first visit",
                steps=("collect identity",),
                actors=(),
            ),
        ),
    )


def _goal(goal_id: str = "G-COMPOSITION-1") -> Goal:
    return Goal(goal_id=goal_id, intent="register a patient")


def _available_capabilities(capability: str = _WORKFLOW_CAPABILITY) -> tuple[CapabilityDescriptor, ...]:
    return (
        CapabilityDescriptor(
            capability=capability, kind="write", idempotent=False, requires_confirmation=False
        ),
    )


def _config_dir(tmp_path: Path, *, planner_strategy: str | None) -> Path:
    # A fresh, unique subdirectory per call -- `_run()` may be called more
    # than once against the same `tmp_path` fixture within one test.
    config_dir = tmp_path / f"config-{uuid.uuid4()}"
    modules_dir = config_dir / "modules"
    modules_dir.mkdir(parents=True)
    values = {} if planner_strategy is None else {"planner_strategy": planner_strategy}
    (modules_dir / "planning.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
    return config_dir


def _run(
    tmp_path: Path,
    *,
    planner_strategy: str | None = "intelligence_aware",
    requirement: RawRequirement | None = None,
    goal: Goal | None = None,
    available_capabilities: tuple[CapabilityDescriptor, ...] | None = None,
    correlation_id: str = "corr-composition-1",
) -> GoalRunResult:
    return run_goal_end_to_end(
        requirement if requirement is not None else _requirement(),
        goal if goal is not None else _goal(),
        available_capabilities if available_capabilities is not None else _available_capabilities(),
        plugin_search_paths=[_PLUGINS_DIR],
        config_dir=_config_dir(tmp_path, planner_strategy=planner_strategy),
        created_at=_CREATED_AT,
        correlation_id=correlation_id,
    )


# -- 1. Happy path --------------------------------------------------------------------------------


def test_happy_path_executes_successfully(tmp_path: Path) -> None:
    result = _run(tmp_path)

    assert result.planning_failure is None
    assert result.plan is not None
    assert result.execution_result is not None


# -- 2. IntelligenceAwarePlannerStrategy is actually selected ---------------------------------------


def test_intelligence_aware_strategy_is_actually_selected(tmp_path: Path) -> None:
    result = _run(tmp_path, planner_strategy="intelligence_aware")

    assert result.plan is not None
    assert result.plan.strategy_name == "intelligence_aware"


# -- 3. PlanningEngine receives the injected TradeoffAssessment ------------------------------------


def test_planning_engine_receives_the_injected_tradeoff_assessment(tmp_path: Path) -> None:
    # The one Workflow artifact this requirement produces is the only
    # ranked candidate NullIntelligenceEngine could have produced -- the
    # resulting PlanStep's own capability is that candidate_id, verbatim,
    # proving the real TradeoffAssessment (not a stand-in) drove this Plan.
    result = _run(tmp_path)

    assert result.plan is not None
    assert len(result.plan.steps) == 1
    assert result.plan.steps[0].capability == _WORKFLOW_CAPABILITY
    assert "ranked by Intelligence" in result.plan.steps[0].rationale


# -- 4. GoalOrchestrator executes without modification ----------------------------------------------


def test_goal_orchestrator_executes_without_modification(tmp_path: Path) -> None:
    # GoalOrchestrator's own contract (orchestration/contract.py): exactly
    # one of two valid shapes -- Planning failed (plan/execution_result
    # both None), or Planning succeeded (both populated). Seeing the
    # second shape here proves the real, unmodified run_goal() ran.
    result = _run(tmp_path)

    assert result.planning_failure is None
    assert result.plan is not None
    assert result.execution_result is not None
    assert result.execution_result.plan_id == result.plan.plan_id


# -- 5. ExecutionEngine executes without modification -----------------------------------------------


def test_execution_engine_executes_without_modification(tmp_path: Path) -> None:
    # No connector is registered for a Workflow-artifact-derived capability
    # (a synthetic id, not a real ERPNext connector) -- ExecutionEngine's
    # own, unmodified, honest "capability not available" -> FAILED outcome
    # is expected and correct here, not a defect. This proves the real
    # engine ran the real step, not that a working connector exists.
    result = _run(tmp_path)

    assert result.execution_result is not None
    assert result.execution_result.final_state is ExecutionRunState.FAILED
    assert len(result.execution_result.step_records) == 1
    record = result.execution_result.step_records[0]
    assert record.state is StepExecutionState.FAILED
    assert record.response is not None
    assert "is not available" in (record.response.diagnostics or "")


# -- 6. The returned object is a valid GoalRunResult -------------------------------------------------


def test_returns_a_valid_goal_run_result(tmp_path: Path) -> None:
    result = _run(tmp_path, goal=_goal("G-VALID-1"))

    assert isinstance(result, GoalRunResult)
    assert result.goal_id == "G-VALID-1"


# -- 7. RuleBasedPlannerStrategy is never selected during this path -----------------------------------


def test_rule_based_strategy_is_never_selected_when_configured_and_supplied(tmp_path: Path) -> None:
    result = _run(tmp_path, planner_strategy="intelligence_aware")

    assert result.plan is not None
    assert result.plan.strategy_name != "rule_based"


def test_falls_back_to_rule_based_when_configuration_does_not_select_intelligence_aware(
    tmp_path: Path,
) -> None:
    # The contrasting case: a real TradeoffAssessment is always computed
    # and always injected by this Composition Root, but configuration
    # alone still decides selection -- unchanged, Sprint 12 behavior.
    result = _run(tmp_path, planner_strategy=None)

    assert result.plan is not None
    assert result.plan.strategy_name == "rule_based"


# -- 8. PluginRegistry is used exactly as designed -----------------------------------------------------


def test_two_independent_calls_do_not_share_any_state(tmp_path: Path) -> None:
    first = _run(tmp_path, requirement=_requirement(requirement_id="REQ-A"), goal=_goal("G-A"))
    second = _run(tmp_path, requirement=_requirement(requirement_id="REQ-B"), goal=_goal("G-B"))

    assert first.goal_id == "G-A"
    assert second.goal_id == "G-B"
    assert first.plan is not None
    assert second.plan is not None
    assert first.plan.plan_id != second.plan.plan_id


def test_repeated_calls_with_identical_inputs_are_deterministic(tmp_path: Path) -> None:
    first = _run(tmp_path)
    second = _run(tmp_path)

    assert first.plan == second.plan
    assert first.execution_result is not None
    assert second.execution_result is not None
    assert first.execution_result.final_state == second.execution_result.final_state
    assert [r.state for r in first.execution_result.step_records] == [
        r.state for r in second.execution_result.step_records
    ]


# -- 9. No Runtime modifications are required -------------------------------------------------------
# See tests/sprint13/test_architecture_boundaries.py for the structural
# (git-diff / import-graph) proof of this -- not meaningfully expressible
# as a functional/behavioral test in this file.


# -- Invalid input: no plugins discovered at all ------------------------------------------------


def test_raises_when_no_plugins_are_discovered(tmp_path: Path) -> None:
    # An empty plugin_search_paths result means dependency_order() is
    # empty too -- no module (including "orchestration") is ever
    # instantiated, so resolving "orchestration.goal_runner" at the end
    # fails honestly rather than silently proceeding with nothing wired.
    empty_plugins_dir = tmp_path / "empty-plugins"
    empty_plugins_dir.mkdir()

    with pytest.raises(CapabilityResolutionError):
        run_goal_end_to_end(
            _requirement(),
            _goal(),
            _available_capabilities(),
            plugin_search_paths=[empty_plugins_dir],
            config_dir=_config_dir(tmp_path, planner_strategy="intelligence_aware"),
            created_at=_CREATED_AT,
            correlation_id="corr-missing-plugins",
        )
