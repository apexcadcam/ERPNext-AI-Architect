"""Shared fixtures for Integration Layer tests.

Every fixture builds fully isolated, disposable fixtures under pytest's own
`tmp_path` — no test touches a real connectors directory — mirroring the
discipline `tests/conftest.py` already establishes for the Runtime's own
Module/Plugin tests (`make_plugin`), one level down for Connectors.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

DEFAULT_CONNECTOR_PY = textwrap.dedent(
    """
    from integration.lifecycle import ConnectorHealth, ConnectorLifecycle

    class _TestConnector(ConnectorLifecycle):
        def connect(self):
            self.connected = True

        def health_check(self):
            return ConnectorHealth(healthy=True, detail="test connector alive")

    def create(manifest):
        return _TestConnector(manifest)
    """
)

#: A connector.py whose factory returns something that is *not* a
#: ConnectorLifecycle — used to test instantiate()'s type-checking.
WRONG_RETURN_TYPE_CONNECTOR_PY = "def create(manifest):\n    return object()\n"

#: A connector.py whose module raises on import.
RAISES_ON_IMPORT_CONNECTOR_PY = "raise ValueError('boom')\n"


@pytest.fixture
def connectors_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "connectors"
    directory.mkdir()
    return directory


@pytest.fixture
def make_connector(connectors_dir: Path) -> Callable[..., Path]:
    """Factory: writes a minimal, working connector (manifest + entry
    point) under `connectors_dir` and returns its directory.
    """

    def _make(
        connector_id: str,
        *,
        operations: list[dict[str, object]] | None = None,
        auth_required: bool = False,
        auth_method: str = "none",
        credential_reference: str | None = None,
        target_system_type: str = "filesystem",
        connector_py: str = DEFAULT_CONNECTOR_PY,
    ) -> Path:
        connector_dir = connectors_dir / connector_id
        connector_dir.mkdir()

        manifest: dict[str, object] = {
            "connector_id": connector_id,
            "display_name": connector_id.title(),
            "maintained_by": "test-suite",
            "target_system_type": target_system_type,
            "version": "0.1.0",
            "auth_required": auth_required,
            "auth_method": auth_method,
            "endpoint_kind": "local_path",
            "endpoint_reference": "/tmp/example",
            "operations": operations or [],
            "entry_point": "connector:create",
        }
        if credential_reference is not None:
            manifest["credential_reference"] = credential_reference

        (connector_dir / "connector.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
        (connector_dir / "connector.py").write_text(connector_py, encoding="utf-8")
        return connector_dir

    return _make
