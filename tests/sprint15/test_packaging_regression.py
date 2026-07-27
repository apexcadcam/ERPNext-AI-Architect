"""Sprint 15 (Phase 3) — Packaging Regression Test.

Guards against the exact class of staleness Sprint 15 discovered and
fixed: `pyproject.toml`'s `[tool.hatch.build.targets.wheel]` `packages`
list silently falling behind the real set of top-level production
packages as new ones are added — exactly what happened between Sprint 4
(`planning`) and Sprint 13 (`composition_root`), discovered only when
Sprint 15 Phase 1 built a real wheel and watched `architect --help`
crash from a clean install.

Uses only the standard library (`tomllib`, built in since Python 3.11,
matching this project's own `requires-python = ">=3.11"`) — no external
tooling, no actual wheel build. A full build-and-install cycle is Sprint
15 Phase 1/2's own verification method, already proven manually; this
test is instead a fast, deterministic, always-run guard against this one
specific config drifting out of sync again — the two are complementary,
not the same technique repeated.

A directory is considered a real, production top-level package if it
directly contains an `__init__.py` file — the same criterion used
throughout Sprint 15's own investigation. `tests/` is the one, disclosed,
intentional exclusion (it has its own `__init__.py`, required for
pytest's own package-mode discovery, but must never ship in a production
wheel); every other such directory must appear in `pyproject.toml`'s own
wheel `packages` list.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"

#: The one, disclosed, intentional exclusion — `tests/` has its own
#: `__init__.py` but must never ship in a production wheel.
_INTENTIONALLY_EXCLUDED = {"tests"}


def _real_top_level_production_packages() -> set[str]:
    return {
        path.name
        for path in sorted(REPO_ROOT.iterdir())
        if path.is_dir() and (path / "__init__.py").is_file() and path.name not in _INTENTIONALLY_EXCLUDED
    }


def _configured_wheel_packages() -> set[str]:
    with PYPROJECT_FILE.open("rb") as handle:
        data = tomllib.load(handle)
    packages: list[str] = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    return set(packages)


def test_every_real_production_package_is_configured_for_the_wheel() -> None:
    real_packages = _real_top_level_production_packages()
    configured_packages = _configured_wheel_packages()
    missing = real_packages - configured_packages
    assert missing == set(), (
        f"the following top-level production package(s) exist but are not listed in "
        f"pyproject.toml's [tool.hatch.build.targets.wheel] packages -- they will "
        f"silently be excluded from a real wheel build (Sprint 15's own discovered "
        f"regression class): {sorted(missing)}"
    )


def test_no_intentionally_excluded_package_is_configured_for_the_wheel() -> None:
    # The reverse mistake -- e.g. tests/ accidentally added to the wheel.
    configured_packages = _configured_wheel_packages()
    accidentally_included = configured_packages & _INTENTIONALLY_EXCLUDED
    assert accidentally_included == set()


def test_every_configured_wheel_package_genuinely_exists() -> None:
    # The opposite staleness direction: a name lingering in the config
    # after its directory was removed or renamed.
    configured_packages = _configured_wheel_packages()
    missing_directories = {
        package_name
        for package_name in configured_packages
        if not (REPO_ROOT / package_name / "__init__.py").is_file()
    }
    assert missing_directories == set()


def test_real_production_packages_and_configured_packages_match_exactly() -> None:
    # The precise, combined claim both tests above check separately --
    # kept as its own test since a single, clear failure message here is
    # often the fastest signal to a developer that something drifted.
    assert _real_top_level_production_packages() == _configured_wheel_packages()
