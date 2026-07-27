"""Sprint 11 (Phases 1-3) — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology
`tests/sprint3/test_architecture_boundaries.py` through
`tests/sprint10/test_architecture_boundaries.py` already established.
Phase 1 scoped this file to `intelligence/bridge/`; Phase 2 extended it to
also cover `intelligence/pipeline/`; Phase 3 extends it again to validate
that every provider (`null_engine.py`, `validating.py`,
`adapters/anthropic_adapter.py`) consumes only Intelligence contracts and
that Pipeline/Bridge each remain the *one* place their own responsibility
lives — one sprint, one boundary-test file, updated per phase, matching
the precedent every prior multi-phase sprint's own boundary-test file
already set.

Validates, directly against the real source:

1. `intelligence/bridge/` imports only `knowledge.*` and
   `intelligence.contract` — no `analysis`, `planning`, `execution`,
   `runtime`, `orchestration`, `integration`, no vendor SDK, no
   networking library.
2. Every other file in `intelligence/` (`contract.py`, `errors.py`,
   `null_engine.py`, `validating.py`, `module.py`, `adapters/*`, and now
   `pipeline/*`) remains exactly as Knowledge-independent as Sprint 8
   left it — `bridge/` is the *only* exception, not a loosening of the
   rest of the package. `intelligence/pipeline/` in particular never
   imports `knowledge.*` at all (see `orchestrator.py`'s own module
   docstring for why its `snapshot` parameter is typed `Any` instead).
3. `knowledge/` (every subpackage) still has zero awareness that
   `intelligence/` exists at all — the dependency direction is one-way,
   matching ADR-001's Knowledge -> Intelligence chain exactly.
4. `intelligence/bridge/` never references `IntelligenceEngine` or either
   of its concrete implementations by name — a static, structural proxy
   for this phase's own "must not invoke the IntelligenceEngine" rule:
   code that never names the engine at all cannot be calling it.
5. (Phase 2) `intelligence/pipeline/` never constructs `EvidenceItem` or
   `Candidate` directly — it may only obtain them by calling one of
   Bridge's own `translate_*` functions, proven both negatively (no
   direct `EvidenceItem(...)`/`Candidate(...)` call anywhere in
   `pipeline/`) and positively (every one of Bridge's four translators
   is actually called from `pipeline/orchestrator.py`).
6. (Phase 3) Every provider (`null_engine.py`, `validating.py`,
   `adapters/anthropic_adapter.py`) imports only `intelligence.contract`/
   `intelligence.errors` — never `knowledge`, never `analysis` — already
   implied by check (2) above but re-asserted directly here, scoped to
   exactly the three provider files this phase names, for this phase's
   own explicit "all providers consume only Intelligence contracts"
   requirement.
7. (Phase 3) `intelligence/pipeline/` is the only file anywhere in
   `intelligence/` that imports `intelligence.bridge` — Pipeline remains
   the *one* orchestration layer connecting Bridge's output to an
   engine, not one of several competing ones. Extending check (5)'s own
   "no direct `EvidenceItem`/`Candidate` construction" scan across the
   whole package (not just `pipeline/`) confirms Bridge remains the
   *one* translation layer too — no provider constructs either type
   itself; both only ever arrive as method parameters.

Self-contained, mirroring every prior sprint-level boundary test file's
own discipline: this directory does not import fixtures or helpers from
`tests/intelligence/` (a sibling, not an ancestor) — everything needed is
rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INTELLIGENCE_DIR = REPO_ROOT / "intelligence"
BRIDGE_DIR = INTELLIGENCE_DIR / "bridge"
PIPELINE_DIR = INTELLIGENCE_DIR / "pipeline"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

_FORBIDDEN_FOR_BRIDGE = {"analysis", "planning", "execution", "runtime", "orchestration", "integration"}
_VENDOR_SDK_MODULES = {"anthropic", "openai", "google", "langchain", "litellm"}
_NETWORKING_MODULES = {"httpx", "requests", "urllib", "aiohttp"}

#: Every other file in `intelligence/` -- `bridge/` is the one, sole
#: exception to "intelligence/ does not import knowledge/".
_NON_BRIDGE_INTELLIGENCE_FILES = (
    "__init__.py",
    "contract.py",
    "errors.py",
    "null_engine.py",
    "validating.py",
    "module.py",
    "adapters/__init__.py",
    "adapters/anthropic_adapter.py",
    "pipeline/__init__.py",
    "pipeline/orchestrator.py",
)

#: Bridge's own four translators -- the only legitimate source of an
#: `EvidenceItem`/`Candidate` anywhere in `intelligence/pipeline/`.
_BRIDGE_TRANSLATOR_NAMES = {
    "translate_artifact_to_candidate",
    "translate_reference_to_evidence",
    "translate_node_to_evidence",
    "translate_edge_to_evidence",
}
_EVIDENCE_AND_CANDIDATE_CONSTRUCTOR_NAMES = {"EvidenceItem", "Candidate"}

#: Names this phase's own brief forbids `intelligence/bridge/` from
#: referencing at all -- a static proxy for "must not invoke the engine."
_ENGINE_NAMES = {"IntelligenceEngine", "NullIntelligenceEngine", "ValidatingIntelligenceEngine"}

#: The three supported providers this Sprint 11 Phase 3 validates.
_PROVIDER_FILES = (
    INTELLIGENCE_DIR / "null_engine.py",
    INTELLIGENCE_DIR / "validating.py",
    INTELLIGENCE_DIR / "adapters" / "anthropic_adapter.py",
)
_FORBIDDEN_FOR_PROVIDERS = {"knowledge", "analysis"}


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


def _all_referenced_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def _direct_full_imports(py_file: Path) -> set[str]:
    """Like `_direct_top_level_imports`, but keeps the full dotted path
    (e.g. `intelligence.bridge`, not just `intelligence`) — needed to
    tell an import of `intelligence.bridge` apart from an unrelated
    import of bare `intelligence` (e.g. `from intelligence import
    IntelligenceEngine`).
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


