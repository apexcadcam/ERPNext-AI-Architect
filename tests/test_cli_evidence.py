"""Tests for `architect evidence extract` (Evidence Platform CLI
Architecture Specification v1.1 §3.1, §6, §7).

Every test drives the real command through `typer.testing.CliRunner`
against a real source tree and the real engines -- nothing is mocked. The
command is a thin adapter, so mocking the layer beneath it would leave
nothing under test.
"""

from __future__ import annotations

import ast
import json as json_module
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from runtime.cli import app
from runtime.output import SECTION_ORDER

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parents[1]

_CUSTOMER_PY = """
class Customer:
    def validate(self):
        pass

    def on_submit(self):
        pass
"""

_API_PY = """
import frappe


@frappe.whitelist()
def get_data():
    return {}
"""

_COMMIT = "61ab7e2b2409b293ffd3c8f72d730fa89b201332"


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "erpnext" / "doctype" / "customer").mkdir(parents=True)
    (root / "erpnext" / "doctype" / "customer" / "customer.py").write_text(_CUSTOMER_PY)
    (root / "erpnext" / "api.py").write_text(_API_PY)
    return root


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "evidence-out"


def _args(source_root: Path, output_dir: Path, *extra: str) -> list[str]:
    return [
        "evidence",
        "extract",
        "erpnext",
        "--version",
        "v15.102.0",
        "--commit",
        _COMMIT,
        "--source-root",
        str(source_root),
        "--output-dir",
        str(output_dir),
        *extra,
    ]


# -- The happy path ------------------------------------------------------------------------------------


def test_extract_succeeds_and_writes_both_artifacts(source_root: Path, output_dir: Path) -> None:
    result = runner.invoke(app, _args(source_root, output_dir))

    assert result.exit_code == 0
    assert (output_dir / "erpnext-v15.102.0.evidence.jsonl").exists()
    assert (output_dir / "erpnext-v15.102.0.meta.json").exists()


def test_extract_reports_the_engines_own_statistics(source_root: Path, output_dir: Path) -> None:
    result = runner.invoke(app, _args(source_root, output_dir, "--json"))
    payload = json_module.loads(result.stdout)

    # Two .py files in the fixture. Four Evidence records: two lifecycle
    # hooks, one whitelist decoration, and — since Sprint 22 — one class
    # definition for `class Customer:`, which declares no base and so
    # contributes a node record and no edge record. The CLI reports
    # whatever the engine counted; this asserts it counts nothing itself.
    assert payload["summary"]["files examined"] == "2"
    assert payload["summary"]["evidence extracted"] == "4"
    assert payload["summary"]["files failed"] == "0"


def test_artifact_paths_reported_are_the_paths_actually_written(source_root: Path, output_dir: Path) -> None:
    result = runner.invoke(app, _args(source_root, output_dir, "--json"))
    written = json_module.loads(result.stdout)["artifacts_written"]

    assert len(written) == 2
    for path in written:
        assert Path(path).exists()


