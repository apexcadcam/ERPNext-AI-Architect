"""Tests for `evaluation.errors` (Architecture Evaluation Engine Specification v1.0 §2)."""

from __future__ import annotations

from evaluation.errors import EvaluationError_


def test_evaluation_error_is_an_exception() -> None:
    assert issubclass(EvaluationError_, Exception)


def test_evaluation_error_carries_its_message() -> None:
    try:
        raise EvaluationError_("something went wrong")
    except EvaluationError_ as exc:
        assert str(exc) == "something went wrong"
