"""Tests for `Profile` (SPRINT3_ARCHITECTURE_PACKAGE.md §8.3, §9.1, ADR-0008)."""

from __future__ import annotations

import pytest

from secrets_management import InvalidProfileNameError, Profile


@pytest.mark.parametrize(
    "name",
    ["Development", "Production", "Customer A", "Customer B", "Local ERP", "Cloud ERP", "anything-goes-99"],
)
def test_arbitrary_profile_names_are_accepted_none_are_hardcoded(name: str) -> None:
    # No enum, no allow-list — every one of these is just a string this
    # project never special-cases, per §8.3's "arbitrary identifiers."
    profile = Profile(name=name)
    assert profile.name == name


def test_environment_value_is_an_identity_mapping() -> None:
    profile = Profile(name="Customer A")
    assert profile.environment_value == "Customer A"


def test_empty_name_raises() -> None:
    with pytest.raises(InvalidProfileNameError, match="empty"):
        Profile(name="")


def test_whitespace_only_name_raises() -> None:
    with pytest.raises(InvalidProfileNameError, match="empty"):
        Profile(name="   ")


def test_name_containing_slash_raises() -> None:
    with pytest.raises(InvalidProfileNameError, match="/"):
        Profile(name="Customer/A")


def test_profile_is_frozen() -> None:
    profile = Profile(name="Development")
    with pytest.raises(AttributeError):
        profile.name = "Production"  # type: ignore[misc]


def test_two_profiles_with_the_same_name_are_equal() -> None:
    assert Profile(name="Development") == Profile(name="Development")
    assert Profile(name="Development") != Profile(name="Production")