def test_output_dir_is_created_when_it_does_not_exist(source_root: Path, tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    result = runner.invoke(app, _args(source_root, nested))

    assert result.exit_code == 0
    assert nested.is_dir()


# -- Output Contract conformance (§6) ---------------------------------------------------------------------


def test_human_output_emits_all_six_sections_in_order(source_root: Path, output_dir: Path) -> None:
    result = runner.invoke(app, _args(source_root, output_dir))
    positions = [result.stdout.index(section.upper().replace("_", " ")) for section in SECTION_ORDER]

    assert positions == sorted(positions)
    assert result.stdout.strip().endswith("exit: 0")


def test_json_output_emits_all_six_keys_plus_exit_code(source_root: Path, output_dir: Path) -> None:
    result = runner.invoke(app, _args(source_root, output_dir, "--json"))
    payload = json_module.loads(result.stdout)

    assert list(payload) == [*SECTION_ORDER, "exit_code"]
    assert payload["exit_code"] == 0


def test_both_modes_report_identical_numbers(source_root: Path, output_dir: Path) -> None:
    human = runner.invoke(app, _args(source_root, output_dir)).stdout
    payload = json_module.loads(runner.invoke(app, _args(source_root, output_dir, "--json")).stdout)

    for label, value in payload["summary"].items():
        assert label in human
        assert value in human


# -- Failure paths (§7): an exit code and a message, never a traceback ---------------------------------------


def test_unknown_repository_fails_with_a_readable_message(source_root: Path, output_dir: Path) -> None:
    args = _args(source_root, output_dir)
    args[2] = "apex_dashboard"
    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "Unknown repository 'apex_dashboard'" in result.stdout
    assert "frappe, erpnext, hrms" in result.stdout
    assert "Traceback" not in result.stdout


def test_missing_source_root_fails_with_the_engines_own_message(tmp_path: Path, output_dir: Path) -> None:
    result = runner.invoke(app, _args(tmp_path / "nope", output_dir))

    assert result.exit_code == 1
    assert "Traceback" not in result.stdout
    payload_free_text = result.stdout.lower()
    assert "nope" in payload_free_text


def test_a_malformed_commit_fails_cleanly_rather_than_raising(source_root: Path, output_dir: Path) -> None:
    # Found by running the command: `Source.commit`'s pattern is enforced
    # while building an Evidence record, deep inside the collector, not at
    # the request boundary -- so this surfaced as a raw pydantic traceback
    # until the command caught ValidationError too.
    args = _args(source_root, output_dir)
    args[args.index("--commit") + 1] = "not-a-sha"
    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "Invalid input: commit" in result.stdout
    assert "Traceback" not in result.stdout


def test_a_failing_run_still_emits_all_six_sections(source_root: Path, output_dir: Path) -> None:
    args = _args(source_root, output_dir)
    args[2] = "apex_dashboard"
    result = runner.invoke(app, args, catch_exceptions=False)

    for section in SECTION_ORDER:
        assert section.upper().replace("_", " ") in result.stdout
    assert result.stdout.strip().endswith("exit: 1")


def test_a_failing_run_in_json_mode_is_still_parseable(source_root: Path, output_dir: Path) -> None:
    args = _args(source_root, output_dir, "--json")
    args[2] = "apex_dashboard"
    payload = json_module.loads(runner.invoke(app, args).stdout)

    assert list(payload) == [*SECTION_ORDER, "exit_code"]
    assert payload["exit_code"] == 1
    assert payload["summary"] == {}
    assert len(payload["errors"]) == 1


def test_version_and_commit_are_required(source_root: Path, output_dir: Path) -> None:
    # Evidence spec §2: provenance is caller-supplied and never inferred.
    # Omitting it must stop the run, not fall back to a previous label.
    result = runner.invoke(app, ["evidence", "extract", "erpnext", "--source-root", str(source_root)])
    assert result.exit_code != 0


# -- Truncation surfaces as a warning, never silently ---------------------------------------------------------


def test_hitting_the_file_ceiling_is_reported_as_a_warning(source_root: Path, output_dir: Path) -> None:
    result = runner.invoke(app, _args(source_root, output_dir, "--max-files", "1", "--json"))
    payload = json_module.loads(result.stdout)

    assert result.exit_code == 0
    assert any("ceiling" in warning for warning in payload["warnings"])


# -- The boundary this command must not cross (§2) --------------------------------------------------------------


def _cli_imports() -> set[str]:
    tree = ast.parse((REPO_ROOT / "runtime" / "cli.py").read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def test_the_cli_imports_no_engine_module_at_all() -> None:
    # §2's whole point: the CLI reaches the Evidence Platform through the
    # Composition Root and holds no engine knowledge. Not the engines, not
    # their contracts, not their errors -- checked over the entire file,
    # including the lazy imports inside command bodies.
    assert {"evidence", "aggregation"} & _cli_imports() == set()


def test_the_cli_reaches_the_platform_through_composition_root() -> None:
    assert "composition_root" in _cli_imports()


def test_importing_the_cli_pulls_in_neither_engine() -> None:
    # The lazy import inside the command body is what keeps this true. If
    # `composition_root/__init__.py` ever re-exported the Evidence Platform
    # functions, `architect doctor` would start loading both engines.
    result = subprocess.run(
        [sys.executable, "-c", "import runtime.cli, sys; print('\\n'.join(sys.modules))"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    loaded = set(result.stdout.splitlines())
    assert "evidence" not in loaded
    assert "aggregation" not in loaded
