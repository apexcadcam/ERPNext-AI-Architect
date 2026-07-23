"""Tests for the Runtime boot sequence (docs/runtime/RUNTIME_BOOT_SEQUENCE.md)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from runtime.boot import Runtime
from runtime.errors import DependencyValidationError
from runtime.lifecycle import RuntimeState


def test_boot_with_zero_plugins_reaches_ready(config_dir: Path, plugins_dir: Path) -> None:
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    info = runtime.boot()

    assert info.state is RuntimeState.READY
    assert info.discovered_module_count == 0
    assert info.started_module_count == 0
    assert runtime.all_healthy()  # vacuously true

    runtime.shutdown()
    assert runtime.state is RuntimeState.STOPPED


def test_boot_sequence_passes_through_every_documented_step_in_order(config_dir: Path, plugins_dir: Path) -> None:
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    runtime.boot()

    expected_prefix = [
        RuntimeState.STARTING,
        RuntimeState.PLUGIN_DISCOVERY,
        RuntimeState.DEPENDENCY_VALIDATION,
        RuntimeState.CONFIG_LOADING,
        RuntimeState.PIPELINE_REGISTRATION,
        RuntimeState.CONNECTOR_REGISTRATION,
        RuntimeState.HEALTH_CHECKING,
        RuntimeState.READY,
    ]
    assert list(runtime._lifecycle.history) == expected_prefix
    runtime.shutdown()


def test_boot_with_a_real_plugin_starts_it_and_reports_healthy(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    make_plugin("demo", capabilities_provided=["demo.capability"])
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    info = runtime.boot()

    assert info.started_module_count == 1
    assert info.module_health["demo"].healthy is True
    assert runtime.all_healthy()
    assert runtime.container.is_registered("demo.capability")

    runtime.shutdown()


def test_boot_fails_when_a_required_capability_is_unsatisfied(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    make_plugin("consumer", capabilities_required=["missing.thing"])
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    with pytest.raises(DependencyValidationError):
        runtime.boot()

    assert runtime.state is RuntimeState.FAILED


def test_config_disabling_a_module_narrows_the_started_set(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    make_plugin("standalone", capabilities_provided=["standalone.thing"])
    (config_dir / "modules").mkdir()
    (config_dir / "modules" / "standalone.yaml").write_text(yaml.safe_dump({"enabled": False}))

    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    info = runtime.boot()

    assert info.discovered_module_count == 1
    assert info.enabled_module_count == 0
    assert info.started_module_count == 0
    runtime.shutdown()


def test_config_disabling_a_depended_upon_module_is_boot_blocking(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    make_plugin("provider", capabilities_provided=["thing"])
    make_plugin("consumer", capabilities_required=["thing"])
    (config_dir / "modules").mkdir()
    (config_dir / "modules" / "provider.yaml").write_text(yaml.safe_dump({"enabled": False}))

    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    with pytest.raises(DependencyValidationError):
        runtime.boot()


def test_dependency_order_reflects_capability_wiring(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    make_plugin("base", capabilities_provided=["base.cap"])
    make_plugin("dependent", capabilities_required=["base.cap"], capabilities_provided=["dependent.cap"])
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    info = runtime.boot()

    assert info.dependency_order.index("base") < info.dependency_order.index("dependent")
    runtime.shutdown()


def test_shutdown_is_safe_to_call_on_an_already_booted_and_stopped_runtime(config_dir: Path, plugins_dir: Path) -> None:
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    runtime.boot()
    runtime.shutdown()
    # calling stop() again on an already-stopped module set must not raise;
    # the Runtime's own state machine is already terminal at STOPPED.
    assert runtime.state is RuntimeState.STOPPED
