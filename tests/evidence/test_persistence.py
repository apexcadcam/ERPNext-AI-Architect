"""Tests for `evidence.persistence` (Evidence Extraction Engine Architecture Specification v1.1 §10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceExtractionError,
    EvidenceKind,
    EvidenceSet,
    EvidenceStatistics,
    Source,
)
from evidence.errors import EvidenceError_
from evidence.persistence import read_evidence_set, write_evidence_set

# -- Fixture builders --------------------------------------------------------------------------------


def _evidence(
    *,
    relative_path: str = "frappe/model/document.py",
    line: int = 421,
    symbol: str = "frappe.model.document.Document.validate",
    subject: str = "validate",
    evidence_id: str = "a" * 64,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind=EvidenceKind.IMPLEMENTATION,
        category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        symbol=symbol,
        subject=subject,
        source=Source(
            repository=CanonicalRepository.FRAPPE,
            version="v15.103.1",
            commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
            relative_path=relative_path,
            line=line,
        ),
        collector=CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR,
        collected_at="2026-07-27T12:00:00+00:00",
    )


def _evidence_set(**overrides: object) -> EvidenceSet:
    defaults: dict[str, object] = {
        "evidence_set_id": "set-1",
        "schema_version": "1.0",
        "repository": CanonicalRepository.FRAPPE,
        "version": "v15.103.1",
        "commit": "61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        "extracted_at": "2026-07-27T12:00:00+00:00",
        "correlation_id": "corr-1",
        "evidence": (_evidence(),),
        "errors": (),
        "truncated": False,
        "statistics": EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=1
        ),
    }
    defaults.update(overrides)
    return EvidenceSet(**defaults)  # type: ignore[arg-type]


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "frappe-v15.103.1.evidence.jsonl", tmp_path / "frappe-v15.103.1.meta.json"


# -- Round trip -------------------------------------------------------------------------------------


def test_round_trip_preserves_the_evidence_set_exactly(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    original = _evidence_set()

    write_evidence_set(original, evidence_path, meta_path)
    restored = read_evidence_set(evidence_path, meta_path)

    assert restored == original


def test_round_trip_preserves_every_metadata_field(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    original = _evidence_set(
        truncated=True,
        errors=(EvidenceExtractionError(relative_path="frappe/broken.py", reason="SyntaxError"),),
        statistics=EvidenceStatistics(
            files_examined=10, files_skipped=3, files_failed=1, evidence_extracted=1
        ),
    )

    write_evidence_set(original, evidence_path, meta_path)
    restored = read_evidence_set(evidence_path, meta_path)

    assert restored.truncated is True
    assert restored.errors == original.errors
    assert restored.statistics == original.statistics
    assert restored.schema_version == "1.0"
    assert restored.evidence_set_id == "set-1"
    assert restored.correlation_id == "corr-1"
    assert restored.extracted_at == original.extracted_at


def test_round_trip_preserves_evidence_order_exactly(tmp_path: Path) -> None:
    # Deliberately stored in an order that is NOT the engine's own sort
    # order -- persistence must replay exactly what it was given, never
    # re-derive or "helpfully" re-sort (spec SS10).
    evidence_path, meta_path = _paths(tmp_path)
    records = (
        _evidence(relative_path="z/last.py", line=1, evidence_id="c" * 64),
        _evidence(relative_path="a/first.py", line=9, evidence_id="b" * 64),
        _evidence(relative_path="m/middle.py", line=5, evidence_id="d" * 64),
    )
    original = _evidence_set(
        evidence=records,
        statistics=EvidenceStatistics(
            files_examined=3, files_skipped=0, files_failed=0, evidence_extracted=3
        ),
    )

    write_evidence_set(original, evidence_path, meta_path)
    restored = read_evidence_set(evidence_path, meta_path)

    assert [record.evidence_id for record in restored.evidence] == [record.evidence_id for record in records]


def test_round_trip_of_an_empty_evidence_set(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    original = _evidence_set(
        evidence=(),
        statistics=EvidenceStatistics(
            files_examined=0, files_skipped=0, files_failed=0, evidence_extracted=0
        ),
    )

    write_evidence_set(original, evidence_path, meta_path)
    restored = read_evidence_set(evidence_path, meta_path)

    assert restored == original
    assert restored.evidence == ()
    assert evidence_path.read_text(encoding="utf-8") == ""


# -- On-disk format ---------------------------------------------------------------------------------


def test_writes_one_json_object_per_line(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    original = _evidence_set(
        evidence=(
            _evidence(evidence_id="a" * 64),
            _evidence(evidence_id="b" * 64, line=99),
        ),
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=2
        ),
    )

    write_evidence_set(original, evidence_path, meta_path)

    lines = evidence_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        assert json.loads(line)["kind"] == "implementation"


def test_meta_file_excludes_the_evidence_tuple(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)

    write_evidence_set(_evidence_set(), evidence_path, meta_path)

    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "evidence" not in payload
    assert payload["schema_version"] == "1.0"
    assert payload["repository"] == "frappe"


def test_serialization_is_byte_identical_across_repeated_writes(tmp_path: Path) -> None:
    first_evidence, first_meta = tmp_path / "first.jsonl", tmp_path / "first.json"
    second_evidence, second_meta = tmp_path / "second.jsonl", tmp_path / "second.json"
    evidence_set = _evidence_set()

    write_evidence_set(evidence_set, first_evidence, first_meta)
    write_evidence_set(evidence_set, second_evidence, second_meta)

    assert first_evidence.read_bytes() == second_evidence.read_bytes()
    assert first_meta.read_bytes() == second_meta.read_bytes()


def test_write_creates_missing_parent_directories(tmp_path: Path) -> None:
    evidence_path = tmp_path / "nested" / "deeper" / "frappe.evidence.jsonl"
    meta_path = tmp_path / "nested" / "deeper" / "frappe.meta.json"

    write_evidence_set(_evidence_set(), evidence_path, meta_path)

    assert evidence_path.is_file()
    assert meta_path.is_file()


def test_read_skips_blank_lines(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    write_evidence_set(_evidence_set(), evidence_path, meta_path)
    evidence_path.write_text(evidence_path.read_text(encoding="utf-8") + "\n   \n", encoding="utf-8")

    restored = read_evidence_set(evidence_path, meta_path)

    assert len(restored.evidence) == 1


# -- Failure handling -------------------------------------------------------------------------------


def test_read_raises_evidence_error_for_a_missing_file(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)

    with pytest.raises(EvidenceError_):
        read_evidence_set(evidence_path, meta_path)


def test_read_raises_evidence_error_for_malformed_meta_json(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    write_evidence_set(_evidence_set(), evidence_path, meta_path)
    meta_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(EvidenceError_, match="malformed evidence metadata"):
        read_evidence_set(evidence_path, meta_path)


def test_read_raises_evidence_error_for_a_malformed_evidence_line(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    write_evidence_set(_evidence_set(), evidence_path, meta_path)
    evidence_path.write_text('{"evidence_id": "incomplete"}\n', encoding="utf-8")

    with pytest.raises(EvidenceError_, match="malformed evidence record"):
        read_evidence_set(evidence_path, meta_path)


def test_read_raises_evidence_error_when_meta_json_violates_the_contract(tmp_path: Path) -> None:
    evidence_path, meta_path = _paths(tmp_path)
    write_evidence_set(_evidence_set(), evidence_path, meta_path)
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    del payload["statistics"]
    meta_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvidenceError_, match="malformed evidence metadata"):
        read_evidence_set(evidence_path, meta_path)
