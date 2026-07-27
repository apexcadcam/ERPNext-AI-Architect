"""Sprint 17 — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior sprint-level/package-level boundary test file
(`tests/sprint3/` through `tests/discovery/test_architecture_boundaries.py`)
has established, scoped to Sprint 17's one new package: `synthesis/`.

Validates, directly against the real source:

1. No frozen package (`analysis`, `knowledge`, `intelligence`, `planning`,
   `execution`, `orchestration`, `runtime`, `composition_root`) imports
   `synthesis` — nothing downstream (Architecture Evaluation, a Product
   layer, Workflow Registry) exists yet per this Sprint's own explicit
   constraints, so `synthesis` is a leaf capability, a caller never a
   dependency.
2. `discovery` itself does not import `synthesis` — the dependency runs
   exactly one direction (`synthesis` depends on `discovery.contract`,
   never the reverse), matching Repository Discovery's own frozen status.
3. `synthesis/` imports only `discovery.contract` (its one legitimate
   frozen-package dependency — for `RepositoryInventory`/
   `RepositoryFileType`), `discovery.engine`/`discovery.errors` (reusing
   `resolve_connector` directly rather than reimplementing it),
   `integration.contract`/`integration.connectors.filesystem.connector`,
   `runtime.pipeline.engine`/`runtime.modules.base`/
   `runtime.modules.manifest`/`runtime.container.di`, and stdlib/pydantic
   — no other frozen package, no new third-party dependency.
4. `RepositoryFacts` is never confused with `analysis.contract.Requirement`
   — `synthesis/` never imports `analysis` at all.

Self-contained, mirroring `tests/discovery/test_architecture_boundaries.py`'s
own discipline exactly: this directory does not import fixtures or
helpers from a sibling test directory — everything needed is rebuilt
here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from synthesis.contract import RepositoryFacts, SynthesisStatistics

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTHESIS_DIR = REPO_ROOT / "synthesis"
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

#: Every top-level import any file under `synthesis/` is allowed to have.
_ALLOWED_TOP_LEVEL_IMPORTS = {
    "__future__",
    "ast",
    "collections",
    "dataclasses",
    "datetime",
    "enum",
    "json",
    "pathlib",
    "re",
    "time",
    "tomllib",
    "typing",
    "uuid",
    "pydantic",
    "synthesis",  # __init__.py's own internal re-exports, sibling-module imports
    "discovery",  # the one legitimate frozen-package dependency (RepositoryInventory,
    # RepositoryFileType, resolve_connector, DiscoveryError_)
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


# -- (1) No frozen package imports synthesis --------------------------------------------------------


def test_no_frozen_package_imports_synthesis() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _FROZEN_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "synthesis" in imports
    }
    assert violations == {}


def test_importing_any_frozen_package_never_transitively_imports_synthesis() -> None:
    for module_name in _FROZEN_PACKAGE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "synthesis" not in modules, module_name


# -- (2) discovery does not import synthesis (one-directional dependency) ---------------------------


def test_discovery_does_not_import_synthesis() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(DISCOVERY_DIR).items()
        if "synthesis" in imports
    }
    assert violations == {}


def test_importing_discovery_never_transitively_imports_synthesis() -> None:
    modules = _sys_modules_after_importing("discovery")
    assert "synthesis" not in modules


# -- (3) synthesis/ depends only on discovery + integration + runtime (narrowly) + stdlib/pydantic ----


def test_synthesis_imports_only_allowed_top_level_modules() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports - _ALLOWED_TOP_LEVEL_IMPORTS)
        for py_file, imports in _all_imports_under(SYNTHESIS_DIR).items()
        if imports - _ALLOWED_TOP_LEVEL_IMPORTS
    }
    assert violations == {}


def test_synthesis_never_imports_analysis_knowledge_intelligence_planning_execution_orchestration() -> None:
    forbidden = {"analysis", "knowledge", "intelligence", "planning", "execution", "orchestration"}
    all_imports: set[str] = set()
    for imports in _all_imports_under(SYNTHESIS_DIR).values():
        all_imports |= imports
    assert all_imports & forbidden == set()


def test_synthesis_actually_imports_discovery_integration_and_runtime_not_merely_permitted_and_unused() -> (
    None
):
    all_imports: set[str] = set()
    for imports in _all_imports_under(SYNTHESIS_DIR).values():
        all_imports |= imports
    assert "discovery" in all_imports
    assert "integration" in all_imports
    assert "runtime" in all_imports


def test_every_synthesis_file_was_actually_scanned() -> None:
    expected = {
        SYNTHESIS_DIR / "__init__.py",
        SYNTHESIS_DIR / "errors.py",
        SYNTHESIS_DIR / "contract.py",
        SYNTHESIS_DIR / "engine.py",
        SYNTHESIS_DIR / "module.py",
        SYNTHESIS_DIR / "pipeline.py",
    }
    assert expected <= set(_all_imports_under(SYNTHESIS_DIR))


# -- (4) RepositoryFacts is never confused with analysis.contract.Requirement -------------------------


def test_repository_facts_rejects_a_requirement_shaped_field() -> None:
    # RepositoryFacts has no field named "requirement" or "requirements" --
    # confirms the rename (v1.0 RepositoryRequirements -> v1.1 RepositoryFacts)
    # actually took effect in the schema, not merely in prose.
    field_names = set(RepositoryFacts.model_fields)
    assert "requirement" not in field_names
    assert "requirements" not in field_names
    assert "facts_id" in field_names


def test_repository_facts_rejects_an_unknown_requirement_id_field() -> None:
    with pytest.raises(ValidationError):
        RepositoryFacts(
            requirement_id="x",  # type: ignore[call-arg]
            source_inventory_id="inv-1",
            repository_root="/repo",
            synthesized_at="2026-07-27T11:00:00+00:00",
            correlation_id="corr-1",
            modules=(),
            components=(),
            apis=(),
            services=(),
            configuration=(),
            dependencies=(),
            extension_points=(),
            entry_points=(),
            unresolved=(),
            truncated=False,
            statistics=SynthesisStatistics(
                files_examined=0, files_skipped=0, files_failed=0, facts_extracted=0
            ),
        )
