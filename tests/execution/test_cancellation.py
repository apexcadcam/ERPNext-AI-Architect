"""Tests for `CancellationToken` (Sprint 5 Architecture Package §18)."""

from __future__ import annotations

from execution.cancellation import CancellationToken


def test_starts_not_cancelled() -> None:
    token = CancellationToken()
    assert token.is_cancellation_requested is False


def test_request_cancellation_sets_the_flag() -> None:
    token = CancellationToken()
    token.request_cancellation()
    assert token.is_cancellation_requested is True


def test_request_cancellation_is_idempotent() -> None:
    token = CancellationToken()
    token.request_cancellation()
    token.request_cancellation()
    assert token.is_cancellation_requested is True