def _all_called_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


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


# -- (1) intelligence/bridge/ imports only knowledge.* and intelligence.contract --------------------


def test_bridge_has_no_direct_import_of_any_forbidden_package() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _FORBIDDEN_FOR_BRIDGE)
        for py_file, imports in _all_imports_under(BRIDGE_DIR).items()
        if imports & _FORBIDDEN_FOR_BRIDGE
    }
    assert violations == {}


def test_every_bridge_file_was_actually_scanned() -> None:
    expected = {BRIDGE_DIR / "__init__.py", BRIDGE_DIR / "translator.py"}
    assert expected <= set(_all_imports_under(BRIDGE_DIR))


def test_bridge_has_no_vendor_sdk_or_networking_library_import() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & (_VENDOR_SDK_MODULES | _NETWORKING_MODULES))
        for py_file, imports in _all_imports_under(BRIDGE_DIR).items()
        if imports & (_VENDOR_SDK_MODULES | _NETWORKING_MODULES)
    }
    assert violations == {}


def test_importing_bridge_never_transitively_imports_a_forbidden_package() -> None:
    # "analysis" is deliberately excluded from this transitive check, for
    # the identical reason already disclosed in
    # tests/sprint10/test_architecture_boundaries.py: `intelligence.bridge`
    # imports `knowledge.domain` directly, and `knowledge.domain` itself
    # legitimately imports `analysis.contract` (Sprint 10 Phase 1's own
    # approved `KnowledgeSnapshot.source` field) -- `analysis` genuinely
    # appears in `sys.modules` through that one already-approved chain,
    # not because `bridge/` touches it directly. The direct AST-scan test
    # above already proves `bridge/` itself never writes that import.
    modules = _sys_modules_after_importing("intelligence.bridge")
    assert not (modules & (_FORBIDDEN_FOR_BRIDGE - {"analysis"}))


# -- (2) Every other intelligence/ file remains exactly as Knowledge-independent as Sprint 8 left it -


@pytest.mark.parametrize("relative_path", _NON_BRIDGE_INTELLIGENCE_FILES)
def test_non_bridge_intelligence_file_does_not_import_knowledge(relative_path: str) -> None:
    py_file = INTELLIGENCE_DIR / relative_path
    assert "knowledge" not in _direct_top_level_imports(py_file), relative_path


def test_only_bridge_imports_knowledge_anywhere_in_intelligence() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(INTELLIGENCE_DIR).items()
        if "knowledge" in imports and BRIDGE_DIR not in py_file.parents
    }
    assert violations == {}


# -- (3) knowledge/ has zero awareness intelligence/ exists ------------------------------------------


