"""Shared fixtures for Sprint 3's final, cross-layer validation suite.

This directory intentionally does not import fixtures from
`tests/integration/conftest.py` or `tests/knowledge/conftest.py` — both are
siblings of this directory, not ancestors, so pytest would not cascade
their fixtures here automatically, and reaching across sideways would
create exactly the kind of cross-test-package coupling this Sprint's own
architecture discipline argues against between the packages under test.
Everything needed is rebuilt here, minimally.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from knowledge.artifacts import (
    ArtifactMetadata,
    ArtifactStatus,
    ArtifactVersionInfo,
    DependencyEdge,
    KnowledgeAPI,
    KnowledgeAPIContent,
    RelationshipEdge,
)

#: The real, repository directories — not a tmp_path fixture — because the
#: whole point of this suite's smoke/contract tests is proving the actual
#: shipped `plugins/` and `integration/connectors/` content works, mirroring
#: the `_PLUGINS_DIR` pattern already used by
#: tests/integration/test_module.py and tests/knowledge/conftest.py.
REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_DIR = REPO_ROOT / "plugins"
CONNECTORS_DIR = REPO_ROOT / "integration" / "connectors"


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "config"
    directory.mkdir()
    return directory


def disable_modules(config_dir: Path, *module_ids: str) -> None:
    """Disables `module_ids` via the Configuration System's own, already-
    proven `enabled: false` module override (`tests/test_boot.py`'s
    established pattern) — used by the smoke tests to boot the real
    `plugins/` directory while scoping to Integration only, without this
    Sprint 3 suite needing to know anything about Sprint 2's Extractor/
    Validator modules' own capability requirements.
    """

    modules_dir = config_dir / "modules"
    modules_dir.mkdir(exist_ok=True)
    for module_id in module_ids:
        (modules_dir / f"{module_id}.yaml").write_text(yaml.safe_dump({"enabled": False}), encoding="utf-8")


def make_validated_knowledge_api(
    api_id: str,
    *,
    relationships: tuple[RelationshipEdge, ...] = (),
    dependencies: tuple[DependencyEdge, ...] = (),
) -> KnowledgeAPI:
    """A minimal, `status=validated` `KnowledgeAPI` artifact — just enough
    of KNOWLEDGE_ARTIFACTS.md §1's envelope to be constructible, independent
    of tests/knowledge/conftest.py's own richer fixture.
    """

    return KnowledgeAPI(
        id=api_id,
        metadata=ArtifactMetadata(
            extracted_at="2026-01-01T00:00:00Z", extraction_method="fixture", extractor_version="0.1.0"
        ),
        version=ArtifactVersionInfo(applies_to="v15"),
        status=ArtifactStatus.VALIDATED,
        confidence=0.9,
        relationships=relationships,
        dependencies=dependencies,
        content=KnowledgeAPIContent(interface_kind="whitelisted-method", name=f"demo.{api_id.lower()}"),
    )


#: A second, independent `ConnectorLifecycle` implementation — deliberately
#: unrelated to the Filesystem Connector — used by the contract-stability
#: tests to prove `ConnectorRegistry` never assumes anything Filesystem-
#: specific.
ECHO_CONNECTOR_PY = textwrap.dedent(
    """
    from integration.lifecycle import ConnectorHealth, ConnectorLifecycle

    class EchoConnector(ConnectorLifecycle):
        def connect(self):
            self.connected = True

        def health_check(self):
            return ConnectorHealth(healthy=True, detail="echo connector alive")

        def echo(self, message: str) -> str:
            return message

    def create(manifest):
        return EchoConnector(manifest)
    """
)


@pytest.fixture
def make_echo_connector(tmp_path: Path) -> Callable[..., Path]:
    """Factory: writes a minimal, working, non-Filesystem connector
    (manifest + entry point) under a fresh tmp_path directory and returns
    the directory that contains it (suitable for `ConnectorRegistry.discover`).
    """

    def _make(connector_id: str = "echo") -> Path:
        connectors_dir = tmp_path / "connectors"
        connectors_dir.mkdir(exist_ok=True)
        connector_dir = connectors_dir / connector_id
        connector_dir.mkdir()

        manifest = {
            "connector_id": connector_id,
            "display_name": connector_id.title(),
            "maintained_by": "test-suite",
            "target_system_type": "custom",
            "version": "0.1.0",
            "endpoint_kind": "local_path",
            "endpoint_reference": ".",
            "operations": [{"name": "echo.say", "kind": "read", "idempotent": True}],
            "entry_point": "connector:create",
        }
        (connector_dir / "connector.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
        (connector_dir / "connector.py").write_text(ECHO_CONNECTOR_PY, encoding="utf-8")
        return connectors_dir

    return _make
