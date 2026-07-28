"""Sprint 13 (Phase 2) — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology every
prior sprint-level boundary test file (`tests/sprint3/` through
`tests/sprint12/`) has established, scoped to Sprint 13 Phase 2's one new
package: `composition_root/`.

Validates, directly against the real source:

1. No frozen package (`analysis`, `knowledge`, `intelligence`, `planning`,
   `execution`, `orchestration`, `runtime`) imports `composition_root` —
   it is a caller, never a dependency of anything it calls.
2. `composition_root/` imports only from the seven frozen packages plus
   stdlib/pydantic/yaml-adjacent third-party packages already used
   elsewhere in this project (`pathlib`) — no new, unrelated dependency.
3. `runtime/` is byte-for-byte unchanged this phase (`git diff` empty) —
   confirmed the same way every prior sprint's own certification has
   confirmed frozen-package non-modification.

Self-contained, mirroring every prior sprint-level boundary test file's
own discipline: this directory does not import fixtures or helpers from
`tests/composition_root/` (a sibling, not an ancestor) — everything
needed is rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSITION_ROOT_DIR = REPO_ROOT / "composition_root"

_FROZEN_PACKAGE_DIRS = {
    "analysis": REPO_ROOT / "analysis",
    "knowledge": REPO_ROOT / "knowledge",
    "intelligence": REPO_ROOT / "intelligence",
    "planning": REPO_ROOT / "planning",
    "execution": REPO_ROOT / "execution",
    "orchestration": REPO_ROOT / "orchestration",
    "runtime": REPO_ROOT / "runtime",
}

#: Every top-level import `composition_root/` is allowed to have: the
#: seven frozen packages plus stdlib, and — since the Evidence Platform
#: CLI (Spec v1.1 §5) — the two Evidence Platform engines.
#:
#: **The two additions, disclosed.** `evidence` and `aggregation` are leaf
#: capabilities the CLI must reach, and §2 settled that it reaches them
#: through the Composition Root rather than by teaching `runtime/cli.py`
#: engine knowledge. That is the same role Sprint 13 created this package
#: for. The addition is confined to `composition_root/evidence_platform.py`
#: — asserted by name in `tests/evidence/` and `tests/aggregation/`'s own
#: boundary files — and `root.py`'s own Sprint 13 dependency set is
#: unchanged, which `test_sprint13_root_module_gained_no_new_dependency`
#: below verifies directly.
_ALLOWED_TOP_LEVEL_IMPORTS = {
    "__future__",
    "pathlib",
    "composition_root",  # __init__.py's own internal re-export from root.py
    "analysis",
    "knowledge",
    "intelligence",
    "planning",
    "execution",
    "orchestration",
    "runtime",
    "evidence",
    "aggregation",
}

#: `root.py`'s own allowed set, unchanged since Sprint 13. Kept separate
#: from the package-wide set above so a later file cannot widen `root.py`
#: by widening the package.
_ALLOWED_ROOT_MODULE_IMPORTS = _ALLOWED_TOP_LEVEL_IMPORTS - {"evidence", "aggregation"}

#: `runtime/cli.py`'s new `run-goal` command (Sprint 14, Phase 2, ADR-005)
#: is the one, disclosed, sanctioned consumer of `composition_root` —
#: exactly the intended purpose ADR-005 authorized. A narrow, disclosed
#: update to this Sprint's own stale "no frozen package imports
#: composition_root yet" assumption, not a change to this Sprint's own
#: behavior: `composition_root` itself is untouched, and every other
#: frozen package still imports none of it.
_SANCTIONED_COMPOSITION_ROOT_CONSUMER = REPO_ROOT / "runtime" / "cli.py"


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


# -- (1) No frozen package imports composition_root --------------------------------------------------


def test_no_frozen_package_imports_composition_root() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for package_dir in _FROZEN_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(package_dir).items()
        if "composition_root" in imports and py_file != _SANCTIONED_COMPOSITION_ROOT_CONSUMER
    }
    assert violations == {}


def test_cli_is_a_real_exercised_composition_root_consumer() -> None:
    # The positive complement of the test above -- proves the one
    # exception is real and exercised, not merely permitted and unused.
    assert "composition_root" in _direct_top_level_imports(_SANCTIONED_COMPOSITION_ROOT_CONSUMER)


def test_importing_any_frozen_package_never_transitively_imports_composition_root() -> None:
    for module_name in _FROZEN_PACKAGE_DIRS:
        modules = _sys_modules_after_importing(module_name)
        assert "composition_root" not in modules, module_name


# -- (2) composition_root/ depends on frozen packages (+ stdlib) only ---------------------------------


def test_composition_root_imports_only_frozen_packages_and_stdlib() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports - _ALLOWED_TOP_LEVEL_IMPORTS)
        for py_file, imports in _all_imports_under(COMPOSITION_ROOT_DIR).items()
        if imports - _ALLOWED_TOP_LEVEL_IMPORTS
    }
    assert violations == {}


def test_sprint13_root_module_gained_no_new_dependency() -> None:
    # The Evidence Platform additions live in their own file. Sprint 13's
    # own composition is frozen and must stay exactly as it was: this
    # asserts `root.py` never picked up `evidence` or `aggregation` when
    # the package-wide allowance widened.
    root_imports = _direct_top_level_imports(COMPOSITION_ROOT_DIR / "root.py")
    assert root_imports - _ALLOWED_ROOT_MODULE_IMPORTS == set()
    assert {"evidence", "aggregation"} & root_imports == set()


def test_composition_root_package_init_pulls_in_no_evidence_platform_engine() -> None:
    # Deliberate (see `composition_root/evidence_platform.py`'s docstring):
    # re-exporting would make `import composition_root` — which
    # `runtime/cli.py` does at module scope — transitively import both
    # engines on every invocation, including `architect doctor`.
    init_imports = _direct_top_level_imports(COMPOSITION_ROOT_DIR / "__init__.py")
    assert {"evidence", "aggregation"} & init_imports == set()


def test_composition_root_imports_from_every_frozen_package_it_claims_to() -> None:
    # The positive complement of the test above -- proves composition_root
    # actually exercises each of the seven frozen packages it depends on,
    # not merely permitted and unused.
    all_imports: set[str] = set()
    for imports in _all_imports_under(COMPOSITION_ROOT_DIR).values():
        all_imports |= imports
    for package_name in _FROZEN_PACKAGE_DIRS:
        assert package_name in all_imports, package_name


def test_every_composition_root_file_was_actually_scanned() -> None:
    expected = {
        COMPOSITION_ROOT_DIR / "__init__.py",
        COMPOSITION_ROOT_DIR / "root.py",
        COMPOSITION_ROOT_DIR / "evidence_platform.py",
    }
    assert expected <= set(_all_imports_under(COMPOSITION_ROOT_DIR))


# -- (3) runtime/ is byte-for-byte unchanged this phase ------------------------------------------------


def test_runtime_package_has_no_uncommitted_changes_other_than_cli() -> None:
    # Sprint 13's own certification found runtime/ entirely untouched.
    # Sprint 14, Phase 2 (ADR-005) has since made one, disclosed, narrow,
    # additive exception to that -- runtime/cli.py's own new `run-goal`
    # command. This test is updated, not silently left to fail: it now
    # asserts the precise, still-true claim (every *other* file under
    # runtime/ remains untouched), not the broader one Sprint 13 itself
    # made before that later, authorized change existed.
    #
    # The Evidence Platform CLI (Spec v1.1 §6) adds a second permitted
    # file, on the same terms: `runtime/output.py` holds the Output
    # Contract every command renders through. It carries strings only and
    # imports no engine, so it adds no dependency to the Runtime -- which
    # `tests/test_command_output.py::test_command_output_carries_no_engine_type`
    # asserts directly. Every other file under runtime/ remains untouched.
    changed_files = {
        line.split("|")[0].strip() for line in _git_diff_stat("runtime/").splitlines() if "|" in line
    }
    assert changed_files <= {"runtime/cli.py", "runtime/output.py"}
