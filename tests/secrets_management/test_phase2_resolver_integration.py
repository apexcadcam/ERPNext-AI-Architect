"""End-to-end `SecretsResolver` tests for Phase 2: `profile://` registered
alongside the Phase 1 backends, proving no breaking change to `env://`/
`dotenv://` and correct profile selection/switching through the full
resolver (not just the backend directly — see test_profile_backend.py for
that). SPRINT3_ARCHITECTURE_PACKAGE.md §8, §9, §18 (Phase 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from secrets_management import (
    DotenvSecretsBackend,
    EnvSecretsBackend,
    Profile,
    ProfileSecretsBackend,
    SecretResolutionError,
    SecretsResolver,
)


def _write_profile(profiles_dir: Path, name: str, contents: str) -> None:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{name}.secrets").write_text(contents)


def _wired_resolver(tmp_path: Path) -> SecretsResolver:
    resolver = SecretsResolver()
    resolver.register(EnvSecretsBackend())
    resolver.register(DotenvSecretsBackend(tmp_path / ".env"))
    resolver.register(ProfileSecretsBackend(tmp_path / "profiles"))
    return resolver


def test_profile_scheme_resolves_through_the_resolver(tmp_path: Path) -> None:
    _write_profile(tmp_path / "profiles", "Development", "API_KEY=dev-value\n")
    resolver = _wired_resolver(tmp_path)

    assert resolver.resolve("profile://Development/API_KEY") == "dev-value"


def test_profile_selection_via_the_profile_value_object(tmp_path: Path) -> None:
    profile = Profile(name="Production")
    _write_profile(tmp_path / "profiles", profile.name, "API_KEY=prod-value\n")
    resolver = _wired_resolver(tmp_path)

    assert resolver.resolve(f"profile://{profile.name}/API_KEY") == "prod-value"


def test_profile_switching_through_the_resolver(tmp_path: Path) -> None:
    _write_profile(tmp_path / "profiles", "Customer A", "API_KEY=a-value\n")
    _write_profile(tmp_path / "profiles", "Customer B", "API_KEY=b-value\n")
    resolver = _wired_resolver(tmp_path)

    assert resolver.resolve("profile://Customer A/API_KEY") == "a-value"
    assert resolver.resolve("profile://Customer B/API_KEY") == "b-value"
    assert resolver.resolve("profile://Customer A/API_KEY") == "a-value"


def test_missing_profile_raises_via_the_resolver(tmp_path: Path) -> None:
    resolver = _wired_resolver(tmp_path)

    with pytest.raises(SecretResolutionError, match="could not be resolved"):
        resolver.resolve("profile://NoSuchProfile/API_KEY")


def test_missing_key_in_existing_profile_raises_via_the_resolver(tmp_path: Path) -> None:
    _write_profile(tmp_path / "profiles", "Development", "OTHER=value\n")
    resolver = _wired_resolver(tmp_path)

    with pytest.raises(SecretResolutionError, match="could not be resolved"):
        resolver.resolve("profile://Development/API_KEY")


# -- Backward compatibility: Phase 1 schemes are unaffected by Phase 2 ------


def test_env_scheme_still_works_unmodified_alongside_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PHASE1_API_KEY", "env-value")
    resolver = _wired_resolver(tmp_path)

    assert resolver.resolve("env://PHASE1_API_KEY") == "env-value"


def test_dotenv_scheme_still_works_unmodified_alongside_profile(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("PHASE1_API_KEY=dotenv-value\n")
    resolver = _wired_resolver(tmp_path)

    assert resolver.resolve("dotenv://PHASE1_API_KEY") == "dotenv-value"


def test_all_three_schemes_coexist_on_one_resolver_without_interference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SHARED_KEY", "from-env")
    (tmp_path / ".env").write_text("SHARED_KEY=from-dotenv\n")
    _write_profile(tmp_path / "profiles", "Development", "SHARED_KEY=from-profile\n")
    resolver = _wired_resolver(tmp_path)

    assert resolver.resolve("env://SHARED_KEY") == "from-env"
    assert resolver.resolve("dotenv://SHARED_KEY") == "from-dotenv"
    assert resolver.resolve("profile://Development/SHARED_KEY") == "from-profile"


def test_vault_scheme_is_still_unimplemented_in_phase_2(tmp_path: Path) -> None:
    resolver = _wired_resolver(tmp_path)

    with pytest.raises(SecretResolutionError, match="no backend registered"):
        resolver.resolve("vault://some/path")
