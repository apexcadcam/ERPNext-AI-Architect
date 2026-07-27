"""Sprint 14 (Phase 2) — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior sprint-level boundary test file (`tests/sprint3/` through
`tests/sprint13/`) has established, scoped to Sprint 14 Phase 2's one
change: the new `run-goal` command in `runtime/cli.py` (ADR-005).

**Reconciling this phase's own literal wording, disclosed rather than
silently smoothed over:** this phase's own brief says "CLI imports
Composition Root only." Checked directly against the real source, that
is not literally true — `runtime/cli.py` also imports `analysis.
requirements.raw.RawRequirement`, `planning.contract.{Goal,
CapabilityDescriptor}`, and `orchestration.contract.GoalRunResult`. This
is not an oversight: the same phase's own "Implementation Rules" section
explicitly permits exactly this ("It MAY: ... construct RawRequirement
... construct Goal ... construct CapabilityDescriptor objects ...
[render] GoalRunResult"). All four are plain, frozen *data* contracts
with zero behavior — never `PlanningEngine`, `ExecutionEngine`,
`GoalOrchestrator`, or any part of `intelligence.pipeline`/`intelligence.
bridge`. The tests below therefore validate the precise, already-approved
boundary the brief's own "MUST NOT" list actually names — the five
specific engine/orchestrator/pipeline exclusions — rather than the
narrower literal "Composition Root only" wording, exactly mirroring the
identical reconciliation already made for "Builder is the only
component..." (Sprint 10) and "no other Intelligence package..."
(Sprint 11).

Validates, directly against the real source:

1. `runtime/cli.py` imports `composition_root` (positive proof the new
   command actually uses it).
2. `runtime/cli.py` never imports `planning.engine`, `execution.engine`,
   `orchestration.orchestrator`, `intelligence.pipeline`, or
   `intelligence.bridge` — the five specific exclusions this phase's own
   brief names, checked by full dotted path so a legitimate import of
   `planning.contract`/`execution.lifecycle`/`orchestration.contract`
   (different submodules of the same top-level packages) is never
   confused with the forbidden ones.
3. No frozen package (`analysis`, `knowledge`, `intelligence`, `planning`,
   `execution`, `orchestration`, `integration`, `composition_root`)
   imports `runtime.cli` — the dependency direction stays one-way.
4. Every other file under `runtime/` is untouched this phase — only
   `runtime/cli.py` changed (the one, narrow, ADR-005-authorized
   exception to the freeze).

Self-contained, mirroring every prior sprint-level boundary test file's
own discipline: this directory does not import fixtures or helpers from
`tests/test_cli.py` (a sibling, not an ancestor) — everything needed is
rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "runtime"
CLI_FILE = RUNTIME_DIR / "cli.py"

_FROZEN_PACKAGE_DIRS = {
    "analysis": REPO_ROOT / "analysis",
    "knowledge": REPO_ROOT / "knowledge",
    "intelligence": REPO_ROOT / "intelligence",
    "planning": REPO_ROOT / "planning",
    "execution": REPO_ROOT / "execution",
    "orchestration": REPO_ROOT / "orchestration",
    "integration": REPO_ROOT / "integration",
    "composition_root": REPO_ROOT / "composition_root",
}

#: The five specific exclusions this phase's own brief names, by full
#: dotted module path.
_FORBIDDEN_SUBMODULES = (
    "planning.engine",
    "execution.engine",
    "orchestration.orchestrator",
    "intelligence.pipeline",
    "intelligence.bridge",
)


def _direct_full_imports(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module)
    return modules


def _direct_top_level_imports(py_file: Path) -> set[str]:
    return {module.split(".")[0] for module in _direct_full_imports(py_file)}


def _all_imports_under(package_dir: Path) -> dict[Path, set[str]]:
    return {
        py_file: _direct_top_level_imports(py_file)
        for py_file in sorted(package_dir.rglob("*.py"))
        if "__pycache__" not in py_file.parts
    }


def _git_diff_stat(path: str) -> str:
    result = subprocess.run(
        ["git", "diff", "--stat", "--", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


# -- (1) runtime/cli.py imports composition_root -----------------------------------------------------


def test_cli_imports_composition_root() -> None:
    assert "composition_root" in _direct_top_level_imports(CLI_FILE)


# -- (2) runtime/cli.py never imports the five specific exclusions -----------------------------------


def test_cli_never_imports_the_five_forbidden_submodules() -> None:
    full_imports = _direct_full_imports(CLI_FILE)
    matched = {module for module in full_imports if module in _FORBIDDEN_SUBMODULES}
    assert matched == set()


# A transitive (sys.modules) check is deliberately not asserted here, for
# the same reason already established in every prior multi-phase sprint's
# own boundary file (first disclosed in tests/sprint7/test_architecture_
# boundaries.py's own test_importing_orchestration_never_transitively_
# imports_secrets_management): confirmed empirically before writing this
# comment, `import runtime.cli` genuinely pulls all five of
# `planning.engine`, `execution.engine`, `orchestration.orchestrator`,
# `intelligence.pipeline`, and `intelligence.bridge` into `sys.modules` --
# not because `runtime/cli.py` imports any of them directly, but because
# `composition_root` (Sprint 13, already approved, frozen) legitimately
# imports all five itself (`orchestration.orchestrator.GoalOrchestrator`
# for its own type hint, `planning.module` which imports `planning.
# engine`, `intelligence.pipeline` which imports `intelligence.bridge`
# internally, etc.). Asserting transitive absence here would be asserting
# something false about an already-approved dependency chain, not
# catching a real boundary violation. The direct AST-scan test above is
# the one that actually proves what this phase's brief cares about:
# `runtime/cli.py` itself never writes any of these five imports.


# -- (3) No frozen package imports runtime.cli --------------------------------------------------------


def test_no_frozen_package_imports_runtime_cli() -> None:
    # "runtime" broadly (e.g. runtime.container.di, runtime.modules.base)
    # is already legitimately imported by several frozen packages' own
    # Module classes -- only a direct import of runtime.cli itself would
    # violate this boundary, hence the full-dotted-path check rather than
    # a bare top-level "runtime" membership test.
    cli_importers: dict[str, list[str]] = {}
    for package_dir in _FROZEN_PACKAGE_DIRS.values():
        for py_file in sorted(package_dir.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            if "runtime.cli" in _direct_full_imports(py_file):
                cli_importers[str(py_file.relative_to(REPO_ROOT))] = ["runtime.cli"]
    assert cli_importers == {}


# -- (4) Only runtime/cli.py changed this phase ------------------------------------------------------


def test_only_cli_file_changed_under_runtime_this_phase() -> None:
    changed_files = {
        line.split("|")[0].strip() for line in _git_diff_stat("runtime/").splitlines() if "|" in line
    }
    assert changed_files <= {"runtime/cli.py"}


# A "positive complement" test asserting `_git_diff_stat("runtime/cli.py") != ""`
# was removed here during release reconstruction: it asserted this phase's
# change was genuinely *uncommitted*, which is definitionally false once
# this file is part of a committed history and would fail forever after.
# `test_cli_imports_composition_root` above already proves the same
# underlying fact (the change is real, not merely permitted and unused)
# through a structural, timeless check instead of a live git-diff one.
