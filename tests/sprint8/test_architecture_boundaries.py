"""Sprint 8 — Architecture Boundary Tests.

Reuses the exact AST-scan-plus-subprocess `sys.modules` methodology
`tests/sprint3/test_architecture_boundaries.py` through
`tests/sprint7/test_architecture_boundaries.py` already established,
applied to the five boundaries Sprint 8 introduces: (1) no existing
package is a consumer of `intelligence/` yet, (2) only `intelligence/
adapters/` may import a vendor AI SDK, (3) outside `adapters/`, no
`intelligence/` file may import a networking library, (4) `intelligence/`
imports no other domain package, and (5) the Container remains the only
runtime integration mechanism — no alternative registry/locator exists.

Self-contained, mirroring `tests/sprint7/test_architecture_boundaries.py`'s
own discipline exactly: this directory does not import fixtures or
helpers from `tests/intelligence/` (a sibling, not an ancestor) —
everything needed is rebuilt here, minimally.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from runtime.container.di import Container
from runtime.modules.manifest import ModuleManifest

from intelligence.module import CAPABILITY_INTELLIGENCE_ENGINE, IntelligenceModule

REPO_ROOT = Path(__file__).resolve().parents[2]
INTELLIGENCE_DIR = REPO_ROOT / "intelligence"
ADAPTERS_DIR = INTELLIGENCE_DIR / "adapters"

_EXISTING_PACKAGE_DIRS = {
    "runtime": REPO_ROOT / "runtime",
    "planning": REPO_ROOT / "planning",
    "execution": REPO_ROOT / "execution",
    "orchestration": REPO_ROOT / "orchestration",
    "integration": REPO_ROOT / "integration",
    "knowledge": REPO_ROOT / "knowledge",
}

#: Named in the task, plus "any future provider SDK" — the specific,
#: currently-known names are what a static AST scan can actually check;
#: a name not yet invented cannot be enumerated, which is exactly why (2)
#: also proves the *general* rule (only `adapters/` may import anything in
#: this set) rather than only checking these five literally.
_VENDOR_SDK_MODULES = {"anthropic", "openai", "google", "langchain", "litellm"}
_NETWORKING_MODULES = {"httpx", "requests", "urllib", "aiohttp"}
_FORBIDDEN_DOMAIN_IMPORTS = {"knowledge", "analysis", "planning", "execution", "orchestration"}

#: `intelligence/bridge/` (Sprint 11, Phase 1) is this package's one
#: sanctioned consumer of `knowledge` — the Knowledge -> Intelligence
#: translation layer ADR-001's own direction requires. This is a disclosed,
#: narrow update to this Sprint's own stale assumption, not a change to
#: Sprint 8's behavior: `intelligence/contract.py`, `null_engine.py`,
#: `validating.py`, `module.py`, and `adapters/` still import none of
#: `_FORBIDDEN_DOMAIN_IMPORTS`, unchanged. `analysis`/`planning`/
#: `execution`/`orchestration` remain forbidden even for `bridge/` — only
#: `knowledge` was ever authorized, and only for this one subpackage.
_SANCTIONED_KNOWLEDGE_CONSUMER = INTELLIGENCE_DIR / "bridge"


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


def _is_under_adapters(py_file: Path) -> bool:
    return "adapters" in py_file.relative_to(INTELLIGENCE_DIR).parts


# -- (1) No existing package is a consumer of intelligence/ yet -----------------------------------


def test_no_existing_package_directly_imports_intelligence() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports)
        for directory in _EXISTING_PACKAGE_DIRS.values()
        for py_file, imports in _all_imports_under(directory).items()
        if "intelligence" in imports
    }
    assert violations == {}


def test_importing_runtime_boot_never_transitively_imports_intelligence() -> None:
    modules = _sys_modules_after_importing("runtime.boot")
    assert "intelligence" not in modules


def test_importing_orchestration_never_transitively_imports_intelligence() -> None:
    modules = _sys_modules_after_importing("orchestration")
    assert "intelligence" not in modules


def test_importing_knowledge_never_transitively_imports_intelligence() -> None:
    modules = _sys_modules_after_importing("knowledge")
    assert "intelligence" not in modules


# -- (2) Only intelligence/adapters/ may import a vendor AI SDK -----------------------------------


def test_only_adapters_may_import_a_vendor_sdk() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _VENDOR_SDK_MODULES)
        for py_file, imports in _all_imports_under(INTELLIGENCE_DIR).items()
        if (imports & _VENDOR_SDK_MODULES) and not _is_under_adapters(py_file)
    }
    assert violations == {}


def test_every_intelligence_file_was_actually_scanned() -> None:
    scanned = set(_all_imports_under(INTELLIGENCE_DIR))
    expected = {
        INTELLIGENCE_DIR / name
        for name in (
            "__init__.py",
            "contract.py",
            "errors.py",
            "null_engine.py",
            "validating.py",
            "module.py",
        )
    } | {ADAPTERS_DIR / name for name in ("__init__.py", "anthropic_adapter.py")}
    assert expected <= scanned


# -- (3) Outside adapters/, no networking library may be imported ---------------------------------


def test_only_adapters_may_import_a_networking_library() -> None:
    violations = {
        str(py_file.relative_to(REPO_ROOT)): sorted(imports & _NETWORKING_MODULES)
        for py_file, imports in _all_imports_under(INTELLIGENCE_DIR).items()
        if (imports & _NETWORKING_MODULES) and not _is_under_adapters(py_file)
    }
    assert violations == {}


# -- (4) intelligence/ imports no other domain package, directly or transitively ------------------


def test_intelligence_has_no_direct_import_of_any_other_domain_package() -> None:
    violations = {}
    for py_file, imports in _all_imports_under(INTELLIGENCE_DIR).items():
        forbidden = imports & _FORBIDDEN_DOMAIN_IMPORTS
        if _SANCTIONED_KNOWLEDGE_CONSUMER in py_file.parents:
            forbidden = forbidden - {"knowledge"}
        if forbidden:
            violations[str(py_file.relative_to(REPO_ROOT))] = sorted(forbidden)
    assert violations == {}


def test_bridge_is_a_real_exercised_knowledge_consumer() -> None:
    # The positive complement of the test above -- proves the one
    # exception is real and exercised, not merely permitted and unused.
    imports = {
        py_file: file_imports
        for py_file, file_imports in _all_imports_under(_SANCTIONED_KNOWLEDGE_CONSUMER).items()
        if "knowledge" in file_imports
    }
    assert imports, "expected at least one file under intelligence/bridge/ to import knowledge"


def test_importing_intelligence_never_transitively_imports_a_forbidden_domain_package() -> None:
    modules = _sys_modules_after_importing("intelligence")
    assert not (modules & _FORBIDDEN_DOMAIN_IMPORTS)


def test_importing_intelligence_module_never_transitively_imports_a_forbidden_domain_package() -> None:
    modules = _sys_modules_after_importing("intelligence.module")
    assert not (modules & _FORBIDDEN_DOMAIN_IMPORTS)


def test_importing_anthropic_adapter_never_transitively_imports_a_forbidden_domain_package() -> None:
    modules = _sys_modules_after_importing("intelligence.adapters.anthropic_adapter")
    assert not (modules & _FORBIDDEN_DOMAIN_IMPORTS)


# -- (5) The Container remains the only runtime integration mechanism -----------------------------


def _container_register_call_sites(package_dir: Path) -> dict[Path, int]:
    sites: dict[Path, int] = {}
    for py_file in sorted(package_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register"
        )
        if count:
            sites[py_file] = count
    return sites


def test_exactly_one_container_register_call_site_exists_in_intelligence() -> None:
    sites = _container_register_call_sites(INTELLIGENCE_DIR)
    assert {str(path.relative_to(REPO_ROOT)) for path in sites} == {"intelligence/module.py"}
    assert sites[INTELLIGENCE_DIR / "module.py"] == 1


def test_no_alternative_registry_or_locator_class_is_defined_anywhere_in_intelligence() -> None:
    forbidden_name_fragments = ("registry", "container", "locator")
    violations: dict[str, list[str]] = {}
    for py_file in INTELLIGENCE_DIR.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        offenders = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(fragment in node.name.lower() for fragment in forbidden_name_fragments)
        ]
        if offenders:
            violations[str(py_file.relative_to(REPO_ROOT))] = offenders
    assert violations == {}


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="intelligence",
        display_name="Intelligence",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_INTELLIGENCE_ENGINE,),
        entry_point="module:create",
    )


def test_the_registered_capability_resolves_through_the_real_container_only() -> None:
    # An end-to-end complement to the two static checks above: the one
    # registration site (module.py) genuinely goes through
    # runtime.container.di.Container -- the same Container every other
    # Sprint's module already uses -- not a private substitute.
    module = IntelligenceModule(_manifest())
    container = Container()

    module.init(container)

    assert container.resolve(CAPABILITY_INTELLIGENCE_ENGINE) is module.engine
