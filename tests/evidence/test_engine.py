"""Tests for `evidence.engine` (Evidence Extraction Engine Architecture Specification v1.1 §8, §9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evidence.collectors import _FileContext
from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceExtractionRequest,
    EvidenceKind,
    Source,
)
from evidence.engine import (
    _collect_from_file,
    _sort_key,
    _walk_all_files,
    extract_evidence,
    resolve_connector,
)
from evidence.errors import EvidenceError_

# -- Fixture -- a small, real, self-authored Frappe-shaped tree ---------------------------------------

_CUSTOMER_PY = """
class Customer:
    def validate(self):
        pass

    def on_submit(self):
        pass
"""

_API_PY = """
import frappe


@frappe.whitelist()
@frappe.only_for('System Manager')
def get_data():
    return {}
"""

_BROKEN_PY = "def broken(:\n    pass\n"


def _build_tree(root: Path) -> None:
    (root / "erpnext" / "accounts" / "doctype" / "customer").mkdir(parents=True)
    (root / "erpnext" / "accounts" / "doctype" / "customer" / "customer.py").write_text(_CUSTOMER_PY)
    (root / "apex_dashboard").mkdir()
    (root / "apex_dashboard" / "api.py").write_text(_API_PY)
    (root / "apex_dashboard" / "broken.py").write_text(_BROKEN_PY)
    (root / "README.md").write_text("# not python\n")


def _request(root: Path, **overrides: object) -> EvidenceExtractionRequest:
    defaults: dict[str, object] = {
        "repository": CanonicalRepository.FRAPPE,
        "source_root": str(root),
        "version": "v15.103.1",
        "commit": "61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        "correlation_id": "corr-1",
        "requested_by": "test-suite",
        "max_files": 1_000,
        "timeout_seconds": 30.0,
    }
    defaults.update(overrides)
    return EvidenceExtractionRequest(**defaults)  # type: ignore[arg-type]


# -- resolve_connector ----------------------------------------------------------------------------


def test_resolve_connector_connects_to_a_real_directory(tmp_path: Path) -> None:
    connector = resolve_connector(str(tmp_path))
    assert connector.list_directory(".") == ()


def test_resolve_connector_raises_evidence_error_for_a_nonexistent_root(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(EvidenceError_):
        resolve_connector(str(missing))


# -- _walk_all_files --------------------------------------------------------------------------------


def test_walk_all_files_finds_every_file_regardless_of_extension(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    result = _walk_all_files(connector, max_files=1_000, timeout_seconds=30.0)

    assert set(result.relative_paths) == {
        "erpnext/accounts/doctype/customer/customer.py",
        "apex_dashboard/api.py",
        "apex_dashboard/broken.py",
        "README.md",
    }
    assert result.truncated is False


def test_walk_all_files_truncates_at_max_files(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    result = _walk_all_files(connector, max_files=1, timeout_seconds=30.0)

    assert result.truncated is True
    assert len(result.relative_paths) == 1


def test_walk_all_files_skips_a_directory_that_becomes_unlistable_when_visited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))
    original_list_directory = connector.list_directory
    calls: dict[str, int] = {}

    def _flaky_list_directory(path: str = ".") -> tuple[str, ...]:
        calls[path] = calls.get(path, 0) + 1
        if path == "apex_dashboard" and calls[path] == 2:
            raise OSError("deliberately broken for this test")
        return original_list_directory(path)

    monkeypatch.setattr(connector, "list_directory", _flaky_list_directory)

    result = _walk_all_files(connector, max_files=1_000, timeout_seconds=30.0)

    assert "apex_dashboard/api.py" not in result.relative_paths
    assert "erpnext/accounts/doctype/customer/customer.py" in result.relative_paths


def test_walk_all_files_skips_a_child_whose_file_or_directory_check_raises_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))
    original_list_directory = connector.list_directory

    def _flaky_list_directory(path: str = ".") -> tuple[str, ...]:
        if path == "apex_dashboard/api.py":
            raise OSError("deliberately broken for this test")
        return original_list_directory(path)

    monkeypatch.setattr(connector, "list_directory", _flaky_list_directory)

    result = _walk_all_files(connector, max_files=1_000, timeout_seconds=30.0)

    assert "apex_dashboard/api.py" not in result.relative_paths
    assert "apex_dashboard/broken.py" in result.relative_paths


def test_walk_all_files_truncates_when_the_deadline_has_already_passed(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    result = _walk_all_files(connector, max_files=1_000, timeout_seconds=0.0)

    assert result.truncated is True
    assert result.relative_paths == ()


# -- _collect_from_file -------------------------------------------------------------------------------


def _context(relative_path: str) -> _FileContext:
    return _FileContext(
        repository=CanonicalRepository.FRAPPE,
        version="v15.103.1",
        commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        relative_path=relative_path,
        collected_at="2026-07-27T12:00:00+00:00",
    )


def test_collect_from_file_returns_evidence_from_both_collectors(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    evidence, error = _collect_from_file(
        connector, "apex_dashboard/api.py", _context("apex_dashboard/api.py")
    )

    assert error is None
    subjects = {record.subject for record in evidence}
    assert subjects == {"frappe.whitelist", "frappe.only_for"}


def test_collect_from_file_records_a_syntax_error_without_raising(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    evidence, error = _collect_from_file(
        connector, "apex_dashboard/broken.py", _context("apex_dashboard/broken.py")
    )

    assert evidence == ()
    assert error is not None
    assert error.relative_path == "apex_dashboard/broken.py"


def test_collect_from_file_records_an_os_error_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_tree(tmp_path)
    connector = resolve_connector(str(tmp_path))

    def _broken_read_text(path: str) -> str:
        raise OSError("deliberately broken for this test")

    monkeypatch.setattr(connector, "read_text", _broken_read_text)

    evidence, error = _collect_from_file(
        connector, "apex_dashboard/api.py", _context("apex_dashboard/api.py")
    )

    assert evidence == ()
    assert error is not None
    assert "deliberately broken" in error.reason


# -- _sort_key -----------------------------------------------------------------------------------------


def test_sort_key_orders_by_repository_path_line_category_symbol() -> None:
    evidence = Evidence(
        evidence_id="a" * 64,
        kind=EvidenceKind.IMPLEMENTATION,
        category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        symbol="frappe.model.document.Document.validate",
        subject="validate",
        source=Source(
            repository=CanonicalRepository.FRAPPE,
            version="v15.103.1",
            commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
            relative_path="frappe/model/document.py",
            line=421,
        ),
        collector=CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR,
        collected_at="2026-07-27T12:00:00+00:00",
    )
    assert _sort_key(evidence) == (
        "frappe",
        "frappe/model/document.py",
        421,
        "controller_lifecycle_hook",
        "frappe.model.document.Document.validate",
    )


# -- extract_evidence (end to end) --------------------------------------------------------------------


def test_extract_evidence_end_to_end_against_a_real_tree(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    request = _request(tmp_path)

    evidence_set = extract_evidence(request)

    assert evidence_set.schema_version == "1.0"
    assert evidence_set.repository == CanonicalRepository.FRAPPE
    assert evidence_set.truncated is False
    assert evidence_set.statistics.files_examined == 4
    assert evidence_set.statistics.files_skipped == 1  # README.md
    assert evidence_set.statistics.files_failed == 1  # broken.py
    assert len(evidence_set.errors) == 1
    assert evidence_set.errors[0].relative_path == "apex_dashboard/broken.py"

    categories = {record.category for record in evidence_set.evidence}
    assert categories == {
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        EvidenceCategory.WHITELISTED_API_DECORATION,
    }
    assert evidence_set.statistics.evidence_extracted == len(evidence_set.evidence)


def test_extract_evidence_output_is_stably_sorted(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    request = _request(tmp_path)

    evidence_set = extract_evidence(request)

    keys = [_sort_key(record) for record in evidence_set.evidence]
    assert keys == sorted(keys)


def test_extract_evidence_is_deterministic_including_evidence_ids(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    request = _request(tmp_path)

    first = extract_evidence(request)
    second = extract_evidence(request)

    strip = {"evidence_set_id": "x", "extracted_at": "x"}
    first_normalized = first.model_copy(
        update={
            **strip,
            "evidence": tuple(e.model_copy(update={"collected_at": "x"}) for e in first.evidence),
        }
    )
    second_normalized = second.model_copy(
        update={
            **strip,
            "evidence": tuple(e.model_copy(update={"collected_at": "x"}) for e in second.evidence),
        }
    )
    assert first_normalized == second_normalized
    # Content-addressed evidence_ids must match exactly, in the same order.
    assert [e.evidence_id for e in first.evidence] == [e.evidence_id for e in second.evidence]


def test_extract_evidence_respects_max_files_and_reports_truncation(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    request = _request(tmp_path, max_files=1)

    evidence_set = extract_evidence(request)

    assert evidence_set.truncated is True
    assert evidence_set.statistics.files_examined == 1


def test_extract_evidence_on_an_empty_repository_produces_a_valid_empty_evidence_set(tmp_path: Path) -> None:
    request = _request(tmp_path)

    evidence_set = extract_evidence(request)

    assert evidence_set.evidence == ()
    assert evidence_set.errors == ()
    assert evidence_set.statistics.files_examined == 0
