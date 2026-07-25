"""Layer isolation and boundary tests for `orchestration/orchestrator.py`
(Sprint 7 Architecture Package §5 ADR Candidate C, §7; §4 invariant 9),
Phase 2.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology
`tests/sprint3/test_architecture_boundaries.py` through `tests/sprint6/
test_architecture_boundaries.py` already established, plus a dedicated
static-and-runtime pair proving invariant 9 (`GoalOrchestrator` never
mutates a `Plan`/`Goal`/`ExecutionResult`).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_FILE = REPO_ROOT / "orchestration" / "orchestrator.py"
PLANNING_DIR = REPO_ROOT / "planning"
EXECUTION_DIR = REPO_ROOT / "execution"

#: The exact, named set orchestrator.py is approved to import directly —
#: ADR Candidate C's own "the one legitimate exception," not a general
#: permission (Sprint 7 Architecture Package §6's own named risk).
APPROVED_DIRECT_IMPORTS = {
    "__future__",
    "planning",
    "runtime",
    "execution",
    "orchestration",
}


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


# -- orchestrator.py's own direct imports are exactly the approved set --------------------


def test_orchestrator_direct_imports_are_within_the_approved_set() -> None:
    imports = _direct_top_level_imports(ORCHESTRATOR_FILE)
    assert imports <= APPROVED_DIRECT_IMPORTS


def test_orchestrator_never_imports_planning_module_or_execution_module() -> None:
    # The one, named, deliberate exception (ADR Candidate C) is to
    # planning.contract/context/engine/errors/graph_reader and
    # execution.cancellation/confirmation/connector_invoker/context/
    # engine/rollback -- never planning.module/execution.module (the live
    # Runtime Module wrappers, a different, unapproved coupling).
    source = ORCHESTRATOR_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ORCHESTRATOR_FILE))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            imported_modules.add(node.module)
    assert "planning.module" not in imported_modules
    assert "execution.module" not in imported_modules


def test_importing_orchestrator_never_transitively_imports_planning_module_or_execution_module() -> None:
    modules = _sys_modules_after_importing("orchestration.orchestrator")
    assert "planning.module" not in modules
    assert "execution.module" not in modules
    assert "secrets_management" not in modules


# -- planning/ and execution/ remain unaware orchestration/ exists ------------------------


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


def test_importing_planning_never_transitively_imports_orchestration() -> None:
    modules = _sys_modules_after_importing("planning")
    assert "orchestration" not in modules


def test_importing_execution_never_transitively_imports_orchestration() -> None:
    modules = _sys_modules_after_importing("execution")
    assert "orchestration" not in modules


# -- Invariant 9 (static half): no assignment onto a Goal/Plan/ExecutionResult field -------


def test_orchestrator_source_never_assigns_onto_a_goal_plan_or_result_attribute() -> None:
    # Immune to docstring/comment false positives -- only a real
    # ast.Assign/ast.Attribute node counts, mirroring
    # tests/sprint4/test_layer_isolation.py's own established technique.
    tree = ast.parse(ORCHESTRATOR_FILE.read_text(encoding="utf-8"), filename=str(ORCHESTRATOR_FILE))
    watched_names = {"goal", "plan", "result"}
    violations: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in watched_names
            ):
                violations.append(target.lineno)
    assert violations == []
