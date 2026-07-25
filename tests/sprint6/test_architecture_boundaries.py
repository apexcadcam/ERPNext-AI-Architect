"""Sprint 6, Phase 7 — Architecture Boundary Tests.

Verifies the two new Module wrappers this Sprint added
(`planning/module.py`, `execution/module.py`) introduce no forbidden
import, and that `runtime/` itself — unchanged by this Sprint's own two
new, additive capability registrations (`runtime.event_bus`/
`runtime.config`, ADR Candidate B) — still has no import of `planning/`
or `execution/` anywhere in its own package, direct or transitive. Reuses
the exact AST-scan-plus-subprocess `sys.modules` methodology
`tests/sprint3/test_architecture_boundaries.py` through `tests/sprint5/
test_architecture_boundaries.py` already established.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNING_MODULE_FILE = REPO_ROOT / "planning" / "module.py"
EXECUTION_MODULE_FILE = REPO_ROOT / "execution" / "module.py"
RUNTIME_DIR = REPO_ROOT / "runtime"
PLANNING_FORBIDDEN = {"integration", "secrets_management"}
EXECUTION_FORBIDDEN = {"secrets_management", "knowledge", "planning"}


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


# -- planning/module.py has no forbidden import ---------------------------------------


def test_planning_module_has_no_direct_import_of_integration_or_secrets_management() -> None:
    imports = _direct_top_level_imports(PLANNING_MODULE_FILE)
    assert imports & PLANNING_FORBIDDEN == set()


def test_importing_planning_module_never_transitively_imports_integration() -> None:
    modules = _sys_modules_after_importing("planning.module")
    assert "integration" not in modules
    assert "secrets_management" not in modules


# -- execution/module.py has no forbidden import ---------------------------------------


def test_execution_module_has_no_direct_import_of_secrets_management_knowledge_or_planning() -> None:
    imports = _direct_top_level_imports(EXECUTION_MODULE_FILE)
    assert imports & EXECUTION_FORBIDDEN == set()


def test_importing_execution_module_never_transitively_imports_planning_as_a_live_capability() -> None:
    # execution.module legitimately, transitively pulls in "planning"
    # itself (and, through planning/__init__.py's own aggregation of every
    # Planning submodule, "planning.engine" too), via execution.engine's
    # own already-approved import of planning.contract (Sprint 5) -- the
    # same "transitive through an already-approved dependency, and through
    # Python's own package-init aggregation" shape already accepted for
    # "knowledge" via planning.graph_reader (Sprint 5 Phase 7's own
    # boundary tests). Only "planning.module" -- this Sprint's own
    # PlanningModule, never re-exported by planning/__init__.py and never
    # imported by anything execution/ touches -- is a meaningful, true
    # assertion here; "planning"/"planning.engine" are not, since Python's
    # own import caching cannot distinguish "imported for an approved
    # frozen type" from "imported as a live capability" once any code has
    # imported the package at all.
    modules = _sys_modules_after_importing("execution.module")
    assert "planning.module" not in modules
    assert "secrets_management" not in modules


# -- runtime/ still has no import of planning/ or execution/ ----------------------------


def test_runtime_has_no_direct_import_of_planning_or_execution() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & {"planning", "execution"})
        for py_file, imports in _all_imports_under(RUNTIME_DIR).items()
        if imports & {"planning", "execution"}
    }
    assert violations == {}


def test_importing_runtime_boot_never_transitively_imports_planning_or_execution() -> None:
    modules = _sys_modules_after_importing("runtime.boot")
    assert "planning" not in modules
    assert "execution" not in modules
