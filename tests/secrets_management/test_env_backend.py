"""Tests for the `env://` backend (SPRINT3_ARCHITECTURE_PACKAGE.md §8.2)."""

from __future__ import annotations

import pytest

from secrets_management import EnvSecretsBackend


def test_resolves_a_set_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETS_TEST_VAR", "sentinel-value")
    backend = EnvSecretsBackend()

    assert backend.resolve("SECRETS_TEST_VAR") == "sentinel-value"


def test_returns_none_for_an_unset_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRETS_TEST_VAR_UNSET", raising=False)
    backend = EnvSecretsBackend()

    assert backend.resolve("SECRETS_TEST_VAR_UNSET") is None


def test_reads_fresh_on_every_call_not_a_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = EnvSecretsBackend()
    monkeypatch.delenv("SECRETS_TEST_VAR_LATE", raising=False)
    assert backend.resolve("SECRETS_TEST_VAR_LATE") is None

    monkeypatch.setenv("SECRETS_TEST_VAR_LATE", "set-after-construction")
    assert backend.resolve("SECRETS_TEST_VAR_LATE") == "set-after-construction"


def test_scheme_is_env() -> None:
    assert EnvSecretsBackend.scheme == "env"
