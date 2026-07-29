"""Pattern Aggregation — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior package-level boundary test file has established, scoped to this
Sprint's one new package: `aggregation/`.

Validates, directly against the real source (Pattern Aggregation Engine
Architecture Specification v1.0 §13):

1. No frozen package imports `aggregation` -- it is a leaf capability, a
   caller never a dependency -- with **exactly one named exception**,
   `composition_root/evidence_platform.py`, disclosed rather than silently
   absorbed.

   The Evidence Platform CLI (Spec v1.1 §2) needs the platform reachable
   from a terminal, and every way of doing that changes some declared
   boundary. The chosen way is the shape this project already established
   twice: Sprint 13 made `composition_root` the one place allowed to wire
   frozen packages together, and Sprint 14 made `runtime/cli.py` a named
   consumer of `composition_root`, updating its own boundary test in place
   to say so. `_SANCTIONED_AGGREGATION_CONSUMERS` names the file by exact
   path; every other file under every frozen package stays forbidden, and
   `test_the_sanctioned_consumer_exception_is_real_and_exercised` proves
   the allowance is used rather than merely reserved.

   The transitive assertion is **not** relaxed: importing any frozen
   package still must not pull `aggregation` into `sys.modules`, because
   `composition_root/__init__.py` deliberately does not re-export the new
   functions and `runtime/cli.py` imports them lazily.
2. `aggregation` imports **none** of `discovery`/`synthesis`/`evaluation`/
   `recommendation`, and none of them imports `aggregation`. Repository
   Intelligence and the Evidence Platform are separate lineages.
3. **`aggregation` imports `evidence.contract` and `evidence.persistence`
   but never `evidence.engine` or `evidence.collectors`** -- the
   executable form of "consume persisted Evidence only". Checked by exact
   dotted path, not top-level name, since `evidence.contract` is allowed
   while `evidence.engine` is forbidden and both begin with `evidence`.
   This is the single most important boundary in this Sprint.
4. `evidence` does not import `aggregation` -- the Evidence Platform
   chain stays one-directional: Extraction -> Aggregation.
5. No new third-party dependency, and no LLM/provider import anywhere.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from aggregation.contract import PatternSet

REPO_ROOT = Path(__file__).resolve().parents[2]
AGGREGATION_DIR = REPO_ROOT / "aggregation"
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

#: The one file inside a frozen package permitted to import `aggregation`,
#: named by exact repo-relative path so the exception cannot widen by
#: accident. See this module's own docstring for the reasoning.
_SANCTIONED_AGGREGATION_CONSUMERS = frozenset({"composition_root/evidence_platform.py"})

#: Repository Intelligence's own four packages -- a separate lineage from
#: the Evidence Platform, never its dependency nor its dependent (§13).
_REPOSITORY_INTELLIGENCE_DIRS = {
    "discovery": REPO_ROOT / "discovery",
    "synthesis": REPO_ROOT / "synthesis",
    "evaluation": REPO_ROOT / "evaluation",
    "recommendation": REPO_ROOT / "recommendation",
}

#: Every top-level import any file under `aggregation/` is allowed to have.
_ALLOWED_TOP_LEVEL_IMPORTS = {
    "__future__",
    "collections",
    "dataclasses",  # resolvers.PopulationContext, mirroring evidence.collectors._FileContext
    "datetime",
    "enum",
    "hashlib",
    "json",
    "pathlib",
    "typing",
    "uuid",
    "pydantic",
    "aggregation",  # __init__.py's own re-exports, sibling-module imports
    "evidence",  # narrowed to specific submodules by its own test below
    "runtime",
}

#: The only `evidence` submodules this package may import (§13). Anything
#: that would re-run extraction is forbidden -- this engine consumes
#: persisted artifacts only.
_ALLOWED_EVIDENCE_SUBMODULES = {"evidence.contract", "evidence.persistence"}
_FORBIDDEN_EVIDENCE_SUBMODULES = {
    "evidence.engine",
    "evidence.collectors",
    "evidence.module",
    "evidence.pipeline",
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
    distinguish `evidence.contract` (allowed) from `evidence.engine`
    (forbidden).
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


def _all_full_imports_under(package_dir: Path) -> dict[Path, set[str]]:
    return {
        py_file: _direct_full_imports(py_file)
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


# -- (1) No frozen package imports aggregation ---------------------------------------------------------


def test_no_frozen_package_imports_aggregation_except_the_sanctioned_consumer() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _FROZEN_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "aggregation" in imports
        and str(py_file.relative_to(REPO_ROOT)) not in _SANCTIONED_AGGREGATION_CONSUMERS
    }
    assert violations == {}


def test_the_sanctioned_consumer_exception_is_real_and_exercised() -> None:
    # An exception nothing uses is an exception that should not exist.
    consumers = {
        str(py_file.relative_to(REPO_ROOT))
        for py_file, imports in _all_imports_under(REPO_ROOT / "composition_root").items()
        if "aggregation" in imports
    }
    assert consumers == set(_SANCTIONED_AGGREGATION_CONSUMERS)


def test_the_sanctioned_consumer_imports_the_engine_not_a_private_internal() -> None:
    # The exception permits calling public entry points. It does not permit
    # reaching into `aggregation.population` or `aggregation.resolvers` and
    # reimplementing a denominator decision outside the engine that tests it.
    imports = _direct_full_imports(REPO_ROOT / "composition_root" / "evidence_platform.py")
    aggregation_imports = {module for module in imports if module.split(".")[0] == "aggregation"}
    assert aggregation_imports == {
        "aggregation.contract",
        "aggregation.engine",
        "aggregation.errors",
        "aggregation.persistence",
    }


def test_importing_any_frozen_package_never_transitively_imports_aggregation() -> None:
    for module_name in _FROZEN_PACKAGE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "aggregation" not in modules, module_name


# -- (2) Repository Intelligence is a separate lineage, in both directions -----------------------------


def test_no_repository_intelligence_package_imports_aggregation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _REPOSITORY_INTELLIGENCE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "aggregation" in imports
    }
    assert violations == {}


def test_aggregation_imports_no_repository_intelligence_package() -> None:
    forbidden = set(_REPOSITORY_INTELLIGENCE_DIRS)
    all_imports: set[str] = set()
    for imports in _all_imports_under(AGGREGATION_DIR).values():
        all_imports |= imports
    assert all_imports & forbidden == set()


def test_importing_any_repository_intelligence_package_never_transitively_imports_aggregation() -> None:
    for module_name in _REPOSITORY_INTELLIGENCE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "aggregation" not in modules, module_name


# -- (3) Consume persisted Evidence only -- checked by exact dotted path -------------------------------


def test_aggregation_imports_only_the_allowed_evidence_submodules() -> None:
    # The single most important boundary in this Sprint. `evidence.contract`
    # and `evidence.persistence` are allowed; `evidence.engine` and
    # `evidence.collectors` are not -- and all four share the same
    # top-level name, so this must be checked by full dotted path.
    violations: dict[str, list[str]] = {}
    for py_file, imports in _all_full_imports_under(AGGREGATION_DIR).items():
        evidence_imports = {module for module in imports if module.split(".")[0] == "evidence"}
        disallowed = evidence_imports - _ALLOWED_EVIDENCE_SUBMODULES
        if disallowed:
            violations[str(py_file.relative_to(REPO_ROOT))] = sorted(disallowed)
    assert violations == {}


def test_aggregation_never_imports_any_extraction_submodule() -> None:
    # Stated positively against the forbidden set, so a future submodule
    # rename cannot silently satisfy the allow-list test above.
    all_imports: set[str] = set()
    for imports in _all_full_imports_under(AGGREGATION_DIR).values():
        all_imports |= imports
    assert all_imports & _FORBIDDEN_EVIDENCE_SUBMODULES == set()


def test_aggregation_actually_imports_evidence_contract() -> None:
    # Proves the allowed dependency is real and exercised, not merely
    # permitted and unused.
    all_imports: set[str] = set()
    for imports in _all_full_imports_under(AGGREGATION_DIR).values():
        all_imports |= imports
    assert "evidence.contract" in all_imports


def test_aggregation_actually_imports_runtime() -> None:
    all_imports: set[str] = set()
    for imports in _all_imports_under(AGGREGATION_DIR).values():
        all_imports |= imports
    assert "runtime" in all_imports


def test_aggregation_never_touches_a_source_tree_directly() -> None:
    # This engine consumes persisted artifacts; it has no business
    # constructing a connector or walking a repository.
    all_imports: set[str] = set()
    for imports in _all_imports_under(AGGREGATION_DIR).values():
        all_imports |= imports
    assert "integration" not in all_imports


# -- (4) The Evidence Platform chain stays one-directional ---------------------------------------------


def test_evidence_does_not_import_aggregation() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(EVIDENCE_DIR).items()
        if "aggregation" in imports
    }
    assert violations == {}


def test_importing_evidence_never_transitively_imports_aggregation() -> None:
    modules = _sys_modules_after_importing("evidence")
    assert "aggregation" not in modules


# -- (5) No new dependency, no LLM ----------------------------------------------------------------------


def test_aggregation_imports_only_allowed_top_level_modules() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports - _ALLOWED_TOP_LEVEL_IMPORTS)
        for py_file, imports in _all_imports_under(AGGREGATION_DIR).items()
        if imports - _ALLOWED_TOP_LEVEL_IMPORTS
    }
    assert violations == {}


def test_aggregation_introduces_no_new_third_party_dependency() -> None:
    # pydantic is the only third-party import permitted. No dataframe
    # library, no statistics package, no database driver -- the executable
    # form of the JSONL-over-database decision.
    third_party = {
        "pandas",
        "numpy",
        "scipy",
        "statistics",
        "duckdb",
        "sqlite3",
        "sqlalchemy",
        "psycopg",
        "psycopg2",
        "httpx",
        "requests",
        "yaml",
    }
    all_imports: set[str] = set()
    for imports in _all_imports_under(AGGREGATION_DIR).values():
        all_imports |= imports
    assert all_imports & third_party == set()


def test_aggregation_imports_no_llm_or_provider_library() -> None:
    # §4/§5: zero Reasoning Engine involvement. Counting is arithmetic.
    providers = {"anthropic", "openai", "google", "langchain", "litellm", "cohere", "transformers"}
    all_imports: set[str] = set()
    for imports in _all_imports_under(AGGREGATION_DIR).values():
        all_imports |= imports
    assert all_imports & providers == set()


# -- Completeness and contract shape ---------------------------------------------------------------------


def test_every_aggregation_file_was_actually_scanned() -> None:
    expected = {
        AGGREGATION_DIR / "__init__.py",
        AGGREGATION_DIR / "errors.py",
        AGGREGATION_DIR / "contract.py",
        AGGREGATION_DIR / "population.py",
        AGGREGATION_DIR / "resolvers.py",
        AGGREGATION_DIR / "inheritance.py",
        AGGREGATION_DIR / "engine.py",
        AGGREGATION_DIR / "persistence.py",
        AGGREGATION_DIR / "module.py",
        AGGREGATION_DIR / "pipeline.py",
    }
    assert expected <= set(_all_imports_under(AGGREGATION_DIR))


def test_pattern_set_has_no_candidate_rule_or_verification_field() -> None:
    # §4: Candidate Rules are Sprint 23, Verification is Sprint 24 --
    # neither is anticipated in this artifact.
    field_names = set(PatternSet.model_fields)
    for forbidden in ("candidates", "candidate_rules", "rules", "verified", "verification"):
        assert forbidden not in field_names
    assert "patterns" in field_names
    assert "skipped_aggregations" in field_names
