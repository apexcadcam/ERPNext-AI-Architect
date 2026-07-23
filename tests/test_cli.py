"""Tests for the `architect` CLI (docs/runtime/CLI_ARCHITECTURE.md)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import yaml
from typer.testing import CliRunner

from runtime.cli import app

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
