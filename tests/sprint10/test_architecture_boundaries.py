"""Sprint 10 — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology
`tests/sprint3/test_architecture_boundaries.py` through
`tests/sprint9/test_architecture_boundaries.py` already established,
applied across the whole Knowledge layer Sprint 10 built:
`knowledge/domain/`, `knowledge/builder/`, `knowledge/projection/`,
`knowledge/query/`.

**Finding, disclosed rather than silently reconciled:** this phase's own
brief states "Builder is the only component allowed to consume
AnalysisResult." Checked directly against the real source (`grep` across
every `.py` file under `knowledge/`), that is not literally true —
`knowledge/domain/contract.py` also imports `analysis.contract.
AnalysisResult` directly, via `KnowledgeSnapshot.source`. This was not an
oversight: it was Phase 1's own explicit, reviewed design ("the one place
this package directly reflects ADR-001's 'Knowledge consumes Analysis'"),
consistent with ADR-001 itself granting the whole Knowledge layer — not
only the Builder — permission to depend on `analysis.contract`. Rewriting
`KnowledgeSnapshot` to drop `.source` or reference it by id instead would
be a production-code change to already-approved, frozen Phase 1 contracts
with no genuine defect motivating it — exactly what this phase's own
brief says not to do ("Do not modify the Knowledge implementation unless
a genuine defect is discovered").

The tests below therefore validate the precise, already-approved boundary
that actually matters — the one this instruction's spirit is really
protecting — rather than the narrower literal wording: `knowledge/domain/`
and `knowledge/builder/` are the two sanctioned holders of `AnalysisResult`
(mirroring the identical reconciliation already made twice in
`tests/sprint9/test_architecture_boundaries.py`, once per Sprint 10 phase
that introduced one), and `knowledge/projection/`/`knowledge/query/` —
the two *processing* stages downstream of both — must never import
`analysis` at all. That second half is the part this phase's instruction
is actually protecting, and it holds without qualification.

Self-contained, mirroring every prior sprint-level boundary test file's
own discipline: this directory does not import fixtures or helpers from
`tests/knowledge/` (a sibling, not an ancestor) — everything needed is
rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

_KNOWLEDGE_SUBPACKAGES = {
    "domain": KNOWLEDGE_DIR / "domain",
    "builder": KNOWLEDGE_DIR / "builder",
    "projection": KNOWLEDGE_DIR / "projection",
    "query": KNOWLEDGE_DIR / "query",
}

#: `knowledge/domain/` and `knowledge/builder/` are the two sanctioned
#: holders/consumers of `analysis.contract.AnalysisResult` — see this
#: module's own docstring for why this is the precise, already-approved
#: boundary, not the literal "Builder only" wording.
_SANCTIONED_ANALYSIS_CONSUMERS = (KNOWLEDGE_DIR / "domain", KNOWLEDGE_DIR / "builder")

_FORBIDDEN_DOMAIN_IMPORTS = {
    "intelligence",
    "planning",
    "execution",
    "runtime",
    "orchestration",
    "integration",
}
_VENDOR_SDK_MODULES = {"anthropic", "openai", "google", "langchain", "litellm"}
_NETWORKING_MODULES = {"httpx", "requests", "urllib", "aiohttp"}
_GRAPH_DATABASE_MODULES = {"neo4j", "rdflib", "networkx", "sqlalchemy", "pymongo", "redis"}


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


def _direct_full_imports(py_file: Path) -> set[str]:
    """Like `_direct_top_level_imports`, but keeps the full dotted path
    (e.g. `knowledge.domain`, not just `knowledge`) — needed to tell an
    import of one of Sprint 10's four new subpackages apart from an
    import of Sprint 2/3's own, already-approved `knowledge.graph`/
    `knowledge.artifacts`, since both share the same top-level package
    name.
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


# -- (1) Knowledge imports only approved packages: none of the six forbidden ones ------------------


