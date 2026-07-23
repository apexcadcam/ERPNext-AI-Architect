"""Tests for `SecretsResolver` (SPRINT3_ARCHITECTURE_PACKAGE.md §8.2, §8.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from secrets_management import (
    DotenvSecretsBackend,
    EnvSecretsBackend,
    InvalidCredentialReferenceError,
    SecretResolutionError,
    SecretsResolver,
)


def test_resolves_via_the_registered_backend_for_its_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "sentinel-value")
    resolver = SecretsResolver()
    resolver.register(EnvSecretsBackend())

    assert resolver.resolve("env://API_KEY") == "sentinel-value"


def test_dispatches_to_the_matching_scheme_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHARED_KEY", "from-env")
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("SHARED_KEY=from-dotenv\n")

    resolver = SecretsResolver()
    resolver.register(EnvSecretsBackend())
    resolver.register(DotenvSecretsBackend(dotenv_file))

    assert resolver.resolve("env://SHARED_KEY") == "from-env"
    assert resolver.resolve("dotenv://SHARED_KEY") == "from-dotenv"


def test_no_backend_registered_for_scheme_raises() -> None:
    resolver = SecretsResolver()

    with pytest.raises(SecretResolutionError, match="no backend registered"):
        resolver.resolve("vault://some/path")


def test_backend_registered_but_key_not_found_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_KEY", raising=False)
    resolver = SecretsResolver()
    resolver.register(EnvSecretsBackend())

    with pytest.raises(SecretResolutionError, match="could not be resolved"):
        resolver.resolve("env://MISSING_KEY")


def test_malformed_reference_raises_invalid_reference_not_resolution_error() -> None:
    resolver = SecretsResolver()
    resolver.register(EnvSecretsBackend())

    with pytest.raises(InvalidCredentialReferenceError):
        resolver.resolve("not-a-reference")


def test_registering_the_same_scheme_twice_without_override_raises() -> None:
    resolver = SecretsResolver()
    resolver.register(EnvSecretsBackend())

    with pytest.raises(ValueError, match="already registered"):
        resolver.register(EnvSecretsBackend())


def test_override_true_replaces_the_backend_for_test_doubles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "real-value")
    resolver = SecretsResolver()
    resolver.register(EnvSecretsBackend())
    resolver.resolve("env://API_KEY")  # sanity check the real backend works first

    class _FakeBackend:
        scheme = "env"

        def resolve(self, key: str) -> str | None:
            return "fake-value"

    resolver.register(_FakeBackend(), override=True)

    assert resolver.resolve("env://API_KEY") == "fake-value"


def test_an_empty_resolver_resolves_nothing_by_default() -> None:
    # No backend is registered automatically — a caller must explicitly
    # opt in to each scheme it wants resolvable.
    resolver = SecretsResolver()

    with pytest.raises(SecretResolutionError):
        resolver.resolve("env://ANYTHING")
