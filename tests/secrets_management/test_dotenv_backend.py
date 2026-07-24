"""Tests for the `dotenv://` backend (SPRINT3_ARCHITECTURE_PACKAGE.md §8.2)."""

from __future__ import annotations

from pathlib import Path

from secrets_management import DotenvSecretsBackend


def test_resolves_a_simple_key_value_line(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("API_KEY=sentinel-value\n")
    backend = DotenvSecretsBackend(dotenv_file)

    assert backend.resolve("API_KEY") == "sentinel-value"


def test_returns_none_for_a_missing_key(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("OTHER_KEY=value\n")
    backend = DotenvSecretsBackend(dotenv_file)

    assert backend.resolve("API_KEY") is None


def test_returns_none_when_the_file_does_not_exist(tmp_path: Path) -> None:
    backend = DotenvSecretsBackend(tmp_path / "does-not-exist.env")

    assert backend.resolve("API_KEY") is None


def test_skips_blank_lines_and_comments(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("\n# a comment\n\nAPI_KEY=sentinel-value\n# API_KEY=wrong\n")
    backend = DotenvSecretsBackend(dotenv_file)

    assert backend.resolve("API_KEY") == "sentinel-value"


def test_strips_an_export_prefix(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("export API_KEY=sentinel-value\n")
    backend = DotenvSecretsBackend(dotenv_file)

    assert backend.resolve("API_KEY") == "sentinel-value"


def test_strips_matching_single_or_double_quotes(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("DOUBLE=\"quoted value\"\nSINGLE='quoted value'\n")
    backend = DotenvSecretsBackend(dotenv_file)

    assert backend.resolve("DOUBLE") == "quoted value"
    assert backend.resolve("SINGLE") == "quoted value"


def test_does_not_strip_mismatched_quotes(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("KEY=\"mismatched'\n")
    backend = DotenvSecretsBackend(dotenv_file)

    assert backend.resolve("KEY") == "\"mismatched'"


def test_reparses_on_every_call_not_cached(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("API_KEY=first\n")
    backend = DotenvSecretsBackend(dotenv_file)
    assert backend.resolve("API_KEY") == "first"

    dotenv_file.write_text("API_KEY=second\n")
    assert backend.resolve("API_KEY") == "second"


def test_scheme_is_dotenv() -> None:
    assert DotenvSecretsBackend.scheme == "dotenv"