def test_knowledge_has_no_direct_import_of_intelligence() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(KNOWLEDGE_DIR).items()
        if "intelligence" in imports
    }
    assert violations == {}


def test_importing_knowledge_never_transitively_imports_intelligence() -> None:
    modules = _sys_modules_after_importing("knowledge")
    assert "intelligence" not in modules


# -- (4) intelligence/bridge/ never references the IntelligenceEngine or a concrete implementation ---


def test_bridge_never_references_the_engine_by_name() -> None:
    violations: dict[str, list[str]] = {}
    for py_file in sorted(BRIDGE_DIR.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        matched = _all_referenced_names(py_file) & _ENGINE_NAMES
        if matched:
            violations[str(py_file.relative_to(REPO_ROOT))] = sorted(matched)
    assert violations == {}


# -- (5) intelligence/pipeline/ never bypasses Bridge (Phase 2) -------------------------------------


def test_pipeline_never_constructs_evidence_or_candidate_directly() -> None:
    violations: dict[str, list[str]] = {}
    for py_file in sorted(PIPELINE_DIR.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        matched = _all_called_names(py_file) & _EVIDENCE_AND_CANDIDATE_CONSTRUCTOR_NAMES
        if matched:
            violations[str(py_file.relative_to(REPO_ROOT))] = sorted(matched)
    assert violations == {}


def test_pipeline_calls_every_one_of_bridges_translators() -> None:
    # The positive complement of the test above -- proves the pipeline
    # actually consumes Bridge's own translators rather than merely
    # avoiding a direct constructor call while still not using Bridge at
    # all.
    called = _all_called_names(PIPELINE_DIR / "orchestrator.py")
    assert _BRIDGE_TRANSLATOR_NAMES <= called


def test_every_pipeline_file_was_actually_scanned() -> None:
    expected = {PIPELINE_DIR / "__init__.py", PIPELINE_DIR / "orchestrator.py"}
    assert expected <= set(_all_imports_under(PIPELINE_DIR))


# -- (6) Every provider consumes only Intelligence contracts (Phase 3) ------------------------------


@pytest.mark.parametrize("py_file", _PROVIDER_FILES, ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_provider_does_not_import_knowledge_or_analysis(py_file: Path) -> None:
    imports = _direct_top_level_imports(py_file)
    assert not (imports & _FORBIDDEN_FOR_PROVIDERS), str(py_file.relative_to(REPO_ROOT))


@pytest.mark.parametrize(
    "module_name",
    ["intelligence.null_engine", "intelligence.validating", "intelligence.adapters.anthropic_adapter"],
)
def test_importing_each_provider_never_transitively_imports_knowledge_or_analysis(module_name: str) -> None:
    modules = _sys_modules_after_importing(module_name)
    assert not (modules & _FORBIDDEN_FOR_PROVIDERS), module_name


# -- (7) Pipeline is the only orchestration layer; Bridge is the only translation layer (Phase 3) ----


def test_pipeline_is_the_only_file_that_imports_bridge() -> None:
    bridge_importers = set()
    for py_file in sorted(INTELLIGENCE_DIR.rglob("*.py")):
        if "__pycache__" in py_file.parts or BRIDGE_DIR in py_file.parents:
            continue
        if any(module == "intelligence.bridge" for module in _direct_full_imports(py_file)):
            bridge_importers.add(str(py_file.relative_to(REPO_ROOT)))
    assert bridge_importers == {"intelligence/pipeline/orchestrator.py"}


def test_no_provider_constructs_evidence_or_candidate_directly() -> None:
    # Extends test_pipeline_never_constructs_evidence_or_candidate_directly
    # across the whole package (excluding bridge/, which is the one place
    # allowed to construct either type) -- proves Bridge remains the only
    # translation layer, not merely that Pipeline itself never bypasses it.
    violations: dict[str, list[str]] = {}
    for py_file in sorted(INTELLIGENCE_DIR.rglob("*.py")):
        if "__pycache__" in py_file.parts or BRIDGE_DIR in py_file.parents:
            continue
        matched = _all_called_names(py_file) & _EVIDENCE_AND_CANDIDATE_CONSTRUCTOR_NAMES
        if matched:
            violations[str(py_file.relative_to(REPO_ROOT))] = sorted(matched)
    assert violations == {}
