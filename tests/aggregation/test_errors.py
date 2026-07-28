"""Tests for `aggregation.errors` (Pattern Aggregation Engine Architecture Specification v1.0)."""

from __future__ import annotations

from aggregation.errors import AggregationError_


def test_aggregation_error_is_an_exception() -> None:
    assert issubclass(AggregationError_, Exception)


def test_aggregation_error_carries_its_message() -> None:
    try:
        raise AggregationError_("something went wrong")
    except AggregationError_ as exc:
        assert str(exc) == "something went wrong"