def test_knowledge_layer_has_no_direct_import_of_any_forbidden_package() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _FORBIDDEN_DOMAIN_IMPORTS)
        for subpackage_dir in _KNOWLEDGE_SUBPACKAGES.values()
        for py_file, imports in _all_imports_under(subpackage_dir).items()
        if imports & _FORBIDDEN_DOMAIN_IMPORTS
    }
    assert violations == {}


def test_every_knowledge_subpackage_file_was_actually_scanned() -> None:
    expected = {
        KNOWLEDGE_DIR / "domain" / "__init__.py",
        KNOWLEDGE_DIR / "domain" / "contract.py",
        KNOWLEDGE_DIR / "builder" / "__init__.py",
        KNOWLEDGE_DIR / "builder" / "builder.py",
        KNOWLEDGE_DIR / "projection" / "__init__.py",
        KNOWLEDGE_DIR / "projection" / "projector.py",
        KNOWLEDGE_DIR / "query" / "__init__.py",
        KNOWLEDGE_DIR / "query" / "service.py",
    }
    scanned: set[Path] = set()
    for subpackage_dir in _KNOWLEDGE_SUBPACKAGES.values():
        scanned |= set(_all_imports_under(subpackage_dir))
    assert expected <= scanned


@pytest.mark.parametrize("module_name", [f"knowledge.{name}" for name in _KNOWLEDGE_SUBPACKAGES])
def test_importing_each_knowledge_subpackage_never_transitively_imports_a_forbidden_package(
    module_name: str,
) -> None:
    modules = _sys_modules_after_importing(module_name)
    assert not (modules & _FORBIDDEN_DOMAIN_IMPORTS), module_name


# -- (2)/(3) Projection and Query never import analysis, at all ------------------------------------


def test_projection_never_imports_analysis() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(KNOWLEDGE_DIR / "projection").items()
        if "analysis" in imports
    }
    assert violations == {}


def test_query_never_imports_analysis() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(KNOWLEDGE_DIR / "query").items()
        if "analysis" in imports
    }
    assert violations == {}


# A transitive (sys.modules) check is deliberately not asserted here, for
# the same reason tests/sprint7/test_architecture_boundaries.py's own
# `test_importing_orchestration_never_transitively_imports_secrets_management`
# already established: `knowledge.projection`/`knowledge.query` both
# import `knowledge.domain` directly (for `KnowledgeCollection`/
# `KnowledgeSnapshot`), and `knowledge.domain` itself legitimately imports
# `analysis` (Phase 1's own approved `KnowledgeSnapshot.source` field) --
# `analysis` genuinely does appear in `sys.modules` after importing either
# one, through that one already-approved chain, not because Projection or
# Query touch `analysis` directly. The AST-scan tests above are the ones
# that actually prove the thing this phase's brief cares about; asserting
# transitive absence here would be asserting something false about an
# already-approved dependency, not catching a real boundary violation.


# -- (4) Only domain/ and builder/ consume AnalysisResult, across the entire knowledge/ tree --------


def test_only_domain_and_builder_import_analysis_anywhere_in_knowledge() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(KNOWLEDGE_DIR).items()
        if "analysis" in imports
        and not any(consumer in py_file.parents for consumer in _SANCTIONED_ANALYSIS_CONSUMERS)
    }
    assert violations == {}


def test_domain_and_builder_are_each_real_exercised_analysis_consumers() -> None:
    for consumer_dir in _SANCTIONED_ANALYSIS_CONSUMERS:
        imports = {
            py_file: file_imports
            for py_file, file_imports in _all_imports_under(consumer_dir).items()
            if "analysis" in file_imports
        }
        assert imports, f"expected at least one file under {consumer_dir} to import analysis"


# -- (5)/(6)/(7) No graph database, no networking, no provider SDK, anywhere in the Knowledge layer --


def test_no_graph_database_library_anywhere_in_the_knowledge_layer() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _GRAPH_DATABASE_MODULES)
        for subpackage_dir in _KNOWLEDGE_SUBPACKAGES.values()
        for py_file, imports in _all_imports_under(subpackage_dir).items()
        if imports & _GRAPH_DATABASE_MODULES
    }
    assert violations == {}


