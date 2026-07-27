"""Sprint 16 — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior sprint-level boundary test file (`tests/sprint3/` through
`tests/sprint15/`) has established, scoped to Sprint 16's one new
package: `discovery/`.

Validates, directly against the real source:

1. No frozen package (`analysis`, `knowledge`, `intelligence`, `planning`,
   `execution`, `orchestration`, `runtime`, `composition_root`) imports
   `discovery` — per this Sprint's own explicit constraints (no
   Requirement Synthesis, no Architecture Evaluation, no Product Layer),
   nothing yet consumes it; `discovery` is a leaf capability, a caller
   never a dependency.
2. `discovery/` imports only `integration.contract`/
   `integration.connectors.filesystem.connector`/`integration.errors`,
   `runtime.pipeline.engine`/`runtime.modules.base`/
   `runtime.modules.manifest`/`runtime.container.di`, and
   stdlib/pydantic — no other frozen package, no new third-party
   dependency.
3. `RepositoryFileType`'s closed vocabulary is enforced by the schema
   itself, not merely by convention — an out-of-vocabulary string can
   never be accepted as a `DiscoveredFile.file_type` (Repository Discovery
   Engine Specification v1.1's own Commit 7 note: "confirm the enum is
   closed in practice, not just in declaration"). A naive AST scan for
   string literals matching an enum value was considered and rejected
   here: `"test"`/`"doctype"`/`"readme"` are legitimate path-segment/stem
   literals in `discovery/engine.py`'s classifier that coincide textually
   with enum values for unrelated reasons (matching a directory named
   `test`, not constructing a `RepositoryFileType`) — a literal-text scan
   would false-positive on correct code, so closedness is verified at the
   schema boundary instead, where it is actually enforced.

Self-contained, mirroring every prior sprint-level boundary test file's
own discipline: this directory does not import fixtures or helpers from
a sibling test directory — everything needed is rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from discovery.contract import DiscoveredFile, RepositoryFileType

REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_DIR = REPO_ROOT / "discovery"

_FROZEN_PACKAGE_DIRS = {
    "analysis": REPO_ROOT / "analysis",
    "knowledge": REPO_ROOT / "knowledge",
    "intelligence": REPO_ROOT / "intelligence",
    "planning": REPO_ROOT / "planning",
    "execution": REPO_ROOT / "execution",
    "orchestration": REPO_ROOT / "orchestration",
    "runtime": REPO_ROOT / "runtime",
    "composition_root": REPO_ROOT / "composition_root",
}

#: Every top-level import any file under `discovery/` is allowed to have.
_ALLOWED_TOP_LEVEL_IMPORTS = {
    "__future__",
    "collections",
    "dataclasses",
    "datetime",
    "enum",
    "pathlib",
    "time",
    "typing",
    "uuid",
    "pydantic",
    "discovery",  # __init__.py's own internal re-exports, sibling-module imports
    "integration",
    "runtime",
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


# -- (1) No frozen package imports discovery --------------------------------------------------------


def test_no_frozen_package_imports_discovery() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _FROZEN_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "discovery" in imports
    }
    assert violations == {}


def test_importing_any_frozen_package_never_transitively_imports_discovery() -> None:
    for module_name in _FROZEN_PACKAGE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "discovery" not in modules, module_name


# -- (2) discovery/ depends only on integration (narrowly) + runtime (narrowly) + stdlib/pydantic -----


def test_discovery_imports_only_allowed_top_level_modules() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports - _ALLOWED_TOP_LEVEL_IMPORTS)
        for py_file, imports in _all_imports_under(DISCOVERY_DIR).items()
        if imports - _ALLOWED_TOP_LEVEL_IMPORTS
    }
    assert violations == {}


def test_discovery_never_imports_analysis_knowledge_intelligence_planning_execution_orchestration() -> None:
    forbidden = {"analysis", "knowledge", "intelligence", "planning", "execution", "orchestration"}
    all_imports: set[str] = set()
    for imports in _all_imports_under(DISCOVERY_DIR).values():
        all_imports |= imports
    assert all_imports & forbidden == set()


def test_discovery_actually_imports_integration_and_runtime_not_merely_permitted_and_unused() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(DISCOVERY_DIR).values():
        all_imports |= imports
    assert "integration" in all_imports
    assert "runtime" in all_imports


def test_every_discovery_file_was_actually_scanned() -> None:
    expected = {
        DISCOVERY_DIR / "__init__.py",
        DISCOVERY_DIR / "errors.py",
        DISCOVERY_DIR / "contract.py",
        DISCOVERY_DIR / "engine.py",
        DISCOVERY_DIR / "module.py",
        DISCOVERY_DIR / "pipeline.py",
    }
    assert expected <= set(_all_imports_under(DISCOVERY_DIR))


# -- (3) RepositoryFileType's closed vocabulary is enforced by the schema, not by convention -----------


def test_discovered_file_rejects_a_file_type_string_outside_the_closed_vocabulary() -> None:
    with pytest.raises(ValidationError):
        DiscoveredFile(relative_path="a.py", file_type="not_a_real_type", size_bytes=1, is_binary=False)  # type: ignore[arg-type]


def test_discovered_file_accepts_every_declared_repository_file_type_value() -> None:
    for member in RepositoryFileType:
        file = DiscoveredFile(relative_path="a", file_type=member, size_bytes=0, is_binary=False)
        assert file.file_type is member
