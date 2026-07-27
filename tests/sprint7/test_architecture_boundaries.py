"""Sprint 7, Phase 4 — Architecture Boundary Tests.

Verifies `orchestration/` introduces no forbidden import, that `runtime/`
still has no direct or transitive import of `orchestration/` anywhere in
its own package, and — at the whole-Sprint level, complementing
`tests/orchestration/test_layer_isolation.py`'s own per-file proof from
Phase 2 — that `planning/`/`execution/` remain provably unaware
`orchestration/` exists. Reuses the exact AST-scan-plus-subprocess
`sys.modules` methodology `tests/sprint3/test_architecture_boundaries.py`
through `tests/sprint6/test_architecture_boundaries.py` already
established.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_DIR = REPO_ROOT / "orchestration"
RUNTIME_DIR = REPO_ROOT / "runtime"
PLANNING_DIR = REPO_ROOT / "planning"
EXECUTION_DIR = REPO_ROOT / "execution"
ORCHESTRATION_FORBIDDEN = {"secrets_management", "knowledge"}

#: `runtime/cli.py`'s new `run-goal` command (Sprint 14, Phase 2, ADR-005)
#: is the one, disclosed, sanctioned exception to "runtime/ never imports
#: orchestration/" — it renders `orchestration.contract.GoalRunResult`
#: (plain data, never `GoalOrchestrator`), the return type of
#: `composition_root.run_goal_end_to_end`. A narrow, disclosed update to
#: this Sprint's own stale assumption, not a change to this Sprint's
#: behavior: every other file in `runtime/` still imports no part of
#: `orchestration`.
_SANCTIONED_ORCHESTRATION_CONSUMER = RUNTIME_DIR / "cli.py"


def _direct_top_level_imports(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def _all_imports_under(package_dir: Path) -> dict[Path, set[str]]:
    return {
        py_file: _direct_top_level_imports(py_file)
        for py_file in sorted(package_dir.rglob("*.py"))
        if "__pycache__" not in py_file.parts
    }


def _sys_modules_after_importing(module_name: str) -> set[str]:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}; import sys; print('\\n'.join(sys.modules))"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return set(result.stdout.splitlines())


# -- orchestration/ has no forbidden import -------------------------------------------------


def test_orchestration_has_no_direct_import_of_secrets_management_or_knowledge() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & ORCHESTRATION_FORBIDDEN)
        for py_file, imports in _all_imports_under(ORCHESTRATION_DIR).items()
        if imports & ORCHESTRATION_FORBIDDEN
    }
    assert violations == {}


def test_every_orchestration_file_was_actually_scanned() -> None:
    scanned = set(_all_imports_under(ORCHESTRATION_DIR))
    expected = {
        ORCHESTRATION_DIR / name for name in ("__init__.py", "contract.py", "orchestrator.py", "module.py")
    }
    assert expected <= scanned


def test_importing_orchestration_never_transitively_imports_secrets_management() -> None:
    # "knowledge" is not asserted here, for the same reason established at
    # tests/sprint5/test_layer_isolation.py: orchestration/orchestrator.py
    # legitimately, transitively pulls in planning/, whose own __init__.py
    # imports planning.graph_reader, which imports knowledge -- a chain
    # through an already-approved dependency, not orchestration/ touching
    # knowledge directly (the AST-scan test above already proves that).
    modules = _sys_modules_after_importing("orchestration")
    assert "secrets_management" not in modules


# -- runtime/ still has no import of orchestration/ ------------------------------------------


def test_runtime_has_no_direct_import_of_orchestration() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(RUNTIME_DIR).items()
        if "orchestration" in imports and py_file != _SANCTIONED_ORCHESTRATION_CONSUMER
    }
    assert violations == {}


def test_cli_is_a_real_exercised_orchestration_consumer() -> None:
    # The positive complement of the test above -- proves the one
    # exception is real and exercised, not merely permitted and unused.
    assert "orchestration" in _direct_top_level_imports(_SANCTIONED_ORCHESTRATION_CONSUMER)


def test_importing_runtime_boot_never_transitively_imports_orchestration() -> None:
    modules = _sys_modules_after_importing("runtime.boot")
    assert "orchestration" not in modules


# -- planning/ and execution/ remain unaware orchestration/ exists (whole-Sprint proof) ------


def test_planning_has_no_import_of_orchestration() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(PLANNING_DIR).items()
        if "orchestration" in imports
    }
    assert violations == {}


def test_execution_has_no_import_of_orchestration() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(EXECUTION_DIR).items()
        if "orchestration" in imports
    }
    assert violations == {}
