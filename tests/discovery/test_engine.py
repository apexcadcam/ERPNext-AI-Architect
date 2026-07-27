"""Tests for `discovery.engine` (Repository Discovery Engine Specification v1.1 §3, §5, §6)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from discovery.contract import DiscoveryRequest, RepositoryFileType
from discovery.engine import (
    classify_entries,
    compute_metadata,
    compute_statistics,
    discover_repository,
    resolve_connector,
    walk_tree,
)
from discovery.errors import RepositoryAccessError, RepositoryNotFoundError

# -- Fixtures --------------------------------------------------------------------------------------


def _apex_dashboard_like_tree(root: Path) -> None:
    """Builds a small tree exercising every §3a classification rule,
    mirroring the real Apex Dashboard repository already reviewed this
    session — concrete, not a toy example.
    """

    app = root / "apex_dashboard"
    app.mkdir()
    (app / "hooks.py").write_text("# hook\n")  # HOOK (must win over PYTHON_SOURCE)
    (app / "overrides.py").write_text("# overrides\n" * 50)  # PYTHON_SOURCE
    (app / "cache_utils.py").write_text("# cache\n" * 10)  # PYTHON_SOURCE
    (app / "modules.txt").write_text("Apex Dashboard\n")  # UNKNOWN (framework marker only)
    (app / "README.md").write_text("# Apex Dashboard\n")  # README

    doctype_dir = app / "doctype" / "apex_dashboard_settings"
    doctype_dir.mkdir(parents=True)
    (doctype_dir / "apex_dashboard_settings.json").write_text("{}")  # DOCTYPE

    tests_dir = app / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_cache_utils.py").write_text("# test\n")  # TEST

    templates_dir = app / "templates" / "pages"
    templates_dir.mkdir(parents=True)
    (templates_dir / "template_dashboard_01.html").write_text("<div></div>")  # TEMPLATE

    static_dir = app / "public"
    static_dir.mkdir()
    (static_dir / "style.css").write_text("body {}")  # STATIC

    (root / "pyproject.toml").write_text("[project]\nname = 'apex_dashboard'\n")  # CONFIG
    (root / "package.json").write_text("{}")  # CONFIG (filename-listed, not generic JSON)
    (root / "data.json").write_text("{}")  # JSON (generic, not doctype/config)

    excluded = root / ".git"
    excluded.mkdir()
    (excluded / "HEAD").write_text("ref: refs/heads/master\n")


def _request(root: Path, **overrides: object) -> DiscoveryRequest:
    defaults: dict[str, object] = {
        "repository_root": str(root),
        "correlation_id": "corr-1",
        "requested_by": "test-suite",
    }
    defaults.update(overrides)
    return DiscoveryRequest(**defaults)  # type: ignore[arg-type]


# -- Stage 1: resolve_connector --------------------------------------------------------------------


def test_resolve_connector_raises_repository_not_found_for_a_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(RepositoryNotFoundError):
        resolve_connector(str(tmp_path / "does-not-exist"))


def test_resolve_connector_raises_repository_not_found_when_root_is_a_file(tmp_path: Path) -> None:
    a_file = tmp_path / "not-a-directory.txt"
    a_file.write_text("x")
    with pytest.raises(RepositoryNotFoundError):
        resolve_connector(str(a_file))


def test_resolve_connector_succeeds_for_a_real_directory(tmp_path: Path) -> None:
    connector = resolve_connector(str(tmp_path))
    assert connector.health_check().healthy is True


def test_resolve_connector_raises_repository_access_error_for_a_non_lifecycle_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FilesystemConnector.connect() only ever raises ConnectorLifecycleError
    # itself ("not a directory"); an OSError from a lower-level check (e.g.
    # a permission failure surfacing from Path.is_dir()) is a different,
    # narrower failure mode -- RepositoryAccessError, not
    # RepositoryNotFoundError.
    def _raise_permission_error(self: Path) -> bool:
        raise PermissionError("simulated permission failure")

    monkeypatch.setattr(Path, "is_dir", _raise_permission_error)

    with pytest.raises(RepositoryAccessError):
        resolve_connector(str(tmp_path))


# -- Stage 2: walk_tree ------------------------------------------------------------------------------


def test_walk_tree_finds_every_file_not_excluded(tmp_path: Path) -> None:
    _apex_dashboard_like_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    result = walk_tree(connector, exclude_patterns=(".git",), max_files=1000, timeout_seconds=30.0)

    assert "apex_dashboard/hooks.py" in result.relative_paths
    assert not any(p.startswith(".git") for p in result.relative_paths)
    assert result.truncated is False
    assert result.errors == ()


def test_walk_tree_excludes_configured_patterns_entirely(tmp_path: Path) -> None:
    _apex_dashboard_like_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    result = walk_tree(connector, exclude_patterns=(".git",), max_files=1000, timeout_seconds=30.0)

    assert all(".git" not in Path(p).parts for p in result.relative_paths)


def test_walk_tree_records_an_error_when_a_directory_becomes_unlistable_after_being_identified_as_one(
    tmp_path: Path,
) -> None:
    # A directory is identified as such by one successful list_directory()
    # call (the type-probe in the parent's loop); visit() then makes its
    # own, second call to actually list it. This simulates the narrow
    # TOCTOU window between those two calls (e.g. permissions revoked, or
    # the directory removed, in between) without relying on an actual race.
    (tmp_path / "flaky").mkdir()
    (tmp_path / "flaky" / "inner.txt").write_text("x")
    connector = resolve_connector(str(tmp_path))

    real_list_directory = connector.list_directory
    call_count = {"flaky": 0}

    def _flaky_list_directory(path: str = ".") -> tuple[str, ...]:
        if path == "flaky":
            call_count["flaky"] += 1
            if call_count["flaky"] == 2:
                raise PermissionError("simulated: became unreadable between calls")
        return real_list_directory(path)

    connector.list_directory = _flaky_list_directory  # type: ignore[method-assign]

    result = walk_tree(connector, exclude_patterns=(), max_files=1000, timeout_seconds=30.0)

    assert any(e.relative_path == "flaky" for e in result.errors)
    assert "flaky/inner.txt" not in result.relative_paths


def test_walk_tree_truncates_at_max_files(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"file_{i}.txt").write_text("x")
    connector = resolve_connector(str(tmp_path))

    result = walk_tree(connector, exclude_patterns=(), max_files=3, timeout_seconds=30.0)

    assert result.truncated is True
    assert len(result.relative_paths) <= 3


def test_walk_tree_truncates_on_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for i in range(5):
        (tmp_path / f"file_{i}.txt").write_text("x")
    connector = resolve_connector(str(tmp_path))

    # Deterministic fake clock: the deadline check trips on the second call.
    clock = iter([0.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))

    result = walk_tree(connector, exclude_patterns=(), max_files=1000, timeout_seconds=1.0)

    assert result.truncated is True


def test_walk_tree_records_a_permission_error_without_aborting_the_whole_run(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("permission checks are bypassed when running as root")

    (tmp_path / "readable.txt").write_text("x")
    locked_dir = tmp_path / "locked"
    locked_dir.mkdir()
    (locked_dir / "secret.txt").write_text("x")
    locked_dir.chmod(0o000)

    try:
        connector = resolve_connector(str(tmp_path))
        result = walk_tree(connector, exclude_patterns=(), max_files=1000, timeout_seconds=30.0)
    finally:
        locked_dir.chmod(0o755)

    assert "readable.txt" in result.relative_paths
    assert any(e.relative_path == "locked" for e in result.errors)


def test_walk_tree_visits_subdirectories_in_sorted_order(tmp_path: Path) -> None:
    for name in ("zeta", "alpha", "mu"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "file.txt").write_text("x")
    connector = resolve_connector(str(tmp_path))

    result = walk_tree(connector, exclude_patterns=(), max_files=1000, timeout_seconds=30.0)

    assert result.top_level_directories == ("alpha", "mu", "zeta")


# -- Stage 3: classify_entries — §3a Classification Priority --------------------------------------


def test_hooks_py_is_classified_as_hook_not_python_source(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text("# hook\n")

    files = classify_entries(str(tmp_path), ["hooks.py"])

    assert files[0].file_type is RepositoryFileType.HOOK


@pytest.mark.parametrize(
    ("relative_path", "expected_type"),
    [
        ("hooks.py", RepositoryFileType.HOOK),
        ("tests/test_thing.py", RepositoryFileType.TEST),
        ("thing_test.py", RepositoryFileType.TEST),
        ("app/doctype/thing/thing.json", RepositoryFileType.DOCTYPE),
        ("pyproject.toml", RepositoryFileType.CONFIG),
        ("package.json", RepositoryFileType.CONFIG),
        ("README.md", RepositoryFileType.README),
        ("readme", RepositoryFileType.README),
        ("data.json", RepositoryFileType.JSON),
        ("module.py", RepositoryFileType.PYTHON_SOURCE),
        ("templates/pages/page.html", RepositoryFileType.TEMPLATE),
        ("style.css", RepositoryFileType.STATIC),
        ("logo.png", RepositoryFileType.STATIC),
        ("unknown.xyz", RepositoryFileType.UNKNOWN),
    ],
)
def test_classification_precedence_table(
    tmp_path: Path, relative_path: str, expected_type: RepositoryFileType
) -> None:
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("content")

    files = classify_entries(str(tmp_path), [relative_path])

    assert files[0].file_type is expected_type


def test_classify_entries_reports_real_size_in_bytes(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x" * 42)

    files = classify_entries(str(tmp_path), ["a.py"])

    assert files[0].size_bytes == 42


def test_classify_entries_marks_known_binary_extensions(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")

    files = classify_entries(str(tmp_path), ["logo.png"])

    assert files[0].is_binary is True


def test_classify_entries_marks_python_source_as_not_binary(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x")

    files = classify_entries(str(tmp_path), ["a.py"])

    assert files[0].is_binary is False


def test_classify_entries_never_reads_file_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.py").write_text("x")

    def _forbidden_read(*args: object, **kwargs: object) -> str:
        raise AssertionError("classify_entries must never read file content")

    monkeypatch.setattr(Path, "read_text", _forbidden_read)

    classify_entries(str(tmp_path), ["a.py"])


# -- Stage 4: compute_statistics / compute_metadata -------------------------------------------------


def test_compute_statistics_aggregates_counts_and_sizes(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x" * 10)
    (tmp_path / "b.py").write_text("x" * 20)
    files = classify_entries(str(tmp_path), ["a.py", "b.py"])

    statistics = compute_statistics(files, directory_count=0)

    assert statistics.total_files == 2
    assert statistics.total_size_bytes == 30
    assert statistics.largest_file_size == 20
    assert statistics.largest_file_path == "b.py"
    assert statistics.files_by_type[RepositoryFileType.PYTHON_SOURCE] == 2


def test_compute_statistics_of_an_empty_repository_has_no_largest_file() -> None:
    statistics = compute_statistics((), directory_count=0)

    assert statistics.total_files == 0
    assert statistics.largest_file_size == 0
    assert statistics.largest_file_path is None


def test_compute_metadata_derives_repository_name_from_the_root_path(tmp_path: Path) -> None:
    metadata = compute_metadata(str(tmp_path), (), ())
    assert metadata.repository_name == tmp_path.name


def test_compute_metadata_detects_languages_from_extensions_present(tmp_path: Path) -> None:
    files = classify_entries(str(tmp_path / "does-not-need-to-exist-for-names"), [])
    (tmp_path / "a.py").write_text("x")
    files = classify_entries(str(tmp_path), ["a.py"])

    metadata = compute_metadata(str(tmp_path), (), files)

    assert metadata.detected_languages == ("python",)


def test_compute_metadata_detects_frappe_only_when_both_markers_present(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text("x")
    files_without_modules_txt = classify_entries(str(tmp_path), ["hooks.py"])
    assert "frappe" not in compute_metadata(str(tmp_path), (), files_without_modules_txt).detected_frameworks

    (tmp_path / "modules.txt").write_text("x")
    files_with_both = classify_entries(str(tmp_path), ["hooks.py", "modules.txt"])
    assert "frappe" in compute_metadata(str(tmp_path), (), files_with_both).detected_frameworks


def test_compute_metadata_entry_point_candidates_lists_only_present_names(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text("x")
    (tmp_path / "main.py").write_text("x")
    files = classify_entries(str(tmp_path), ["hooks.py", "main.py"])

    metadata = compute_metadata(str(tmp_path), (), files)

    assert metadata.entry_point_candidates == ("hooks.py", "main.py")


# -- discover_repository — end to end ---------------------------------------------------------------


def test_discover_repository_end_to_end_against_a_real_tree(tmp_path: Path) -> None:
    _apex_dashboard_like_tree(tmp_path)

    inventory = discover_repository(_request(tmp_path))

    relative_paths = {f.relative_path for f in inventory.files}
    assert "apex_dashboard/hooks.py" in relative_paths
    assert not any(p.startswith(".git") for p in relative_paths)
    assert inventory.truncated is False
    assert inventory.metadata.repository_name == tmp_path.name
    assert "frappe" in inventory.metadata.detected_frameworks
    assert inventory.statistics.total_files == len(inventory.files)


def test_discover_repository_files_are_sorted_by_relative_path(tmp_path: Path) -> None:
    (tmp_path / "zeta.py").write_text("x")
    (tmp_path / "alpha.py").write_text("x")

    inventory = discover_repository(_request(tmp_path))

    assert [f.relative_path for f in inventory.files] == ["alpha.py", "zeta.py"]


def test_discover_repository_raises_for_a_missing_root(tmp_path: Path) -> None:
    with pytest.raises(RepositoryNotFoundError):
        discover_repository(_request(tmp_path / "missing"))


# -- §5 Determinism -----------------------------------------------------------------------------------


def test_discover_repository_is_deterministic_across_repeated_runs(tmp_path: Path) -> None:
    _apex_dashboard_like_tree(tmp_path)
    request = _request(tmp_path)

    first = discover_repository(request)
    second = discover_repository(request)

    assert first.model_copy(update={"inventory_id": "x", "discovered_at": "x"}) == second.model_copy(
        update={"inventory_id": "x", "discovered_at": "x"}
    )


def test_discover_repository_inventory_id_and_discovered_at_are_excluded_from_the_determinism_guarantee(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("x")
    request = _request(tmp_path)

    first = discover_repository(request)
    second = discover_repository(request)

    assert first.inventory_id != second.inventory_id
