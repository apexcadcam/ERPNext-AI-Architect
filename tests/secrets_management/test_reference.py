"""Tests for `credential_reference` parsing (SPRINT3_ARCHITECTURE_PACKAGE.md §8.2)."""

from __future__ import annotations

import pytest

from secrets_management import (
    CredentialReference,
    InvalidCredentialReferenceError,
    parse_credential_reference,
)


def test_parses_scheme_and_key() -> None:
    reference = parse_credential_reference("env://API_KEY")
    assert reference == CredentialReference(scheme="env", key="API_KEY")


def test_parses_dotenv_scheme() -> None:
    reference = parse_credential_reference("dotenv://DB_PASSWORD")
    assert reference.scheme == "dotenv"
    assert reference.key == "DB_PASSWORD"


def test_key_may_itself_contain_a_scheme_like_separator() -> None:
    # partition() splits on the *first* "://" only, so a key containing
    # "://" (unusual, but not forbidden) is preserved whole.
    reference = parse_credential_reference("env://SOME_URL_VALUE://suffix")
    assert reference.scheme == "env"
    assert reference.key == "SOME_URL_VALUE://suffix"


def test_missing_separator_raises() -> None:
    with pytest.raises(InvalidCredentialReferenceError, match="://"):
        parse_credential_reference("env-API_KEY")


def test_empty_scheme_raises() -> None:
    with pytest.raises(InvalidCredentialReferenceError, match="empty scheme"):
        parse_credential_reference("://API_KEY")


def test_empty_key_raises() -> None:
    with pytest.raises(InvalidCredentialReferenceError, match="empty key"):
        parse_credential_reference("env://")


def test_reference_is_frozen() -> None:
    reference = parse_credential_reference("env://API_KEY")
    with pytest.raises(AttributeError):
        reference.key = "OTHER"  # type: ignore[misc]
