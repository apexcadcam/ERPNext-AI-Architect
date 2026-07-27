"""Tests for `recommendation.errors` (Recommendation Engine Architecture Specification v1.0 §3)."""

from __future__ import annotations

from recommendation.errors import RecommendationError_


def test_recommendation_error_is_an_exception() -> None:
    assert issubclass(RecommendationError_, Exception)


def test_recommendation_error_carries_its_message() -> None:
    try:
        raise RecommendationError_("something went wrong")
    except RecommendationError_ as exc:
        assert str(exc) == "something went wrong"
