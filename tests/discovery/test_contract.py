"""Tests for `discovery.contract` (Repository Discovery Engine Specification v1.1 §2, §4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from discovery.contract import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_MAX_FILES,
    DEFAULT_TIMEOUT_SECONDS,
    DiscoveredFile,
    DiscoveryFileError,
    DiscoveryRequest,
    RepositoryFileType,
    RepositoryInventory,
    RepositoryMetadata,
    RepositoryStatistics,
)

# -- DiscoveryRequest ----------------------------------------------------------------------------


def test_discovery_request_requires_repository_root_correlation_id_and_requested_by() -> None:
    request = DiscoveryRequest(repository_root="/repo", correlation_id="corr-1", requested_by="test-suite")
    assert request.repository_root == "/repo"
    assert request.correlation_id == "corr-1"
    assert request.requested_by == "test-suite"


def test_discovery_request_applies_documented_defaults() -> None:
    request = DiscoveryRequest(repository_root="/repo", correlation_id="corr-1", requested_by="test-suite")
    assert request.exclude_patterns == DEFAULT_EXCLUDE_PATTERNS
    assert request.max_files == DEFAULT_MAX_FILES
    assert request.timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_discovery_request_rejects_empty_repository_root() -> None:
    with pytest.raises(ValidationError):
        DiscoveryRequest(repository_root="", correlation_id="corr-1", requested_by="test-suite")


def test_discovery_request_rejects_non_positive_max_files() -> None:
    with pytest.raises(ValidationError):
        DiscoveryRequest(
            repository_root="/repo", correlation_id="corr-1", requested_by="test-suite", max_files=0
        )


def test_discovery_request_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValidationError):
        DiscoveryRequest(
            repository_root="/repo", correlation_id="corr-1", requested_by="test-suite", timeout_seconds=0
        )


def test_discovery_request_is_frozen() -> None:
    request = DiscoveryRequest(repository_root="/repo", correlation_id="corr-1", requested_by="test-suite")
    with pytest.raises(ValidationError):
        request.repository_root = "/other"


def test_discovery_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DiscoveryRequest(
            repository_root="/repo",
            correlation_id="corr-1",
            requested_by="test-suite",
            unknown_field=1,  # type: ignore[call-arg]
        )


# -- DiscoveryFileError ---------------------------------------------------------------------------


def test_discovery_file_error_requires_relative_path_and_reason() -> None:
    error = DiscoveryFileError(relative_path="secret/", reason="permission denied")
    assert error.relative_path == "secret/"
    assert error.reason == "permission denied"


def test_discovery_file_error_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        DiscoveryFileError(relative_path="secret/", reason="")


# -- RepositoryFileType ---------------------------------------------------------------------------


def test_repository_file_type_defines_every_specified_value() -> None:
    assert {member.value for member in RepositoryFileType} == {
        "hook",
        "test",
        "doctype",
        "config",
        "readme",
        "json",
        "python_source",
        "template",
        "static",
        "unknown",
    }


def test_repository_file_type_is_a_str_enum() -> None:
    assert RepositoryFileType.HOOK.value == "hook"
    assert isinstance(RepositoryFileType.HOOK, str)


# -- DiscoveredFile --------------------------------------------------------------------------------


def test_discovered_file_round_trips_through_json() -> None:
    file = DiscoveredFile(
        relative_path="apex_dashboard/hooks.py",
        file_type=RepositoryFileType.HOOK,
        size_bytes=3104,
        is_binary=False,
    )
    restored = DiscoveredFile.model_validate_json(file.model_dump_json())
    assert restored == file


def test_discovered_file_rejects_negative_size() -> None:
    with pytest.raises(ValidationError):
        DiscoveredFile(
            relative_path="a.py", file_type=RepositoryFileType.PYTHON_SOURCE, size_bytes=-1, is_binary=False
        )


# -- RepositoryStatistics --------------------------------------------------------------------------


def test_repository_statistics_allows_a_null_largest_file_path_for_an_empty_repository() -> None:
    statistics = RepositoryStatistics(
        total_files=0,
        total_directories=0,
        total_size_bytes=0,
        files_by_type={},
        largest_file_size=0,
        largest_file_path=None,
    )
    assert statistics.largest_file_path is None


def test_repository_statistics_files_by_type_is_keyed_by_the_enum() -> None:
    statistics = RepositoryStatistics(
        total_files=2,
        total_directories=1,
        total_size_bytes=100,
        files_by_type={RepositoryFileType.PYTHON_SOURCE: 2},
        largest_file_size=60,
        largest_file_path="a.py",
    )
    assert statistics.files_by_type[RepositoryFileType.PYTHON_SOURCE] == 2


# -- RepositoryMetadata ----------------------------------------------------------------------------


def test_repository_metadata_defaults_to_empty_tuples() -> None:
    metadata = RepositoryMetadata(repository_name="apex_dashboard")
    assert metadata.detected_languages == ()
    assert metadata.detected_frameworks == ()
    assert metadata.top_level_directories == ()
    assert metadata.entry_point_candidates == ()


# -- RepositoryInventory ---------------------------------------------------------------------------


def _inventory() -> RepositoryInventory:
    return RepositoryInventory(
        inventory_id="inv-1",
        repository_root="/repo",
        discovered_at="2026-07-27T10:00:00+00:00",
        correlation_id="corr-1",
        files=(
            DiscoveredFile(
                relative_path="hooks.py", file_type=RepositoryFileType.HOOK, size_bytes=10, is_binary=False
            ),
        ),
        truncated=False,
        excluded_paths=(".git",),
        errors=(),
        statistics=RepositoryStatistics(
            total_files=1,
            total_directories=0,
            total_size_bytes=10,
            files_by_type={RepositoryFileType.HOOK: 1},
            largest_file_size=10,
            largest_file_path="hooks.py",
        ),
        metadata=RepositoryMetadata(repository_name="repo"),
    )


def test_repository_inventory_round_trips_through_json() -> None:
    inventory = _inventory()
    restored = RepositoryInventory.model_validate_json(inventory.model_dump_json())
    assert restored == inventory


def test_repository_inventory_is_frozen() -> None:
    inventory = _inventory()
    with pytest.raises(ValidationError):
        inventory.truncated = True


def test_repository_inventory_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RepositoryInventory(  # type: ignore[call-arg]
            inventory_id="inv-1",
            repository_root="/repo",
            discovered_at="2026-07-27T10:00:00+00:00",
            correlation_id="corr-1",
            files=(),
            truncated=False,
            excluded_paths=(),
            errors=(),
            statistics=RepositoryStatistics(
                total_files=0,
                total_directories=0,
                total_size_bytes=0,
                files_by_type={},
                largest_file_size=0,
                largest_file_path=None,
            ),
            metadata=RepositoryMetadata(repository_name="repo"),
            unexpected="field",
        )
