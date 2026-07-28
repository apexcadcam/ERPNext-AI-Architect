"""Evidence Extraction — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior package-level boundary test file (`tests/discovery/`,
`tests/synthesis/`, `tests/evaluation/`, `tests/recommendation/`) has
established, scoped to this Sprint's one new package: `evidence/`.

Validates, directly against the real source:

1. No frozen package (`analysis`, `knowledge`, `intelligence`, `planning`,
   `execution`, `orchestration`, `runtime`, `composition_root`) imports
   `evidence`, with **exactly one named exception**: `evidence` is a leaf
   capability, a caller never a dependency.

   **The exception, disclosed rather than silently absorbed.** The
   Evidence Platform CLI (Spec v1.1 §2) needs the platform reachable from
   a terminal, and every option for doing that changes some declared
   boundary. The chosen option is the one this project already
   established twice — Sprint 13 made `composition_root` *the one place
   allowed to import frozen packages together and wire them*, and Sprint
   14 made `runtime/cli.py` a named, disclosed consumer of
   `composition_root`, updating its own boundary test in place to say so.
   `composition_root/evidence_platform.py` is that same shape, one layer
   further out, and `_SANCTIONED_EVIDENCE_CONSUMERS` below names it by
   exact path. Every other file under every frozen package — including
   every other file under `composition_root` itself — remains forbidden,
   and `test_the_sanctioned_consumer_exception_is_real_and_exercised`
   proves the exception is used rather than merely reserved.

   The transitive assertion is **not** relaxed: importing any frozen
   package, `composition_root` included, still must not pull `evidence`
   into `sys.modules`, because `composition_root/__init__.py` deliberately
   does not re-export the new functions and `runtime/cli.py` imports them
   lazily inside the commands that need them.
2. None of `discovery`, `synthesis`, `evaluation`, `recommendation`
   imports `evidence`, and `evidence` imports none of them — Evidence
   Extraction and Repository Intelligence are **sibling leaves, not a
   chain** (Specification v1.1 §12). Repository Intelligence reviews a
   *downstream* app; Evidence Extraction mines the *framework's own*
   source. Neither may depend on the other's domain logic.
3. `evidence/` imports only `integration.connectors.filesystem` (its one
   legitimate shared-infrastructure dependency, the same one
   `discovery.engine.resolve_connector` already reuses), `runtime.*`
   (pipeline/module/container), plus stdlib and pydantic — no other
   frozen package, no new third-party dependency.
4. `evidence/` never imports `analysis` — `Evidence` is never confused
   with `analysis.contract.Requirement`, the same discipline every prior
   package's own boundary test already established.

Self-contained, mirroring `tests/recommendation/test_architecture_boundaries.py`'s
own discipline exactly: this directory does not import fixtures or
helpers from a sibling test directory — everything needed is rebuilt
here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from evidence.contract import EvidenceSet

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "evidence"

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

#: The one file inside a frozen package permitted to import `evidence`,
#: named by exact repo-relative path so the exception cannot widen by
#: accident. See this module's own docstring for the full reasoning; see
#: `composition_root/evidence_platform.py`'s docstring for the design.
_SANCTIONED_EVIDENCE_CONSUMERS = frozenset({"composition_root/evidence_platform.py"})

#: Repository Intelligence's own four packages -- siblings of `evidence`,
#: never its dependencies nor its dependents (§12).
_REPOSITORY_INTELLIGENCE_DIRS = {
    "discovery": REPO_ROOT / "discovery",
    "synthesis": REPO_ROOT / "synthesis",
    "evaluation": REPO_ROOT / "evaluation",
    "recommendation": REPO_ROOT / "recommendation",
}

#: Every top-level import any file under `evidence/` is allowed to have.
_ALLOWED_TOP_LEVEL_IMPORTS = {
    "__future__",
    "ast",
    "dataclasses",
    "datetime",
    "enum",
    "hashlib",
    "json",
    "pathlib",
    "time",
    "typing",
    "uuid",
    "pydantic",
    "evidence",  # __init__.py's own internal re-exports, sibling-module imports
    "integration",  # the one legitimate shared-infrastructure dependency (FilesystemConnector)
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


def _direct_full_imports(py_file: Path) -> set[str]:
    """Full dotted module paths, not just top-level names -- required to
    check *which* `evidence` submodules the sanctioned consumer reaches
    for, since `evidence.engine` and `evidence.collectors` share a
    top-level name.
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


# -- (1) No frozen package imports evidence -------------------------------------------------------------


