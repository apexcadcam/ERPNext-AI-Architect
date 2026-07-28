"""Tests for `evidence.errors` (Evidence Extraction Engine Architecture Specification v1.1)."""

from __future__ import annotations

from evidence.errors import EvidenceError_


def test_evidence_error_is_an_exception() -> None:
    assert issubclass(EvidenceError_, Exception)


def test_evidence_error_carries_its_message() -> None:
    try:
        raise EvidenceError_("something went wrong")
    except EvidenceError_ as exc:
        assert str(exc) == "something went wrong"
