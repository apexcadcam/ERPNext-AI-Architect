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

#: Every top-level import `composition_root/root.py` is allowed to have:
#: the seven frozen packages plus stdlib.
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
        if "composition_root" in imports
    }
    assert violations == {}


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
    expected = {COMPOSITION_ROOT_DIR / "__init__.py", COMPOSITION_ROOT_DIR / "root.py"}
    assert expected <= set(_all_imports_under(COMPOSITION_ROOT_DIR))


# -- (3) runtime/ is byte-for-byte unchanged this phase ------------------------------------------------


def test_runtime_package_has_no_uncommitted_changes() -> None:
    changed_files = {
        line.split("|")[0].strip() for line in _git_diff_stat("runtime/").splitlines() if "|" in line
    }
    assert changed_files == set()
