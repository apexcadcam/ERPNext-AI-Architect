"""Tests for `discovery.errors` (Repository Discovery Engine Specification v1.1 §2)."""

from __future__ import annotations

import pytest

from discovery.errors import DiscoveryError_, RepositoryAccessError, RepositoryNotFoundError


def test_repository_not_found_error_is_a_discovery_error() -> None:
    assert issubclass(RepositoryNotFoundError, DiscoveryError_)


def test_repository_access_error_is_a_discovery_error() -> None:
    assert issubclass(RepositoryAccessError, DiscoveryError_)


def test_discovery_error_is_an_exception() -> None:
    assert issubclass(DiscoveryError_, Exception)


def test_repository_not_found_error_carries_its_message() -> None:
    with pytest.raises(RepositoryNotFoundError, match="no such directory"):
        raise RepositoryNotFoundError("no such directory: /nope")


def test_repository_access_error_carries_its_message() -> None:
    with pytest.raises(RepositoryAccessError, match="permission denied"):
        raise RepositoryAccessError("permission denied: /root-only")


def test_the_two_error_types_are_distinct() -> None:
    assert not issubclass(RepositoryNotFoundError, RepositoryAccessError)
    assert not issubclass(RepositoryAccessError, RepositoryNotFoundError)
