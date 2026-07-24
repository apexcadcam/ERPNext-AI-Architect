"""Sprint 4, Phase 6, §3 — Architecture Boundary Tests.

Verifies `planning/` has no direct or transitive import of `integration/`
or `secrets_management/`. Reuses the exact AST-scan + subprocess
`sys.modules` methodology `tests/sprint3/test_architecture_boundaries.py`
already established for Sprint 3's own boundary tests, applied here to the
Planning package instead.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNING_DIR = REPO_ROOT / "planning"
FORBIDDEN = {"integration", "secrets_management"}


def _direct_top_level_imports(py_file: Path) -> set[str]:
    """The set of top-level package names `py_file` directly imports,
    e.g. `from integration.contract import X` contributes `"integration"`.
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


# -- Direct-import (AST) checks -----------------------------------------------------


def test_planning_has_no_direct_import_of_integration_or_secrets_management() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & FORBIDDEN)
        for py_file, imports in _all_imports_under(PLANNING_DIR).items()
        if imports & FORBIDDEN
    }
    assert violations == {}


def test_every_planning_file_was_actually_scanned() -> None:
    # Sanity check on the AST scan itself: it must have found every
    # production file this Sprint shipped, not silently scanned zero files.
    scanned = set(_all_imports_under(PLANNING_DIR))
    expected = {
        PLANNING_DIR / name
        for name in (
            "__init__.py",
            "contract.py",
            "context.py",
            "engine.py",
            "errors.py",
            "events.py",
            "graph_reader.py",
            "strategy.py",
            "validation.py",
        )
    }
    assert expected <= scanned


# -- Hidden/transitive-import (subprocess) checks --------------------------------------


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


def test_importing_planning_never_transitively_imports_integration_or_secrets_management() -> None:
    modules = _sys_modules_after_importing("planning")
    assert "integration" not in modules
    assert "secrets_management" not in modules


def test_importing_each_planning_submodule_individually_stays_isolated() -> None:
    for submodule in (
        "planning.contract",
        "planning.context",
        "planning.engine",
        "planning.errors",
        "planning.events",
        "planning.graph_reader",
        "planning.strategy",
        "planning.validation",
    ):
        modules = _sys_modules_after_importing(submodule)
        assert "integration" not in modules, f"{submodule} transitively imports integration"
        assert "secrets_management" not in modules, f"{submodule} transitively imports secrets_management"
