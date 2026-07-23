"""Tests for `ProfileSecretsBackend` (SPRINT3_ARCHITECTURE_PACKAGE.md §8.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from secrets_management import InvalidCredentialReferenceError, ProfileSecretsBackend


def _write_profile(profiles_dir: Path, name: str, contents: str) -> None:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{name}.secrets").write_text(contents)


def test_resolves_a_key_from_the_named_profiles_file(tmp_path: Path) -> None:
    _write_profile(tmp_path, "Development", "API_KEY=dev-value\n")
    backend = ProfileSecretsBackend(tmp_path)

    assert backend.resolve("Development/API_KEY") == "dev-value"


def test_profile_selection_two_different_profiles_resolve_independently(tmp_path: Path) -> None:
    _write_profile(tmp_path, "Customer A", "API_KEY=customer-a-value\n")
    _write_profile(tmp_path, "Customer B", "API_KEY=customer-b-value\n")
    backend = ProfileSecretsBackend(tmp_path)

    assert backend.resolve("Customer A/API_KEY") == "customer-a-value"
    assert backend.resolve("Customer B/API_KEY") == "customer-b-value"


def test_profile_switching_the_same_backend_serves_multiple_profiles_in_sequence(tmp_path: Path) -> None:
    _write_profile(tmp_path, "Local ERP", "SITE_URL=local-value\n")
    _write_profile(tmp_path, "Cloud ERP", "SITE_URL=cloud-value\n")
    backend = ProfileSecretsBackend(tmp_path)

    first = backend.resolve("Local ERP/SITE_URL")
    switched = backend.resolve("Cloud ERP/SITE_URL")
    switched_back = backend.resolve("Local ERP/SITE_URL")

    assert first == "local-value"
    assert switched == "cloud-value"
    assert switched_back == "local-value"


def test_a_profile_never_sees_another_profiles_key(tmp_path: Path) -> None:
    _write_profile(tmp_path, "Customer A", "SECRET_ONLY_IN_A=value-a\n")
    _write_profile(tmp_path, "Customer B", "OTHER_KEY=value-b\n")
    backend = ProfileSecretsBackend(tmp_path)

    assert backend.resolve("Customer B/SECRET_ONLY_IN_A") is None


def test_missing_profile_file_returns_none(tmp_path: Path) -> None:
    backend = ProfileSecretsBackend(tmp_path)

    assert backend.resolve("NoSuchProfile/API_KEY") is None


def test_missing_key_in_an_existing_profile_returns_none(tmp_path: Path) -> None:
    _write_profile(tmp_path, "Development", "OTHER_KEY=value\n")
    backend = ProfileSecretsBackend(tmp_path)

    assert backend.resolve("Development/API_KEY") is None


@pytest.mark.parametrize(
    "malformed_key",
    [
        "DevelopmentNoSlash",
        "/OnlyKeyNoProfile",
        "Development/",
        "",
    ],
)
def test_invalid_profile_reference_shapes_raise(tmp_path: Path, malformed_key: str) -> None:
    backend = ProfileSecretsBackend(tmp_path)

    with pytest.raises(InvalidCredentialReferenceError):
        backend.resolve(malformed_key)


def test_invalid_profile_name_in_reference_raises(tmp_path: Path) -> None:
    backend = ProfileSecretsBackend(tmp_path)

    # A profile name that is itself invalid (whitespace-only) is caught
    # even though the "<profile>/<key>" shape otherwise parses fine.
    with pytest.raises(InvalidCredentialReferenceError):
        backend.resolve("   /API_KEY")


def test_scheme_is_profile() -> None:
    assert ProfileSecretsBackend.scheme == "profile"


def test_reparses_on_every_call_not_cached(tmp_path: Path) -> None:
    _write_profile(tmp_path, "Development", "API_KEY=first\n")
    backend = ProfileSecretsBackend(tmp_path)
    assert backend.resolve("Development/API_KEY") == "first"

    _write_profile(tmp_path, "Development", "API_KEY=second\n")
    assert backend.resolve("Development/API_KEY") == "second"
