"""Sprint 9 — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology
`tests/sprint3/test_architecture_boundaries.py` through
`tests/sprint8/test_architecture_boundaries.py` already established,
applied to the boundaries Sprint 9 introduces: (1) `analysis/` (whole and
per-subpackage) imports none of the seven forbidden domain packages,
direct or transitive; (2) no `analysis/` file imports a provider SDK,
network library, HTTP client, or AI library; (3) `analysis/similarity/`
depends only on `analysis.contract` — not `analysis.erpnext`, not
`analysis.requirements`; (4) `analysis/requirements/` does not depend on
`analysis/erpnext/`, and (5) `analysis/erpnext/` does not depend on
`analysis/requirements/` — proving both possible directions of the one
dependency this Sprint could have accidentally introduced between its two
independent extraction sources; (6) the whole `analysis/` internal import
graph is acyclic; and (7) no existing package consumes `analysis/`
*except* the named, ADR-001-sanctioned exceptions — `knowledge/domain/`
(Sprint 10 Phase 1) and `knowledge/builder/` (Sprint 10 Phase 2) — the
same "named legitimate consumers, everything else still forbidden" shape
`tests/sprint7/test_architecture_boundaries.py` already established for
`orchestration/`'s own two sanctioned imports. This item's own check has
been updated twice now, once per Sprint 10 phase that introduced a new
real consumer — each a stale-assumption fix necessitated by ADR-001
(already accepted before either update), not a new design decision;
Sprint 9's own behavior is unchanged both times.

Self-contained, mirroring `tests/sprint7/test_architecture_boundaries.py`'s
and `tests/sprint8/test_architecture_boundaries.py`'s own discipline
exactly: this directory does not import fixtures or helpers from
`tests/analysis/` (a sibling, not an ancestor) — everything needed is
rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "analysis"

_EXISTING_PACKAGE_DIRS = {
    "runtime": REPO_ROOT / "runtime",
    "planning": REPO_ROOT / "planning",
    "execution": REPO_ROOT / "execution",
    "orchestration": REPO_ROOT / "orchestration",
    "integration": REPO_ROOT / "integration",
    "knowledge": REPO_ROOT / "knowledge",
    "intelligence": REPO_ROOT / "intelligence",
}

_FORBIDDEN_DOMAIN_IMPORTS = {
    "intelligence",
    "planning",
    "execution",
    "runtime",
    "orchestration",
    "integration",
    "knowledge",
}
_VENDOR_SDK_MODULES = {"anthropic", "openai", "google", "langchain", "litellm"}
_NETWORKING_MODULES = {"httpx", "requests", "urllib", "aiohttp"}

#: Every `analysis/` submodule's *own* internal package, keyed by its
#: dotted module name -- the source-of-truth allowed-edge map §6 checks
#: the real import graph against.
_ANALYSIS_SUBMODULES = (
    "analysis.contract",
    "analysis.erpnext.metadata",
    "analysis.erpnext.extractor",
    "analysis.requirements.raw",
    "analysis.requirements.analyzer",
    "analysis.similarity.comparator",
)


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


def _direct_full_imports(py_file: Path) -> set[str]:
    """Like `_direct_top_level_imports`, but keeps the full dotted path
    (e.g. `analysis.erpnext.metadata`, not just `analysis`) -- needed to
    tell `analysis/similarity/` importing `analysis.contract` apart from
    it importing `analysis.erpnext`, since both start with the same
    top-level package name.
    """

    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module)
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


# -- (1) analysis/ imports none of the seven forbidden domain packages ----------------------------


def test_analysis_has_no_direct_import_of_any_forbidden_package() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _FORBIDDEN_DOMAIN_IMPORTS)
        for py_file, imports in _all_imports_under(ANALYSIS_DIR).items()
        if imports & _FORBIDDEN_DOMAIN_IMPORTS
    }
    assert violations == {}


def test_every_analysis_file_was_actually_scanned() -> None:
    scanned = set(_all_imports_under(ANALYSIS_DIR))
    expected = {ANALYSIS_DIR / "__init__.py", ANALYSIS_DIR / "contract.py"}
    for subpackage in ("erpnext", "requirements", "similarity"):
        expected.add(ANALYSIS_DIR / subpackage / "__init__.py")
    expected |= {
        ANALYSIS_DIR / "erpnext" / "metadata.py",
        ANALYSIS_DIR / "erpnext" / "extractor.py",
        ANALYSIS_DIR / "requirements" / "raw.py",
        ANALYSIS_DIR / "requirements" / "analyzer.py",
        ANALYSIS_DIR / "similarity" / "comparator.py",
    }
    assert expected <= scanned


def test_importing_analysis_never_transitively_imports_a_forbidden_package() -> None:
    modules = _sys_modules_after_importing("analysis")
    assert not (modules & _FORBIDDEN_DOMAIN_IMPORTS)


def test_importing_each_analysis_subpackage_never_transitively_imports_a_forbidden_package() -> None:
    for module_name in ("analysis.erpnext", "analysis.requirements", "analysis.similarity"):
        modules = _sys_modules_after_importing(module_name)
        assert not (modules & _FORBIDDEN_DOMAIN_IMPORTS), module_name


# -- (2) No analysis/ file imports a vendor SDK, network, or HTTP library --------------------------


def test_analysis_has_no_vendor_sdk_or_network_import_anywhere() -> None:
    forbidden = _VENDOR_SDK_MODULES | _NETWORKING_MODULES
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & forbidden)
        for py_file, imports in _all_imports_under(ANALYSIS_DIR).items()
        if imports & forbidden
    }
    assert violations == {}


# -- (3)-(5) Internal dependency direction rules ---------------------------------------------------


def test_similarity_depends_only_on_analysis_contract() -> None:
    imports = _direct_full_imports(ANALYSIS_DIR / "similarity" / "comparator.py")
    analysis_imports = {
        module for module in imports if module == "analysis" or module.startswith("analysis.")
    }
    assert analysis_imports <= {"analysis", "analysis.contract"}


def test_requirements_does_not_depend_on_erpnext() -> None:
    for filename in ("raw.py", "analyzer.py"):
        imports = _direct_full_imports(ANALYSIS_DIR / "requirements" / filename)
        assert not any(module.startswith("analysis.erpnext") for module in imports)


def test_erpnext_does_not_depend_on_requirements() -> None:
    for filename in ("metadata.py", "extractor.py"):
        imports = _direct_full_imports(ANALYSIS_DIR / "erpnext" / filename)
        assert not any(module.startswith("analysis.requirements") for module in imports)


# -- (6) The whole analysis/ internal import graph is acyclic --------------------------------------


def _module_path(dotted: str) -> Path:
    return ANALYSIS_DIR.parent / Path(*dotted.split("."))


def _internal_analysis_imports(dotted_module: str) -> set[str]:
    """Every `analysis.*` module this one directly imports, restricted to
    the set of modules this test actually tracks (`_ANALYSIS_SUBMODULES`).
    """

    py_file = _module_path(dotted_module).with_suffix(".py")
    full_imports = _direct_full_imports(py_file)
    return {
        module
        for module in full_imports
        if module != dotted_module
        and any(
            module == candidate or module.startswith(candidate + ".") for candidate in _ANALYSIS_SUBMODULES
        )
    } & set(_ANALYSIS_SUBMODULES)


def test_analysis_internal_import_graph_is_acyclic() -> None:
    graph = {module: _internal_analysis_imports(module) for module in _ANALYSIS_SUBMODULES}

    visiting: set[str] = set()
    visited: set[str] = set()

    def _visit(node: str) -> None:
        if node in visited:
            return
        assert node not in visiting, f"cycle detected: revisited '{node}' while still visiting it"
        visiting.add(node)
        for dependency in graph[node]:
            _visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for module in _ANALYSIS_SUBMODULES:
        _visit(module)

    assert visited == set(_ANALYSIS_SUBMODULES)


# -- (7) No existing package consumes analysis/ except the ADR-001-sanctioned exceptions ----------

#: `knowledge/domain/` (Sprint 10 Phase 1) and `knowledge/builder/`
#: (Sprint 10 Phase 2) are the two named, ADR-001-sanctioned consumers of
#: `analysis.contract` — this set grows only when a later phase adds
#: another one, exactly as explicitly authorized at the time, never
#: silently. Everything else remains forbidden.
_SANCTIONED_ANALYSIS_CONSUMERS = (
    REPO_ROOT / "knowledge" / "domain",
    REPO_ROOT / "knowledge" / "builder",
)


def test_no_existing_package_directly_imports_analysis_except_the_sanctioned_ones() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for directory in _EXISTING_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(directory).items()
        if "analysis" in imports
        and not any(consumer in py_file.parents for consumer in _SANCTIONED_ANALYSIS_CONSUMERS)
    }
    assert violations == {}


@pytest.mark.parametrize("consumer_dir", _SANCTIONED_ANALYSIS_CONSUMERS)
def test_each_sanctioned_package_is_a_real_exercised_analysis_consumer(consumer_dir: Path) -> None:
    # The positive complement of the test above -- proves each exception
    # is real and exercised, not merely permitted and unused.
    imports = {
        py_file: file_imports
        for py_file, file_imports in _all_imports_under(consumer_dir).items()
        if "analysis" in file_imports
    }
    assert imports, "expected at least one knowledge/domain/ file to import analysis"


def test_importing_runtime_boot_never_transitively_imports_analysis() -> None:
    modules = _sys_modules_after_importing("runtime.boot")
    assert "analysis" not in modules


def test_importing_intelligence_never_transitively_imports_analysis() -> None:
    modules = _sys_modules_after_importing("intelligence")
    assert "analysis" not in modules
