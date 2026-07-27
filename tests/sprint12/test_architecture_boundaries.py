"""Sprint 12 (Phases 1-2) — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior sprint-level boundary test file (`tests/sprint3/` through
`tests/sprint11/`) has established. Phase 1 scoped this file to
`planning/strategy_intelligence.py`; Phase 2 extends it, in place, to
also cover `planning/module.py`'s own new config-driven strategy
selection — one sprint, one boundary-test file, updated per phase,
matching the precedent every prior multi-phase sprint's own boundary-test
file already set.

**Disclosed, pre-existing exception this file does NOT re-litigate:**
`planning/graph_reader.py` already imports `knowledge.graph`/
`knowledge.artifacts` directly (Sprint 4, ADR-0011) — this predates Sprint
12 entirely and is not something this phase touches or re-approves. A
direct consequence: importing `planning.strategy_intelligence` (which
imports `planning.context`, which imports `planning.graph_reader`)
*transitively* pulls `knowledge`/`knowledge.artifacts`/`knowledge.graph`
into `sys.modules` — confirmed empirically before writing this file's own
tests, exactly as `tests/sprint10/test_architecture_boundaries.py` and
`tests/sprint11/test_architecture_boundaries.py` each already had to
confirm for their own analogous already-approved chains. This file
therefore does not assert transitive absence of `knowledge` — only that
`planning/strategy_intelligence.py` itself never *directly* imports it,
and that no file anywhere in `planning/` gains a *new* dependency this
phase didn't authorize.

Validates, directly against the real source:

1. `planning/strategy_intelligence.py` imports only `planning.*` and
   `intelligence.contract` — no `knowledge`, `analysis`, `execution`,
   `runtime`, `orchestration`, `integration`, and specifically neither
   `intelligence.pipeline` nor `intelligence.bridge`.
2. No file anywhere in `planning/` (not just the new one) has gained a
   new direct import of `knowledge`, `analysis`, `execution`,
   `intelligence.pipeline`, or `intelligence.bridge` — `planning/
   graph_reader.py`'s own pre-existing `knowledge` import is the one
   named, disclosed exception.
3. `execution/` still depends on `planning/` (already true, unchanged);
   `planning/` still does not depend on `execution/` (still true, this
   phase does not change it either).
4. (Phase 2) `planning/module.py` imports exactly `intelligence.contract`
   — the same, single, already-approved Intelligence dependency Phase 1
   introduced, not a broader one. `planning/engine.py` and `planning/
   strategy.py` (both unmodified) import no part of `intelligence` at
   all — `PlanningModule` is the only Planning component aware that more
   than one `PlannerStrategy` exists or that `intelligence.contract`
   exists; `PlanningEngine` remains strategy-agnostic, exactly as before.

Self-contained, mirroring every prior sprint-level boundary test file's
own discipline: this directory does not import fixtures or helpers from
`tests/planning/` (a sibling, not an ancestor) — everything needed is
rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNING_DIR = REPO_ROOT / "planning"
EXECUTION_DIR = REPO_ROOT / "execution"
STRATEGY_INTELLIGENCE_FILE = PLANNING_DIR / "strategy_intelligence.py"
GRAPH_READER_FILE = PLANNING_DIR / "graph_reader.py"

#: Exactly what this phase's own brief names as forbidden new dependencies
#: for Planning -- not `runtime`/`orchestration`/`integration`, which
#: `planning/module.py` already, legitimately, pre-existingly depends on
#: (the standard Module-registration pattern every domain package uses,
#: Sprint 4/6, unrelated to this phase).
_FORBIDDEN_FOR_STRATEGY_INTELLIGENCE = {"knowledge", "analysis", "execution"}
_FORBIDDEN_INTELLIGENCE_SUBMODULES = ("intelligence.pipeline", "intelligence.bridge")

#: The one, pre-existing, disclosed exception to "planning/ imports none
#: of knowledge/analysis/execution" -- Sprint 4's own ADR-0011, predating
#: this Sprint entirely. Not re-approved or reconsidered here.
_PRE_EXISTING_KNOWLEDGE_CONSUMER = GRAPH_READER_FILE


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
    (e.g. `intelligence.pipeline`, not just `intelligence`).
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


# -- (1) strategy_intelligence.py imports only planning.* and intelligence.contract -----------------


def test_strategy_intelligence_imports_only_planning_and_intelligence() -> None:
    imports = _direct_top_level_imports(STRATEGY_INTELLIGENCE_FILE) - {"__future__"}
    assert imports == {"planning", "intelligence"}


def test_strategy_intelligence_does_not_import_intelligence_pipeline_or_bridge() -> None:
    full_imports = _direct_full_imports(STRATEGY_INTELLIGENCE_FILE)
    matched = {module for module in full_imports if module.startswith(_FORBIDDEN_INTELLIGENCE_SUBMODULES)}
    assert matched == set()


def test_strategy_intelligence_imports_exactly_intelligence_contract() -> None:
    full_imports = _direct_full_imports(STRATEGY_INTELLIGENCE_FILE)
    intelligence_imports = {module for module in full_imports if module.split(".")[0] == "intelligence"}
    assert intelligence_imports == {"intelligence.contract"}


def test_importing_strategy_intelligence_never_transitively_imports_analysis_execution_or_pipeline_bridge() -> (
    None
):
    # "knowledge" is deliberately excluded from this check -- see this
    # module's own docstring: it arrives legitimately, transitively,
    # through planning.context -> planning.graph_reader's own pre-existing,
    # Sprint-4-approved import, not through strategy_intelligence.py itself.
    modules = _sys_modules_after_importing("planning.strategy_intelligence")
    assert "analysis" not in modules
    assert "execution" not in modules
    assert "intelligence.pipeline" not in modules
    assert "intelligence.bridge" not in modules


# -- (2) No file anywhere in planning/ gains a new dependency this phase didn't authorize ------------


def test_no_planning_file_gains_a_new_dependency_on_knowledge_analysis_or_execution() -> None:
    violations: dict[str, list[str]] = {}
    for py_file, imports in _all_imports_under(PLANNING_DIR).items():
        if py_file == _PRE_EXISTING_KNOWLEDGE_CONSUMER:
            forbidden = imports & (_FORBIDDEN_FOR_STRATEGY_INTELLIGENCE - {"knowledge"})
        else:
            forbidden = imports & _FORBIDDEN_FOR_STRATEGY_INTELLIGENCE
        if forbidden:
            violations[str(py_file.relative_to(REPO_ROOT))] = sorted(forbidden)
    assert violations == {}


def test_no_planning_file_imports_intelligence_pipeline_or_bridge() -> None:
    violations: dict[str, list[str]] = {}
    for py_file, imports in _all_full_imports_under(PLANNING_DIR).items():
        matched = {module for module in imports if module.startswith(_FORBIDDEN_INTELLIGENCE_SUBMODULES)}
        if matched:
            violations[str(py_file.relative_to(REPO_ROOT))] = sorted(matched)
    assert violations == {}


def test_graph_reader_remains_the_only_planning_file_importing_knowledge() -> None:
    knowledge_importers = {
        str(py_file.relative_to(REPO_ROOT))
        for py_file, imports in _all_imports_under(PLANNING_DIR).items()
        if "knowledge" in imports
    }
    assert knowledge_importers == {"planning/graph_reader.py"}


# -- (3) Execution still depends on Planning; Planning still does not depend on Execution -----------


def test_execution_still_depends_on_planning() -> None:
    importers = {
        str(py_file.relative_to(REPO_ROOT))
        for py_file, imports in _all_imports_under(EXECUTION_DIR).items()
        if "planning" in imports
    }
    assert importers, "expected at least one execution/ file to still import planning"


def test_planning_still_does_not_depend_on_execution() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(PLANNING_DIR).items()
        if "execution" in imports
    }
    assert violations == {}


# -- (4) PlanningModule is the only Planning component aware of multiple strategies (Phase 2) --------

MODULE_FILE = PLANNING_DIR / "module.py"
ENGINE_FILE = PLANNING_DIR / "engine.py"
STRATEGY_FILE = PLANNING_DIR / "strategy.py"


def test_module_imports_exactly_intelligence_contract() -> None:
    full_imports = _direct_full_imports(MODULE_FILE)
    intelligence_imports = {module for module in full_imports if module.split(".")[0] == "intelligence"}
    assert intelligence_imports == {"intelligence.contract"}


def test_module_does_not_import_intelligence_pipeline_or_bridge() -> None:
    full_imports = _direct_full_imports(MODULE_FILE)
    matched = {module for module in full_imports if module.startswith(_FORBIDDEN_INTELLIGENCE_SUBMODULES)}
    assert matched == set()


def test_engine_and_strategy_remain_completely_unaware_intelligence_exists() -> None:
    for py_file in (ENGINE_FILE, STRATEGY_FILE):
        imports = _direct_top_level_imports(py_file)
        assert "intelligence" not in imports, str(py_file.relative_to(REPO_ROOT))


def test_only_module_and_strategy_intelligence_import_intelligence_anywhere_in_planning() -> None:
    importers = {
        str(py_file.relative_to(REPO_ROOT))
        for py_file, imports in _all_imports_under(PLANNING_DIR).items()
        if "intelligence" in imports
    }
    assert importers == {"planning/module.py", "planning/strategy_intelligence.py"}
