"""Shared pytest fixtures.

Every fixture here builds fully isolated, disposable fixtures under
pytest's own `tmp_path` — no test ever touches a real config directory or
plugin path, and no test depends on execution order or shared state.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

DEFAULT_MODULE_PY = textwrap.dedent(
    """
    from runtime.modules.base import Module, HealthCheckResult

    class _TestModule(Module):
        def init(self, container):
            self.container = container
            self.started = False

        def start(self):
            self.started = True

        def health_check(self):
            return HealthCheckResult(healthy=self.started, detail="test module alive")

    def create(manifest):
        return _TestModule(manifest)
    """
)


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "config"
    directory.mkdir()
    return directory


@pytest.fixture
def plugins_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "plugins"
    directory.mkdir()
    return directory


@pytest.fixture
def make_plugin(plugins_dir: Path) -> Callable[..., Path]:
    """Factory: writes a minimal, working plugin (manifest + entry point)
    under `plugins_dir` and returns its directory.
    """

    def _make(
        module_id: str,
        *,
        capabilities_provided: list[str] | None = None,
        capabilities_required: list[str] | None = None,
        enabled_by_default: bool = True,
        module_py: str = DEFAULT_MODULE_PY,
    ) -> Path:
        plugin_dir = plugins_dir / module_id
        plugin_dir.mkdir()

        manifest = {
            "module_id": module_id,
            "display_name": module_id.title(),
            "maintained_by": "test-suite",
            "version": "0.1.0",
            "capabilities_provided": capabilities_provided or [],
            "capabilities_required": capabilities_required or [],
            "enabled_by_default": enabled_by_default,
            "entry_point": "module:create",
        }
        (plugin_dir / "module.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
        (plugin_dir / "module.py").write_text(module_py, encoding="utf-8")
        return plugin_dir

    return _make
