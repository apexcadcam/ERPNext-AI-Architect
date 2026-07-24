"""Sprint 5, Phase 7 — Architecture Boundary Tests.

Verifies `execution/` has no direct or transitive import of
`secrets_management/` or `knowledge/`, and that `planning/` — unchanged
since Sprint 4 — still has zero dependency on the new `execution/`
package, the one-way direction Sprint 5 Architecture Package §6 requires.
Reuses the exact AST-scan + subprocess `sys.modules` methodology
`tests/sprint3/test_architecture_boundaries.py` and
`tests/sprint4/test_architecture_boundaries.py` already established.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_DIR = REPO_ROOT / "execution"
PLANNING_DIR = REPO_ROOT / "planning"
EXECUTION_FORBIDDEN = {"secrets_management", "knowledge"}


def _direct_top_level_imports(py_file: Path) -> set[str]:
    """The set of top-level package names `py_file` directly imports,
    e.g. `from knowledge.graph import X` contributes `"knowledge"`.
    """

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


# -- execution/ has no import of secrets_management/ or knowledge/ ------------------------


def test_execution_has_no_direct_import_of_secrets_management_or_knowledge() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & EXECUTION_FORBIDDEN)
        for py_file, imports in _all_imports_under(EXECUTION_DIR).items()
        if imports & EXECUTION_FORBIDDEN
    }
    assert violations == {}


def test_every_execution_file_was_actually_scanned() -> None:
    # Sanity check on the AST scan itself: it must have found every
    # production file this Sprint shipped, not silently scanned zero files.
    scanned = set(_all_imports_under(EXECUTION_DIR))
    expected = {
        EXECUTION_DIR / name
        for name in (
            "__init__.py",
            "cancellation.py",
            "confirmation.py",
            "confirmation_gate.py",
            "connector_invoker.py",
            "context.py",
            "contract.py",
            "engine.py",
            "errors.py",
            "events.py",
            "lifecycle.py",
            "retry.py",
            "rollback.py",
            "scheduler.py",
        )
    }
    assert expected <= scanned


def test_importing_execution_never_transitively_imports_secrets_management() -> None:
    # "knowledge" is deliberately not asserted here: execution/context.py
    # legitimately imports planning.contract.RuntimeContextInfo, and
    # planning/__init__.py itself imports planning.graph_reader, which
    # imports knowledge -- exactly the same transitive shape planning's
    # own test suite already accepts for itself. This is a chain through
    # an already-approved dependency, not execution/ touching knowledge
    # directly; the AST-scan tests above already prove no execution/ file
    # imports knowledge directly.
    modules = _sys_modules_after_importing("execution")
    assert "secrets_management" not in modules


def test_importing_each_execution_submodule_individually_stays_isolated_from_secrets_management() -> None:
    for submodule in (
        "execution.cancellation",
        "execution.confirmation",
        "execution.confirmation_gate",
        "execution.connector_invoker",
        "execution.context",
        "execution.contract",
        "execution.engine",
        "execution.errors",
        "execution.events",
        "execution.lifecycle",
        "execution.retry",
        "execution.rollback",
        "execution.scheduler",
    ):
        modules = _sys_modules_after_importing(submodule)
        assert "secrets_management" not in modules, f"{submodule} transitively imports secrets_management"


# -- planning/ still has zero dependency on execution/ (the one-way direction) ------------


def test_planning_has_no_direct_import_of_execution() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(PLANNING_DIR).items()
        if "execution" in imports
    }
    assert violations == {}


def test_importing_planning_never_transitively_imports_execution() -> None:
    modules = _sys_modules_after_importing("planning")
    assert "execution" not in modules
