"""Shared fixtures for Sprint 6's final validation suite.

Self-contained, mirroring `tests/sprint3/conftest.py`'s/`tests/sprint5/
conftest.py`'s own discipline: this directory does not import fixtures or
test doubles from `tests/execution/`, `tests/planning/`, or
`tests/integration/` (siblings, not ancestors, so pytest would not cascade
their fixtures here anyway) — everything needed is rebuilt here, minimally.
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
#: `tests/sprint3/conftest.py`/`tests/sprint5/conftest.py` already used.
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
    `tests/sprint3/conftest.py` established, reused here to scope a real
    boot of the real `plugins/` directory to Integration/Planning/
    Execution alone, without this suite needing to know anything about
    Sprint 2's Extractor/Validator modules' own capability requirements.
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
    with Integration/Planning/Execution enabled (Extractor/Validator
    disabled, orthogonal to what this Sprint validates) and real connector
    discovery configured.
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
    public API only (`get()`/`register()`/`.manifest.model_copy()`), no
    private internals touched, mirroring `tests/execution/
    test_connector_invoker.py`'s own established pattern. Needed because
    `booted_runtime` boots against the real, shipped
    `integration/connectors/filesystem/connector.yaml`, whose own
    `endpoint_reference` is the placeholder `"."`, per that manifest's own
    documented, deliberate "a real deployment sets it before registration"
    convention — a real boot proving Sprint 6's own wiring must not also
    read or write real repository files to do it.
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