def test_no_frozen_package_imports_evidence_except_the_sanctioned_consumer() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _FROZEN_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "evidence" in imports and str(py_file.relative_to(REPO_ROOT)) not in _SANCTIONED_EVIDENCE_CONSUMERS
    }
    assert violations == {}


def test_the_sanctioned_consumer_exception_is_real_and_exercised() -> None:
    # An exception that nothing uses is an exception that should not exist.
    # This asserts the named file is present and does import `evidence`, so
    # the allowance above can never quietly outlive its reason.
    consumers = {
        str(py_file.relative_to(REPO_ROOT))
        for py_file, imports in _all_imports_under(REPO_ROOT / "composition_root").items()
        if "evidence" in imports
    }
    assert consumers == set(_SANCTIONED_EVIDENCE_CONSUMERS)


def test_the_sanctioned_consumer_imports_the_engine_not_a_private_internal() -> None:
    # The exception permits calling the Evidence Platform's public entry
    # points. It does not permit reaching into collectors or reimplementing
    # extraction outside the package that tests it.
    imports = _direct_full_imports(REPO_ROOT / "composition_root" / "evidence_platform.py")
    evidence_imports = {module for module in imports if module.split(".")[0] == "evidence"}
    assert evidence_imports == {
        "evidence.contract",
        "evidence.engine",
        "evidence.errors",
        "evidence.persistence",
    }
    assert "evidence.collectors" not in evidence_imports


def test_importing_any_frozen_package_never_transitively_imports_evidence() -> None:
    for module_name in _FROZEN_PACKAGE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "evidence" not in modules, module_name


# -- (2) evidence and Repository Intelligence are sibling leaves, in both directions --------------------


def test_no_repository_intelligence_package_imports_evidence() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _REPOSITORY_INTELLIGENCE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "evidence" in imports
    }
    assert violations == {}


def test_evidence_imports_no_repository_intelligence_package() -> None:
    forbidden = set(_REPOSITORY_INTELLIGENCE_DIRS)
    all_imports: set[str] = set()
    for imports in _all_imports_under(EVIDENCE_DIR).values():
        all_imports |= imports
    assert all_imports & forbidden == set()


def test_importing_any_repository_intelligence_package_never_transitively_imports_evidence() -> None:
    for module_name in _REPOSITORY_INTELLIGENCE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "evidence" not in modules, module_name


# -- (3) evidence/ depends only on integration + runtime (narrowly) + stdlib/pydantic -------------------


def test_evidence_imports_only_allowed_top_level_modules() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports - _ALLOWED_TOP_LEVEL_IMPORTS)
        for py_file, imports in _all_imports_under(EVIDENCE_DIR).items()
        if imports - _ALLOWED_TOP_LEVEL_IMPORTS
    }
    assert violations == {}


def test_evidence_actually_imports_integration_and_runtime_not_merely_permitted_and_unused() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(EVIDENCE_DIR).values():
        all_imports |= imports
    assert "integration" in all_imports
    assert "runtime" in all_imports


def test_every_evidence_file_was_actually_scanned() -> None:
    expected = {
        EVIDENCE_DIR / "__init__.py",
        EVIDENCE_DIR / "errors.py",
        EVIDENCE_DIR / "contract.py",
        EVIDENCE_DIR / "collectors.py",
        EVIDENCE_DIR / "engine.py",
        EVIDENCE_DIR / "persistence.py",
        EVIDENCE_DIR / "module.py",
        EVIDENCE_DIR / "pipeline.py",
    }
    assert expected <= set(_all_imports_under(EVIDENCE_DIR))


def test_evidence_introduces_no_new_third_party_dependency() -> None:
    # pydantic is the only third-party import permitted anywhere in this
    # package -- no database driver, no HTTP client, no parser library.
    third_party = {"sqlite3", "duckdb", "psycopg", "psycopg2", "sqlalchemy", "httpx", "requests", "yaml"}
    all_imports: set[str] = set()
    for imports in _all_imports_under(EVIDENCE_DIR).values():
        all_imports |= imports
    assert all_imports & third_party == set()


# -- (4) evidence/ never imports analysis ---------------------------------------------------------------


def test_evidence_never_imports_analysis() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(EVIDENCE_DIR).values():
        all_imports |= imports
    assert "analysis" not in all_imports


def test_evidence_set_has_no_requirement_or_finding_shaped_field() -> None:
    field_names = set(EvidenceSet.model_fields)
    assert "requirement" not in field_names
    assert "requirements" not in field_names
    assert "findings" not in field_names
    assert "evidence" in field_names
