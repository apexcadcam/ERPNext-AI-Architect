"""Tests for the `architect` CLI (docs/runtime/CLI_ARCHITECTURE.md)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import yaml
from typer.testing import CliRunner

from orchestration.contract import GoalRunResult, PlanningFailure
from runtime.cli import _goal_run_result_payload, _render_goal_run_result, app

runner = CliRunner()

# The CLI deliberately sends structured logs to stderr and command output
# (including --json payloads) to stdout separately (CLI_ARCHITECTURE.md —
# scriptable output must never be interleaved with log noise). Every
# --json assertion below reads `result.stdout` specifically, never the
# combined `.output`, to actually exercise that separation rather than
# accidentally relying on log lines happening to also be valid JSON.


def test_help_exits_zero_and_lists_every_required_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("doctor", "plugins", "runtime", "config"):
        assert command in result.output


def test_doctor_with_no_plugins_or_config_succeeds(config_dir: Path, plugins_dir: Path) -> None:
    result = runner.invoke(app, ["doctor", "--config-dir", str(config_dir), "--plugin-path", str(plugins_dir)])
    assert result.exit_code == 0
    assert "HEALTHY" in result.output


def test_doctor_json_output_is_valid_and_matches_human_readable_facts(config_dir: Path, plugins_dir: Path) -> None:
    result = runner.invoke(
        app, ["doctor", "--config-dir", str(config_dir), "--plugin-path", str(plugins_dir), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["runtime_state"] == "ready"


def test_plugins_list_with_nothing_installed_reports_that_clearly(plugins_dir: Path) -> None:
    result = runner.invoke(app, ["plugins", "list", "--plugin-path", str(plugins_dir)])
    assert result.exit_code == 0
    assert "No plugins installed" in result.output


def test_plugins_list_shows_a_discovered_plugin(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("demo", capabilities_provided=["demo.cap"])
    result = runner.invoke(app, ["plugins", "list", "--plugin-path", str(plugins_dir)])
    assert result.exit_code == 0
    assert "demo" in result.output
    assert "demo.cap" in result.output


def test_plugins_list_json(make_plugin: Callable[..., Path], plugins_dir: Path) -> None:
    make_plugin("demo")
    result = runner.invoke(app, ["plugins", "list", "--plugin-path", str(plugins_dir), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["plugins"][0]["module_id"] == "demo"


def test_runtime_info_reports_ready_state(config_dir: Path, plugins_dir: Path) -> None:
    result = runner.invoke(
        app, ["runtime", "info", "--config-dir", str(config_dir), "--plugin-path", str(plugins_dir)]
    )
    assert result.exit_code == 0
    assert "State: ready" in result.output


def test_config_validate_succeeds_on_empty_config_dir(config_dir: Path) -> None:
    result = runner.invoke(app, ["config", "validate", "--config-dir", str(config_dir)])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_config_validate_fails_on_literal_credential(config_dir: Path) -> None:
    (config_dir / "global.yaml").write_text(yaml.safe_dump({"secret_token": "literal-value"}))
    result = runner.invoke(app, ["config", "validate", "--config-dir", str(config_dir)])
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_config_validate_json_output(config_dir: Path) -> None:
    result = runner.invoke(app, ["config", "validate", "--config-dir", str(config_dir), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["issues"] == []


def test_doctor_fails_with_nonzero_exit_when_dependency_validation_fails(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    make_plugin("consumer", capabilities_required=["missing.thing"])
    result = runner.invoke(app, ["doctor", "--config-dir", str(config_dir), "--plugin-path", str(plugins_dir)])
    assert result.exit_code == 1


# == run-goal (Sprint 14, Phase 2) ====================================================================
#
# Uses the REAL `plugins/` directory (integration/planning/execution/
# orchestration) -- the synthetic, empty `plugins_dir` fixture above is
# deliberately not used for the success-path tests, since `run-goal`
# structurally cannot complete without those four real modules.

_REAL_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
_REQUIREMENT_ID = "REQ-CLI-1"
_PROCESS_NAME = "Patient Registration"
_WORKFLOW_CAPABILITY = f"WF-{_REQUIREMENT_ID}:process:{_PROCESS_NAME}"


def _goal_input(
    *,
    requirement_id: str = _REQUIREMENT_ID,
    process_name: str = _PROCESS_NAME,
    capability: str | None = _WORKFLOW_CAPABILITY,
) -> dict[str, object]:
    data: dict[str, object] = {
        "requirement": {
            "requirement_id": requirement_id,
            "description": "Register new patients.",
            "processes": [
                {
                    "name": process_name,
                    "excerpt": "register new patients before their first visit",
                    "steps": ["collect identity"],
                    "actors": [],
                }
            ],
        },
        "goal": {"goal_id": "G-CLI-1", "intent": "register a patient"},
    }
    if capability is not None:
        data["available_capabilities"] = [
            {"capability": capability, "kind": "write", "idempotent": False, "requires_confirmation": False}
        ]
    return data


def _write_goal_file(tmp_path: Path, data: dict[str, object] | str, *, name: str = "goal.yaml") -> Path:
    goal_file = tmp_path / name
    text = data if isinstance(data, str) else yaml.safe_dump(data)
    goal_file.write_text(text, encoding="utf-8")
    return goal_file


def _intelligence_aware_config_dir(tmp_path: Path, *, name: str = "config") -> Path:
    config_dir = tmp_path / name
    modules_dir = config_dir / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "planning.yaml").write_text(
        yaml.safe_dump({"planner_strategy": "intelligence_aware"}), encoding="utf-8"
    )
    return config_dir


def test_run_goal_successful_execution(tmp_path: Path) -> None:
    goal_file = _write_goal_file(tmp_path, _goal_input())
    config_dir = _intelligence_aware_config_dir(tmp_path)

    result = runner.invoke(
        app,
        [
            "run-goal",
            str(goal_file),
            "--config-dir",
            str(config_dir),
            "--plugin-path",
            str(_REAL_PLUGINS_DIR),
        ],
    )

    assert result.exit_code == 1  # execution FAILED: no connector exists for a synthetic capability
    assert "Strategy: intelligence_aware" in result.output
    assert _WORKFLOW_CAPABILITY in result.output
    assert "Goal state: FAILED" in result.output


def test_run_goal_missing_input_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run-goal", str(tmp_path / "does-not-exist.yaml")])

    assert result.exit_code == 1
    assert "Could not read input file" in result.output


def test_run_goal_invalid_yaml(tmp_path: Path) -> None:
    goal_file = _write_goal_file(tmp_path, "requirement: [unterminated", name="bad.yaml")

    result = runner.invoke(app, ["run-goal", str(goal_file)])

    assert result.exit_code == 1
    assert "not valid YAML" in result.output


def test_run_goal_missing_required_keys(tmp_path: Path) -> None:
    goal_file = _write_goal_file(tmp_path, {"requirement": {"requirement_id": "R", "description": "x"}})

    result = runner.invoke(app, ["run-goal", str(goal_file)])

    assert result.exit_code == 1
    assert "'requirement' and 'goal' keys" in result.output


def test_run_goal_invalid_pydantic_model(tmp_path: Path) -> None:
    # "kind" must be "read" or "write" -- CapabilityDescriptor's own Literal.
    data = _goal_input(capability=None)
    data["available_capabilities"] = [
        {"capability": "x", "kind": "not-a-real-kind", "idempotent": False, "requires_confirmation": False}
    ]
    goal_file = _write_goal_file(tmp_path, data)

    result = runner.invoke(app, ["run-goal", str(goal_file)])

    assert result.exit_code == 1
    assert "failed validation" in result.output


def test_run_goal_planning_failure_rendering(tmp_path: Path) -> None:
    # No plugins at all -> PluginRegistry never registers "planning" ->
    # Runtime-level failure (RuntimeError_), not a PlanningFailure -- this
    # exercises the "input/boot itself failed" branch, distinctly from a
    # PlanningFailure produced by GoalOrchestrator's own internal catch.
    goal_file = _write_goal_file(tmp_path, _goal_input())
    empty_plugins_dir = tmp_path / "empty-plugins"
    empty_plugins_dir.mkdir()

    result = runner.invoke(app, ["run-goal", str(goal_file), "--plugin-path", str(empty_plugins_dir)])

    assert result.exit_code == 1
    assert "Runtime failed to boot" in result.output


def test_run_goal_execution_failure_rendering(tmp_path: Path) -> None:
    goal_file = _write_goal_file(tmp_path, _goal_input())
    config_dir = _intelligence_aware_config_dir(tmp_path)

    result = runner.invoke(
        app,
        [
            "run-goal",
            str(goal_file),
            "--config-dir",
            str(config_dir),
            "--plugin-path",
            str(_REAL_PLUGINS_DIR),
        ],
    )

    assert result.exit_code == 1
    assert "Execution: FAILED" in result.output
    assert "is not available" in result.output


def test_run_goal_json_output(tmp_path: Path) -> None:
    goal_file = _write_goal_file(tmp_path, _goal_input())
    config_dir = _intelligence_aware_config_dir(tmp_path)

    result = runner.invoke(
        app,
        [
            "run-goal",
            str(goal_file),
            "--config-dir",
            str(config_dir),
            "--plugin-path",
            str(_REAL_PLUGINS_DIR),
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["goal_id"] == "G-CLI-1"
    assert payload["goal_state"] == "failed"
    assert payload["plan"]["strategy_name"] == "intelligence_aware"
    assert payload["plan"]["steps"][0]["capability"] == _WORKFLOW_CAPABILITY
    assert payload["execution_result"]["final_state"] == "failed"
    assert payload["execution_result"]["step_records"][0]["response_status"] == "failure"


def test_run_goal_human_readable_output_is_used_without_json_flag(tmp_path: Path) -> None:
    goal_file = _write_goal_file(tmp_path, _goal_input())
    config_dir = _intelligence_aware_config_dir(tmp_path)

    result = runner.invoke(
        app,
        [
            "run-goal",
            str(goal_file),
            "--config-dir",
            str(config_dir),
            "--plugin-path",
            str(_REAL_PLUGINS_DIR),
        ],
    )

    assert result.exit_code == 1
    assert "Goal: G-CLI-1" in result.output
    assert not result.output.strip().startswith("{")


def test_run_goal_falls_back_to_rule_based_without_intelligence_aware_configuration(tmp_path: Path) -> None:
    goal_file = _write_goal_file(tmp_path, _goal_input())
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "run-goal",
            str(goal_file),
            "--config-dir",
            str(config_dir),
            "--plugin-path",
            str(_REAL_PLUGINS_DIR),
        ],
    )

    assert "Strategy: rule_based" in result.output


# -- planning_failure rendering, exercised directly ---------------------------------------------------
#
# Neither real PlannerStrategy (RuleBasedPlannerStrategy,
# IntelligenceAwarePlannerStrategy) can ever produce a Plan violating
# validate_plan's own rules -- both only ever emit steps for matched
# capabilities, with requires_confirmation copied verbatim and no
# depends_on ever set. A genuine GoalOrchestrator-caught PlanningFailure
# is therefore not reachable through this Composition Root's real,
# live path; the rendering code for it is exercised directly here
# instead, against a real (hand-built) GoalRunResult -- the same
# "can't reach it live, test the real type directly" technique already
# used elsewhere in this project (e.g. tests/intelligence/test_pipeline.py's
# own hand-assembled fixtures).


def _planning_failure_result() -> GoalRunResult:
    return GoalRunResult(
        goal_id="G-FAILED-1",
        planning_failure=PlanningFailure(
            error_type="PlannerStrategyError", detail="no PlannerStrategy is configured"
        ),
    )


def test_render_goal_run_result_shows_planning_failure() -> None:
    rendered = _render_goal_run_result(_planning_failure_result())

    assert "Planning failed: PlannerStrategyError — no PlannerStrategy is configured" in rendered
    assert "Goal state: PLANNING_FAILED" in rendered


def test_goal_run_result_payload_shows_planning_failure() -> None:
    payload = _goal_run_result_payload(_planning_failure_result())

    assert payload["goal_state"] == "planning_failed"
    assert payload["planning_failure"] == {
        "error_type": "PlannerStrategyError",
        "detail": "no PlannerStrategy is configured",
    }
    assert payload["plan"] is None
    assert payload["execution_result"] is None
