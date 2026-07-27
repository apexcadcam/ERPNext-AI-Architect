"""Recommendation Engine — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior package-level boundary test file (`tests/discovery/`,
`tests/synthesis/`, `tests/evaluation/test_architecture_boundaries.py`)
has established, scoped to this package's one new package:
`recommendation/`.

Validates, directly against the real source:

1. No frozen package (`analysis`, `knowledge`, `intelligence`, `planning`,
   `execution`, `orchestration`, `runtime`, `composition_root`) imports
   `recommendation` — nothing downstream exists yet, so `recommendation`
   is a leaf capability, a caller never a dependency.
2. None of `discovery`, `synthesis`, `evaluation` imports
   `recommendation` — the dependency runs exactly one direction
   (`recommendation` depends on `evaluation.contract`, never the reverse).
3. `recommendation/` imports only `evaluation.contract` (its one
   legitimate frozen-package dependency — for `ArchitectureEvaluation`
   and `Finding`/`Evidence`) and
   `runtime.pipeline.engine`/`runtime.modules.base`/
   `runtime.modules.manifest`/`runtime.container.di`, plus
   stdlib/pydantic — no other frozen package, no new third-party
   dependency. Notably **not** `discovery`, **not** `synthesis`, and
   **not** `integration` — this engine touches no filesystem and
   constructs no connector (Recommendation Engine Architecture
   Specification v1.0's own Scope Freeze).
4. `recommendation/` never imports `analysis` — `Recommendation` is never
   confused with `analysis.contract.Requirement`, the same discipline
   `evaluation/`'s own boundary test already established one layer down.

Self-contained, mirroring `tests/evaluation/test_architecture_boundaries.py`'s
own discipline exactly: this directory does not import fixtures or
helpers from a sibling test directory — everything needed is rebuilt
here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from recommendation.contract import RecommendationSet

REPO_ROOT = Path(__file__).resolve().parents[2]
RECOMMENDATION_DIR = REPO_ROOT / "recommendation"
DISCOVERY_DIR = REPO_ROOT / "discovery"
SYNTHESIS_DIR = REPO_ROOT / "synthesis"
EVALUATION_DIR = REPO_ROOT / "evaluation"

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

#: Every top-level import any file under `recommendation/` is allowed to have.
_ALLOWED_TOP_LEVEL_IMPORTS = {
    "__future__",
    "dataclasses",
    "datetime",
    "enum",
    "typing",
    "uuid",
    "pydantic",
    "recommendation",  # __init__.py's own internal re-exports, sibling-module imports
    "evaluation",  # the one legitimate frozen-package dependency (ArchitectureEvaluation and its fact types)
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


# -- (1) No frozen package imports recommendation -------------------------------------------------------


def test_no_frozen_package_imports_recommendation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _FROZEN_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "recommendation" in imports
    }
    assert violations == {}


def test_importing_any_frozen_package_never_transitively_imports_recommendation() -> None:
    for module_name in _FROZEN_PACKAGE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "recommendation" not in modules, module_name


# -- (2) None of discovery/synthesis/evaluation imports recommendation (one-directional dependency) -----


def test_discovery_does_not_import_recommendation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(DISCOVERY_DIR).items()
        if "recommendation" in imports
    }
    assert violations == {}


def test_synthesis_does_not_import_recommendation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(SYNTHESIS_DIR).items()
        if "recommendation" in imports
    }
    assert violations == {}


def test_evaluation_does_not_import_recommendation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(EVALUATION_DIR).items()
        if "recommendation" in imports
    }
    assert violations == {}


def test_importing_evaluation_never_transitively_imports_recommendation() -> None:
    modules = _sys_modules_after_importing("evaluation")
    assert "recommendation" not in modules


# -- (3) recommendation/ depends only on evaluation.contract + runtime (narrowly) + stdlib/pydantic ------


def test_recommendation_imports_only_allowed_top_level_modules() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports - _ALLOWED_TOP_LEVEL_IMPORTS)
        for py_file, imports in _all_imports_under(RECOMMENDATION_DIR).items()
        if imports - _ALLOWED_TOP_LEVEL_IMPORTS
    }
    assert violations == {}


def test_recommendation_never_imports_discovery_synthesis_or_integration() -> None:
    # Recommendation Engine touches no filesystem and constructs no
    # connector -- unlike Discovery/Synthesis, it has no legitimate reason
    # to depend on discovery, synthesis, or integration (Scope Freeze).
    forbidden = {"discovery", "synthesis", "integration"}
    all_imports: set[str] = set()
    for imports in _all_imports_under(RECOMMENDATION_DIR).values():
        all_imports |= imports
    assert all_imports & forbidden == set()


def test_recommendation_actually_imports_evaluation_and_runtime_not_merely_permitted_and_unused() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(RECOMMENDATION_DIR).values():
        all_imports |= imports
    assert "evaluation" in all_imports
    assert "runtime" in all_imports


def test_every_recommendation_file_was_actually_scanned() -> None:
    expected = {
        RECOMMENDATION_DIR / "__init__.py",
        RECOMMENDATION_DIR / "errors.py",
        RECOMMENDATION_DIR / "contract.py",
        RECOMMENDATION_DIR / "scoring.py",
        RECOMMENDATION_DIR / "engine.py",
        RECOMMENDATION_DIR / "module.py",
        RECOMMENDATION_DIR / "pipeline.py",
    }
    assert expected <= set(_all_imports_under(RECOMMENDATION_DIR))


# -- (4) recommendation/ never imports analysis -----------------------------------------------------------


def test_recommendation_never_imports_analysis() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(RECOMMENDATION_DIR).values():
        all_imports |= imports
    assert "analysis" not in all_imports


def test_recommendation_set_has_no_requirement_shaped_field() -> None:
    field_names = set(RecommendationSet.model_fields)
    assert "requirement" not in field_names
    assert "requirements" not in field_names
    assert "source_evaluation_id" in field_names
