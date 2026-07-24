"""Architecture boundary tests for Sprint 3, Phase 6.

Verifies, mechanically rather than by convention, the isolation the
Architecture Audit's approval of Phase 5 rested on:

  - knowledge.graph imports neither integration, runtime, nor secrets_management
  - integration imports neither knowledge.graph nor secrets_management-as-a-live-dependency*
  - secrets_management imports neither integration nor knowledge

(*secrets_management is a legitimate, documented dependency a *future*
connector's own code may take — see the Architecture Audit's finding C2 —
but nothing in integration/'s own frozen framework files does today, and
this test asserts that current, actual state, not a permanent prohibition.)

Two independent techniques are used because they catch different classes of
violation:

  - AST scanning of each file's own `import`/`from ... import` statements —
    precise about which file/line is the offender, catches direct imports.
  - A subprocess-isolated `sys.modules` check after importing only the
    package under test — catches transitive/hidden imports an AST scan of
    one package's own files cannot see (e.g. introduced via a shared
    dependency's own import chain), with a clean interpreter per check so
    results never depend on what other test modules already imported this
    session.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _direct_top_level_imports(py_file: Path) -> set[str]:
    """The set of top-level package names `py_file` directly imports,
    e.g. `from integration.contract import X` contributes `"integration"`.
    """

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


# -- Direct-import (AST) checks -----------------------------------------------------


def test_knowledge_graph_has_no_direct_import_of_forbidden_packages() -> None:
    forbidden = {"integration", "runtime", "secrets_management"}
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & forbidden)
        for py_file, imports in _all_imports_under(REPO_ROOT / "knowledge" / "graph").items()
        if imports & forbidden
    }
    assert violations == {}


def test_integration_layer_has_no_direct_import_of_knowledge_graph() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for py_file, imports in _all_imports_under(REPO_ROOT / "integration").items()
        if "knowledge" in imports
    }
    assert violations == {}


def test_secrets_management_has_no_direct_import_of_integration_or_knowledge() -> None:
    forbidden = {"integration", "knowledge"}
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & forbidden)
        for py_file, imports in _all_imports_under(REPO_ROOT / "secrets_management").items()
        if imports & forbidden
    }
    assert violations == {}


def test_no_circular_import_among_the_three_packages() -> None:
    package_dirs = {
        "knowledge_graph": REPO_ROOT / "knowledge" / "graph",
        "integration": REPO_ROOT / "integration",
        "secrets_management": REPO_ROOT / "secrets_management",
    }
    top_level_to_key = {
        "knowledge": "knowledge_graph",
        "integration": "integration",
        "secrets_management": "secrets_management",
    }

    edges: dict[str, set[str]] = {key: set() for key in package_dirs}
    for key, directory in package_dirs.items():
        for imports in _all_imports_under(directory).values():
            for imported in imports:
                target = top_level_to_key.get(imported)
                if target is not None and target != key:
                    edges[key].add(target)

    # Plain DFS cycle detection over the direct-import graph built above.
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in edges}

    def _has_cycle(node: str) -> bool:
        color[node] = GRAY
        for neighbor in edges[node]:
            if color[neighbor] == GRAY:
                return True
            if color[neighbor] == WHITE and _has_cycle(neighbor):
                return True
        color[node] = BLACK
        return False

    cyclic = [node for node in edges if color[node] == WHITE and _has_cycle(node)]
    assert cyclic == [], f"circular import detected among {edges}"


# -- Hidden/transitive-import (subprocess) checks --------------------------------------


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


def test_importing_knowledge_graph_never_transitively_imports_integration() -> None:
    modules = _sys_modules_after_importing("knowledge.graph")
    assert "integration" not in modules
    assert "secrets_management" not in modules


def test_importing_integration_never_transitively_imports_knowledge_graph() -> None:
    modules = _sys_modules_after_importing("integration")
    assert "knowledge.graph" not in modules
    assert "knowledge" not in modules


def test_importing_secrets_management_never_transitively_imports_integration_or_knowledge() -> None:
    modules = _sys_modules_after_importing("secrets_management")
    assert "integration" not in modules
    assert "knowledge" not in modules
