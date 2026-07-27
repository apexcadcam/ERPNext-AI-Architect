"""Tests for `synthesis.errors` (Requirement Synthesis Engine Specification v1.1 §2)."""

from __future__ import annotations

import pytest

from synthesis.errors import RepositoryInventoryStaleError, SynthesisError_


def test_repository_inventory_stale_error_is_a_synthesis_error() -> None:
    assert issubclass(RepositoryInventoryStaleError, SynthesisError_)


def test_synthesis_error_is_an_exception() -> None:
    assert issubclass(SynthesisError_, Exception)


def test_repository_inventory_stale_error_carries_its_message() -> None:
    with pytest.raises(RepositoryInventoryStaleError, match="no such directory"):
        raise RepositoryInventoryStaleError("no such directory: /nope")
