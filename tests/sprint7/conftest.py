"""Shared fixtures for Sprint 7's final validation suite.

Self-contained, mirroring `tests/sprint6/conftest.py`'s own discipline
exactly: this directory does not import fixtures or test doubles from
`tests/orchestration/`, `tests/execution/`, `tests/planning/`, or
`tests/integration/` (siblings, not ancestors) — everything needed is
rebuilt here, minimally. `booted_runtime` needs no change from Sprint 6's
own version to also include Orchestration: `orchestration/`'s manifest is
`enabled_by_default: true`, like every other module, so disabling only
Extractor/Validator already leaves Integration, Planning, Execution, and
Orchestration all enabled.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from integration.registry import ConnectorRegistry, DiscoveredConnector
from runtime.boot import Runtime

#: The real, repository directories — not a tmp_path fixture — because the
#: whole point of this suite is proving the actual shipped `plugins/`
#: directory boots and wires together, mirroring the `PLUGINS_DIR` pattern
#: `tests/sprint3/conftest.py` through `tests/sprint6/conftest.py` already
#: used.
REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_DIR = REPO_ROOT / "plugins"
CONNECTORS_DIR = REPO_ROOT / "integration" / "connectors"


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "config"
    directory.mkdir()
    return directory


def disable_modules(config_dir: Path, *module_ids: str) -> None:
    """Disables `module_ids` via the Configuration System's own
    `enabled: false` module override — the same, already-proven pattern
    every prior Sprint's own conftest already established.
    """

    modules_dir = config_dir / "modules"
    modules_dir.mkdir(exist_ok=True)
    for module_id in module_ids:
        (modules_dir / f"{module_id}.yaml").write_text(yaml.safe_dump({"enabled": False}), encoding="utf-8")


def configure_connector_search_paths(config_dir: Path) -> None:
    """Points Integration's own config-driven `connector_search_paths`
    (Sprint 6 Phase 3) at the real `integration/connectors/` directory, so
    a real boot discovers the real Filesystem connector.
    """

    modules_dir = config_dir / "modules"
    modules_dir.mkdir(exist_ok=True)
    (modules_dir / "integration.yaml").write_text(
        yaml.safe_dump({"connector_search_paths": [str(CONNECTORS_DIR)]}), encoding="utf-8"
    )


@pytest.fixture
def booted_runtime(config_dir: Path) -> Iterator[Runtime]:
    """A real `Runtime`, booted against the real `plugins/` directory,
    with Integration/Planning/Execution/Orchestration enabled
    (Extractor/Validator disabled, orthogonal to what this Sprint
    validates) and real connector discovery configured.
    """

    disable_modules(config_dir, "extractor", "validator")
    configure_connector_search_paths(config_dir)
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[PLUGINS_DIR])
    runtime.boot()
    yield runtime
    runtime.shutdown()


def root_filesystem_connector_at(registry: ConnectorRegistry, root: Path) -> None:
    """Repoints the real, already-discovered Filesystem connector's own
    `endpoint_reference` at `root` — through `ConnectorRegistry`'s own
    public API only, mirroring `tests/sprint6/conftest.py`'s own identical
    helper (itself mirroring `tests/execution/test_connector_invoker.py`'s
    established pattern).
    """

    discovered = registry.get("filesystem")
    assert discovered is not None
    registry.register(
        DiscoveredConnector(
            manifest=discovered.manifest.model_copy(update={"endpoint_reference": str(root)}),
            connector_dir=discovered.connector_dir,
        )
    )
    registry.validate()
