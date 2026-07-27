"""Sprint 18 — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior sprint-level/package-level boundary test file (`tests/sprint3/`
through `tests/synthesis/test_architecture_boundaries.py`) has
established, scoped to Sprint 18's one new package: `evaluation/`.

Validates, directly against the real source:

1. No frozen package (`analysis`, `knowledge`, `intelligence`, `planning`,
   `execution`, `orchestration`, `runtime`, `composition_root`) imports
   `evaluation` — nothing downstream (a future Recommendation Engine)
   exists yet per this Sprint's own explicit constraints, so `evaluation`
   is a leaf capability, a caller never a dependency.
2. Neither `discovery` nor `synthesis` imports `evaluation` — the
   dependency runs exactly one direction (`evaluation` depends on
   `synthesis.contract`, never the reverse).
3. `evaluation/` imports only `synthesis.contract` (its one legitimate
   frozen-package dependency — for `RepositoryFacts` and its fact types)
   and `runtime.pipeline.engine`/`runtime.modules.base`/
   `runtime.modules.manifest`/`runtime.container.di`, plus stdlib/pydantic
   — no other frozen package, no new third-party dependency. Notably
   **not** `discovery` and **not** `integration` — this engine touches no
   filesystem and constructs no connector (Architecture Evaluation Engine
   Specification v1.0's own opening note).
4. `evaluation/` never imports `analysis` — `ArchitectureEvaluation` is
   never confused with `analysis.contract.Requirement`, the same
   discipline `synthesis/`'s own boundary test already established one
   layer down.

Self-contained, mirroring `tests/synthesis/test_architecture_boundaries.py`'s
own discipline exactly: this directory does not import fixtures or
helpers from a sibling test directory — everything needed is rebuilt
here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from evaluation.contract import ArchitectureEvaluation

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = REPO_ROOT / "evaluation"
DISCOVERY_DIR = REPO_ROOT / "discovery"
SYNTHESIS_DIR = REPO_ROOT / "synthesis"

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

#: Every top-level import any file under `evaluation/` is allowed to have.
_ALLOWED_TOP_LEVEL_IMPORTS = {
    "__future__",
    "collections",
    "dataclasses",
    "datetime",
    "enum",
    "time",
    "typing",
    "uuid",
    "pydantic",
    "evaluation",  # __init__.py's own internal re-exports, sibling-module imports
    "synthesis",  # the one legitimate frozen-package dependency (RepositoryFacts and its fact types)
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


# -- (1) No frozen package imports evaluation ---------------------------------------------------------


def test_no_frozen_package_imports_evaluation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _FROZEN_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "evaluation" in imports
    }
    assert violations == {}


def test_importing_any_frozen_package_never_transitively_imports_evaluation() -> None:
    for module_name in _FROZEN_PACKAGE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "evaluation" not in modules, module_name


# -- (2) Neither discovery nor synthesis imports evaluation (one-directional dependency) ---------------


def test_discovery_does_not_import_evaluation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(DISCOVERY_DIR).items()
        if "evaluation" in imports
    }
    assert violations == {}


def test_synthesis_does_not_import_evaluation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(SYNTHESIS_DIR).items()
        if "evaluation" in imports
    }
    assert violations == {}


def test_importing_synthesis_never_transitively_imports_evaluation() -> None:
    modules = _sys_modules_after_importing("synthesis")
    assert "evaluation" not in modules


# -- (3) evaluation/ depends only on synthesis.contract + runtime (narrowly) + stdlib/pydantic ----------


def test_evaluation_imports_only_allowed_top_level_modules() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports - _ALLOWED_TOP_LEVEL_IMPORTS)
        for py_file, imports in _all_imports_under(EVALUATION_DIR).items()
        if imports - _ALLOWED_TOP_LEVEL_IMPORTS
    }
    assert violations == {}


def test_evaluation_never_imports_discovery_or_integration() -> None:
    # Architecture Evaluation touches no filesystem and constructs no
    # connector -- unlike Discovery/Synthesis, it has no legitimate reason
    # to depend on either package.
    forbidden = {"discovery", "integration"}
    all_imports: set[str] = set()
    for imports in _all_imports_under(EVALUATION_DIR).values():
        all_imports |= imports
    assert all_imports & forbidden == set()


def test_evaluation_actually_imports_synthesis_and_runtime_not_merely_permitted_and_unused() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(EVALUATION_DIR).values():
        all_imports |= imports
    assert "synthesis" in all_imports
    assert "runtime" in all_imports


def test_every_evaluation_file_was_actually_scanned() -> None:
    expected = {
        EVALUATION_DIR / "__init__.py",
        EVALUATION_DIR / "errors.py",
        EVALUATION_DIR / "contract.py",
        EVALUATION_DIR / "rules.py",
        EVALUATION_DIR / "engine.py",
        EVALUATION_DIR / "module.py",
        EVALUATION_DIR / "pipeline.py",
    }
    assert expected <= set(_all_imports_under(EVALUATION_DIR))


# -- (4) evaluation/ never imports analysis -------------------------------------------------------------


def test_evaluation_never_imports_analysis() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(EVALUATION_DIR).values():
        all_imports |= imports
    assert "analysis" not in all_imports


def test_architecture_evaluation_has_no_requirement_shaped_field() -> None:
    field_names = set(ArchitectureEvaluation.model_fields)
    assert "requirement" not in field_names
    assert "requirements" not in field_names
    assert "source_facts_id" in field_names