def test_no_networking_library_anywhere_in_the_knowledge_layer() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _NETWORKING_MODULES)
        for subpackage_dir in _KNOWLEDGE_SUBPACKAGES.values()
        for py_file, imports in _all_imports_under(subpackage_dir).items()
        if imports & _NETWORKING_MODULES
    }
    assert violations == {}


def test_no_provider_sdk_anywhere_in_the_knowledge_layer() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _VENDOR_SDK_MODULES)
        for subpackage_dir in _KNOWLEDGE_SUBPACKAGES.values()
        for py_file, imports in _all_imports_under(subpackage_dir).items()
        if imports & _VENDOR_SDK_MODULES
    }
    assert violations == {}


# -- (8) No hidden runtime dependencies -------------------------------------------------------------


@pytest.mark.parametrize("module_name", [f"knowledge.{name}" for name in _KNOWLEDGE_SUBPACKAGES])
def test_importing_each_knowledge_subpackage_never_transitively_imports_runtime(module_name: str) -> None:
    assert "runtime" not in _sys_modules_after_importing(module_name), module_name


# -- No existing package outside Knowledge consumes any of these four subpackages yet ---------------

#: Checked by full dotted path, not bare "knowledge" -- several existing
#: packages (e.g. `planning/graph_reader.py`) already legitimately import
#: Sprint 2/3's own `knowledge.graph`/`knowledge.artifacts`; that is
#: unrelated, already-approved history this test must not flag. Only an
#: import of one of Sprint 10's four *new* subpackages counts here.
_NEW_KNOWLEDGE_SUBPACKAGE_PREFIXES = tuple(f"knowledge.{name}" for name in _KNOWLEDGE_SUBPACKAGES)

_EXISTING_PACKAGE_DIRS = {
    "runtime": REPO_ROOT / "runtime",
    "planning": REPO_ROOT / "planning",
    "execution": REPO_ROOT / "execution",
    "orchestration": REPO_ROOT / "orchestration",
    "integration": REPO_ROOT / "integration",
    "intelligence": REPO_ROOT / "intelligence",
}

#: `intelligence/bridge/` (Sprint 11, Phase 1) is now a real, sanctioned
#: consumer of `knowledge.domain` (it translates `KnowledgeReference` into
#: `intelligence.contract.EvidenceItem`) — a disclosed, narrow update to
#: this test's own stale "no consumer yet" assumption, not a change to
#: this Sprint's behavior. Every other existing package remains exactly as
#: unaware of `knowledge.domain`/`builder`/`projection`/`query` as before.
_SANCTIONED_NEW_KNOWLEDGE_SUBPACKAGE_CONSUMER = REPO_ROOT / "intelligence" / "bridge"


def test_no_existing_package_imports_the_new_knowledge_subpackages_yet() -> None:
    violations: dict[str, list[str]] = {}
    for directory in _EXISTING_PACKAGE_DIRS.values():
        for py_file, imports in _all_full_imports_under(directory).items():
            if _SANCTIONED_NEW_KNOWLEDGE_SUBPACKAGE_CONSUMER in py_file.parents:
                continue
            new_subpackage_imports = {
                module for module in imports if module.startswith(_NEW_KNOWLEDGE_SUBPACKAGE_PREFIXES)
            }
            if new_subpackage_imports:
                violations[str(py_file.relative_to(REPO_ROOT))] = sorted(new_subpackage_imports)
    assert violations == {}


def test_bridge_is_a_real_exercised_consumer_of_knowledge_domain() -> None:
    # The positive complement of the test above -- proves the one
    # exception is real and exercised, not merely permitted and unused.
    imports = {
        py_file: file_imports
        for py_file, file_imports in _all_full_imports_under(
            _SANCTIONED_NEW_KNOWLEDGE_SUBPACKAGE_CONSUMER
        ).items()
        if any(module.startswith(_NEW_KNOWLEDGE_SUBPACKAGE_PREFIXES) for module in file_imports)
    }
    assert imports, "expected at least one file under intelligence/bridge/ to import knowledge.domain"
