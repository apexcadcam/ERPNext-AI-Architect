"""Tests for `synthesis.engine` (Requirement Synthesis Engine Specification v1.1 §4, §5, §7)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from discovery.contract import DiscoveryRequest
from discovery.engine import discover_repository
from synthesis.contract import ExtractionMethod, SynthesisRequest
from synthesis.engine import (
    Budget,
    extract_apis,
    extract_components,
    extract_dependencies,
    extract_hooks,
    identify_modules,
    partition_inventory,
    resolve_connector,
    synthesize_requirements,
)
from synthesis.errors import RepositoryInventoryStaleError

# -- Fixture ---------------------------------------------------------------------------------------

_HOOKS_PY = """
app_name = "test_app"
app_title = "Test App"
scheduler_events = {
    "daily": ["test_app.tasks.daily_cleanup"],
}
doc_events = {
    "Sales Invoice": {"on_submit": "test_app.events.on_submit_handler"},
}
override_whitelisted_methods = {
    "frappe.desk.desktop.get_desktop_page": "test_app.overrides.get_desktop_page_override",
}
"""

_OVERRIDES_PY = """
import frappe


@frappe.whitelist()
@frappe.read_only()
def get_desktop_page_override(page):
    return {}


def _private_helper():
    pass
"""

_DOCTYPE_JSON = '{"name": "My DocType", "module": "Test App"}'
_PYPROJECT_TOML = '[project]\nname = "test_app"\ndependencies = ["pydantic>=2.6", "PyYAML>=6.0"]\n'
_PACKAGE_JSON = '{"dependencies": {"vue": "^3.0.0"}, "devDependencies": {"eslint": "^8.0.0"}}'
_REQUIREMENTS_TXT = "frappe\nrequests>=2.0\n# a comment\n\n"


def _build_test_app(root: Path) -> None:
    app = root / "test_app"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "hooks.py").write_text(_HOOKS_PY)
    (app / "overrides.py").write_text(_OVERRIDES_PY)
    doctype_dir = app / "doctype" / "my_doctype"
    doctype_dir.mkdir(parents=True)
    (doctype_dir / "my_doctype.json").write_text(_DOCTYPE_JSON)
    (root / "pyproject.toml").write_text(_PYPROJECT_TOML)
    (root / "package.json").write_text(_PACKAGE_JSON)
    (root / "requirements.txt").write_text(_REQUIREMENTS_TXT)


def _synthesis_request(root: Path, **overrides: object) -> SynthesisRequest:
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(root), correlation_id="corr-1", requested_by="test")
    )
    defaults: dict[str, object] = {
        "repository_inventory": inventory,
        "correlation_id": "corr-1",
        "requested_by": "test-suite",
    }
    defaults.update(overrides)
    return SynthesisRequest(**defaults)  # type: ignore[arg-type]


# -- Stage 1: partition_inventory --------------------------------------------------------------------


def test_partition_inventory_groups_by_file_type(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )

    partitioned = partition_inventory(inventory)

    from discovery.contract import RepositoryFileType

    assert any(f.relative_path.endswith("hooks.py") for f in partitioned[RepositoryFileType.HOOK])
    assert any(f.relative_path.endswith(".json") for f in partitioned[RepositoryFileType.DOCTYPE])


# -- Stage 2: identify_modules ------------------------------------------------------------------------


def test_identify_modules_finds_the_python_package(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )

    modules = identify_modules(inventory)

    package_modules = [m for m in modules if m.module_kind == "python_package"]
    assert any(m.relative_path == "test_app" for m in package_modules)


def test_identify_modules_finds_the_frappe_app_via_hooks_py_presence(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )

    modules = identify_modules(inventory)

    frappe_apps = [m for m in modules if m.module_kind == "frappe_app"]
    assert frappe_apps == [m for m in modules if m.name == "test_app" and m.module_kind == "frappe_app"]
    assert len(frappe_apps) == 1


def test_identify_modules_does_not_tag_a_directory_without_hooks_py_as_a_frappe_app(
    tmp_path: Path,
) -> None:
    _build_test_app(tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.py").write_text("x")
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )

    modules = identify_modules(inventory)

    assert not any(m.name == "scripts" and m.module_kind == "frappe_app" for m in modules)


# -- Stage 3: resolve_connector (reused from discovery, wrapped error type) --------------------------


def test_resolve_connector_wraps_discovery_error_as_synthesis_error(tmp_path: Path) -> None:
    with pytest.raises(RepositoryInventoryStaleError):
        resolve_connector(str(tmp_path / "missing"))


def test_resolve_connector_succeeds_for_a_real_directory(tmp_path: Path) -> None:
    connector = resolve_connector(str(tmp_path))
    assert connector.health_check().healthy is True


# -- Stage 4: extract_hooks -----------------------------------------------------------------------


def test_extract_hooks_extracts_config_service_extension_and_entry_point_facts(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    from discovery.contract import RepositoryFileType

    partitioned = partition_inventory(inventory)
    connector = resolve_connector(inventory.repository_root)

    configuration, services, extension_points, entry_points, unresolved = extract_hooks(
        partitioned[RepositoryFileType.HOOK], connector
    )

    assert unresolved == ()
    assert any(f.key == "app_name" and f.value == "test_app" for f in configuration)
    assert any(
        f.name == "test_app.tasks.daily_cleanup" and f.declared_via == "scheduler_events" for f in services
    )
    assert any(
        f.name == "test_app.events.on_submit_handler" and f.extension_kind == "doc_event"
        for f in extension_points
    )
    assert any(
        f.name == "frappe.desk.desktop.get_desktop_page" and f.extension_kind == "override_whitelisted_method"
        for f in extension_points
    )
    assert any(f.name == "hooks.py" and f.entry_kind == "frappe_app_entry" for f in entry_points)


def test_extract_hooks_records_a_syntax_error_as_unresolved_without_raising(tmp_path: Path) -> None:
    app = tmp_path / "broken_app"
    app.mkdir()
    (app / "hooks.py").write_text("this is not : valid python (((")
    from discovery.contract import DiscoveredFile, RepositoryFileType

    connector = resolve_connector(str(tmp_path))
    broken_file = DiscoveredFile(
        relative_path="broken_app/hooks.py", file_type=RepositoryFileType.HOOK, size_bytes=10, is_binary=False
    )

    configuration, services, extension_points, entry_points, unresolved = extract_hooks(
        (broken_file,), connector
    )

    assert configuration == () and services == () and extension_points == () and entry_points == ()
    assert len(unresolved) == 1
    assert unresolved[0].relative_path == "broken_app/hooks.py"


# -- Stage 5: extract_components -------------------------------------------------------------------


def test_extract_components_extracts_the_doctype_name(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    from discovery.contract import RepositoryFileType

    partitioned = partition_inventory(inventory)
    connector = resolve_connector(inventory.repository_root)

    components, unresolved = extract_components(partitioned[RepositoryFileType.DOCTYPE], connector)

    assert unresolved == ()
    assert any(c.name == "My DocType" and c.component_kind == "doctype" for c in components)


def test_extract_components_records_malformed_json_as_unresolved(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    app = tmp_path / "app"
    (app / "doctype" / "bad").mkdir(parents=True)
    (app / "doctype" / "bad" / "bad.json").write_text("{not valid json")
    connector = resolve_connector(str(tmp_path))
    bad_file = DiscoveredFile(
        relative_path="app/doctype/bad/bad.json",
        file_type=RepositoryFileType.DOCTYPE,
        size_bytes=10,
        is_binary=False,
    )

    components, unresolved = extract_components((bad_file,), connector)

    assert components == ()
    assert len(unresolved) == 1


# -- Stage 6: extract_apis -----------------------------------------------------------------------------


def test_extract_apis_finds_the_whitelisted_function_only(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    from discovery.contract import RepositoryFileType

    partitioned = partition_inventory(inventory)
    connector = resolve_connector(inventory.repository_root)

    apis, unresolved = extract_apis(partitioned[RepositoryFileType.PYTHON_SOURCE], connector)

    assert unresolved == ()
    names = {a.name for a in apis}
    assert "get_desktop_page_override" in names
    assert "_private_helper" not in names


def test_extract_apis_captures_the_signature(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    from discovery.contract import RepositoryFileType

    partitioned = partition_inventory(inventory)
    connector = resolve_connector(inventory.repository_root)

    apis, _ = extract_apis(partitioned[RepositoryFileType.PYTHON_SOURCE], connector)

    override = next(a for a in apis if a.name == "get_desktop_page_override")
    assert override.signature == "(page)"
    assert override.detection_method is ExtractionMethod.DETERMINISTIC


# -- Stage 7: extract_dependencies -----------------------------------------------------------------


def test_extract_dependencies_from_pyproject_toml(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    from discovery.contract import RepositoryFileType

    partitioned = partition_inventory(inventory)
    connector = resolve_connector(inventory.repository_root)

    dependencies, unresolved = extract_dependencies(partitioned[RepositoryFileType.CONFIG], connector)

    assert unresolved == ()
    python_deps = {d.name: d.version_constraint for d in dependencies if d.dependency_kind == "python"}
    assert python_deps.get("pydantic") == ">=2.6"
    assert "requests" in python_deps  # from requirements.txt


def test_extract_dependencies_from_package_json(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    from discovery.contract import RepositoryFileType

    partitioned = partition_inventory(inventory)
    connector = resolve_connector(inventory.repository_root)

    dependencies, _ = extract_dependencies(partitioned[RepositoryFileType.CONFIG], connector)

    js_deps = {d.name for d in dependencies if d.dependency_kind == "javascript"}
    assert "vue" in js_deps
    assert "eslint" in js_deps


def test_extract_dependencies_records_malformed_toml_as_unresolved(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "pyproject.toml").write_text("this = is [ not valid toml")
    connector = resolve_connector(str(tmp_path))
    bad_file = DiscoveredFile(
        relative_path="pyproject.toml", file_type=RepositoryFileType.CONFIG, size_bytes=10, is_binary=False
    )

    dependencies, unresolved = extract_dependencies((bad_file,), connector)

    assert dependencies == ()
    assert len(unresolved) == 1


# -- synthesize_requirements -- end to end -----------------------------------------------------------


def test_synthesize_requirements_end_to_end(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    request = _synthesis_request(tmp_path)

    facts = synthesize_requirements(request)

    assert facts.source_inventory_id == request.repository_inventory.inventory_id
    assert facts.repository_root == str(tmp_path)
    assert facts.truncated is False
    assert any(m.module_kind == "frappe_app" for m in facts.modules)
    assert any(c.component_kind == "doctype" for c in facts.components)
    assert any(a.name == "get_desktop_page_override" for a in facts.apis)
    assert any(s.declared_via == "scheduler_events" for s in facts.services)
    assert any(e.extension_kind == "override_whitelisted_method" for e in facts.extension_points)
    assert any(e.entry_kind == "frappe_app_entry" for e in facts.entry_points)
    assert facts.statistics.facts_extracted > 0
    assert facts.statistics.files_failed == 0
    assert facts.unresolved == ()


def test_synthesize_requirements_raises_for_a_stale_repository_root(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    request = _synthesis_request(tmp_path)
    import shutil

    shutil.rmtree(tmp_path)

    with pytest.raises(RepositoryInventoryStaleError):
        synthesize_requirements(request)


# -- §5 Determinism -------------------------------------------------------------------------------


def test_synthesize_requirements_is_deterministic_across_repeated_runs(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    request = _synthesis_request(tmp_path)

    first = synthesize_requirements(request)
    second = synthesize_requirements(request)

    strip = {"facts_id": "x", "synthesized_at": "x"}
    assert first.model_copy(update=strip) == second.model_copy(update=strip)


# -- Budget / truncation --------------------------------------------------------------------------


def test_synthesize_requirements_truncates_at_max_files(tmp_path: Path) -> None:
    _build_test_app(tmp_path)
    request = _synthesis_request(tmp_path, max_files=1)

    facts = synthesize_requirements(request)

    assert facts.truncated is True
    assert facts.statistics.files_examined == 1


# -- Additional edge-case coverage -------------------------------------------------------------------


def test_split_pep508_name_returns_the_spec_unchanged_when_it_does_not_match() -> None:
    from synthesis.engine import _split_pep508_name

    assert _split_pep508_name("!!!not-a-valid-spec") == ("!!!not-a-valid-spec", "")


def test_identify_modules_ignores_an_init_py_directly_at_the_repository_root(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("")
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )

    modules = identify_modules(inventory)

    assert not any(m.relative_path in (".", "") for m in modules)


def test_extract_hooks_budget_exhaustion_stops_processing_remaining_hook_files(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "app_one").mkdir()
    (tmp_path / "app_one" / "hooks.py").write_text('app_name = "one"\n')
    (tmp_path / "app_two").mkdir()
    (tmp_path / "app_two" / "hooks.py").write_text('app_name = "two"\n')
    connector = resolve_connector(str(tmp_path))
    files = (
        DiscoveredFile(
            relative_path="app_one/hooks.py",
            file_type=RepositoryFileType.HOOK,
            size_bytes=10,
            is_binary=False,
        ),
        DiscoveredFile(
            relative_path="app_two/hooks.py",
            file_type=RepositoryFileType.HOOK,
            size_bytes=10,
            is_binary=False,
        ),
    )
    budget = Budget(remaining_files=1, deadline=time.monotonic() + 30.0)

    configuration, *_ = extract_hooks(files, connector, budget)

    assert budget.truncated is True
    assert len(configuration) == 1


def test_extract_hooks_skips_non_assign_top_level_statements(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "hooks.py").write_text('import os\napp_name = "test_app"\n')
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="hooks.py", file_type=RepositoryFileType.HOOK, size_bytes=10, is_binary=False
    )

    configuration, *_ = extract_hooks((file,), connector)

    assert any(f.key == "app_name" for f in configuration)


def test_extract_hooks_treats_a_non_literal_assignment_value_as_none(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "hooks.py").write_text("app_include_js = compute_js_files()\n")
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="hooks.py", file_type=RepositoryFileType.HOOK, size_bytes=10, is_binary=False
    )

    configuration, *_ = extract_hooks((file,), connector)

    assert any(f.key == "app_include_js" and f.value == "" for f in configuration)


def test_extract_hooks_skips_tuple_unpacking_assignment_targets(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "hooks.py").write_text('a, b = "x", "y"\napp_name = "test_app"\n')
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="hooks.py", file_type=RepositoryFileType.HOOK, size_bytes=10, is_binary=False
    )

    configuration, *_ = extract_hooks((file,), connector)

    assert {f.key for f in configuration} == {"app_name"}


def test_extract_components_falls_back_to_filename_stem_when_name_is_absent(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    doctype_dir = tmp_path / "doctype" / "nameless_doctype"
    doctype_dir.mkdir(parents=True)
    (doctype_dir / "nameless_doctype.json").write_text('{"module": "Test"}')
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="doctype/nameless_doctype/nameless_doctype.json",
        file_type=RepositoryFileType.DOCTYPE,
        size_bytes=10,
        is_binary=False,
    )

    components, unresolved = extract_components((file,), connector)

    assert unresolved == ()
    assert components[0].name == "nameless_doctype"


def test_is_whitelist_decorator_recognizes_a_bare_imported_whitelist_name(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "api.py").write_text("from frappe import whitelist\n\n\n@whitelist\ndef bare(): pass\n")
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="api.py", file_type=RepositoryFileType.PYTHON_SOURCE, size_bytes=10, is_binary=False
    )

    apis, unresolved = extract_apis((file,), connector)

    assert unresolved == ()
    assert any(a.name == "bare" for a in apis)


def test_is_whitelist_decorator_rejects_an_unrelated_decorator(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "api.py").write_text("@property\ndef not_an_api(self): pass\n")
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="api.py", file_type=RepositoryFileType.PYTHON_SOURCE, size_bytes=10, is_binary=False
    )

    apis, _ = extract_apis((file,), connector)

    assert apis == ()


def test_is_whitelist_decorator_rejects_a_subscript_shaped_decorator(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "api.py").write_text("@some_registry['key']\ndef odd(): pass\n")
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="api.py", file_type=RepositoryFileType.PYTHON_SOURCE, size_bytes=10, is_binary=False
    )

    apis, unresolved = extract_apis((file,), connector)

    assert unresolved == ()
    assert apis == ()


def test_extract_apis_records_a_syntax_error_as_unresolved(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "broken.py").write_text("def broken( : pass")
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="broken.py", file_type=RepositoryFileType.PYTHON_SOURCE, size_bytes=10, is_binary=False
    )

    apis, unresolved = extract_apis((file,), connector)

    assert apis == ()
    assert len(unresolved) == 1


def test_extract_dependencies_records_an_unreadable_file_as_unresolved(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "pyproject.toml").write_text("[project]\n")
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="pyproject.toml", file_type=RepositoryFileType.CONFIG, size_bytes=10, is_binary=False
    )
    (tmp_path / "pyproject.toml").unlink()

    dependencies, unresolved = extract_dependencies((file,), connector)

    assert dependencies == ()
    assert len(unresolved) == 1


def test_extract_dependencies_records_malformed_package_json_as_unresolved(tmp_path: Path) -> None:
    from discovery.contract import DiscoveredFile, RepositoryFileType

    (tmp_path / "package.json").write_text("{not valid json")
    connector = resolve_connector(str(tmp_path))
    file = DiscoveredFile(
        relative_path="package.json", file_type=RepositoryFileType.CONFIG, size_bytes=10, is_binary=False
    )

    dependencies, unresolved = extract_dependencies((file,), connector)

    assert dependencies == ()
    assert len(unresolved) == 1
