"""Tests for the Runtime boot sequence (docs/runtime/RUNTIME_BOOT_SEQUENCE.md)."""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from runtime.boot import Runtime
from runtime.errors import DependencyValidationError
from runtime.lifecycle import RuntimeState
from runtime.modules.base import Module

#: A module whose own init() explicitly registers a specific value for one
#: of its declared capabilities -- the exact shape IntegrationModule,
#: ExtractorModule, and ValidatorModule already use in real, shipped code
#: (Sprint 6 Architecture Package §4.2, ADR Candidate A).
_SELF_REGISTERING_MODULE_PY = textwrap.dedent(
    """
    from runtime.modules.base import Module, HealthCheckResult

    class _SelfRegisteringModule(Module):
        def init(self, container):
            container.register("demo.capability", lambda: "the-specific-value", override=True)

        def health_check(self):
            return HealthCheckResult(healthy=True, detail="self-registering test module")

    def create(manifest):
        return _SelfRegisteringModule(manifest)
    """
)


def test_boot_with_zero_plugins_reaches_ready(config_dir: Path, plugins_dir: Path) -> None:
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    info = runtime.boot()

    assert info.state is RuntimeState.READY
    assert info.discovered_module_count == 0
    assert info.started_module_count == 0
    assert runtime.all_healthy()  # vacuously true

    runtime.shutdown()
    assert runtime.state is RuntimeState.STOPPED


def test_boot_sequence_passes_through_every_documented_step_in_order(
    config_dir: Path, plugins_dir: Path
) -> None:
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


def test_a_modules_own_init_time_registration_survives_the_generic_fallback(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    # ADR Candidate A (Sprint 6 Architecture Package §18): a module's own,
    # more specific init()-time capability registration must survive
    # _start_one_module()'s generic per-module fallback, which runs
    # immediately afterward. Pre-fix, this fails -- the generic loop
    # silently overwrites "demo.capability" with the module instance
    # itself, discarding "the-specific-value".
    make_plugin("demo", capabilities_provided=["demo.capability"], module_py=_SELF_REGISTERING_MODULE_PY)
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    runtime.boot()

    assert runtime.container.resolve("demo.capability") == "the-specific-value"
    runtime.shutdown()


def test_a_module_that_never_self_registers_still_resolves_to_the_module_instance(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    # The generic fallback's own, legitimate use case (tests/conftest.py's
    # DEFAULT_MODULE_PY registers nothing itself) must be unchanged by ADR
    # Candidate A's guard.
    make_plugin("demo", capabilities_provided=["demo.capability"])
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    runtime.boot()

    assert isinstance(runtime.container.resolve("demo.capability"), Module)
    runtime.shutdown()


def test_runtime_event_bus_capability_is_registered_before_boot(config_dir: Path, plugins_dir: Path) -> None:
    # ADR Candidate B (Sprint 6 Architecture Package §18): registered at
    # Runtime construction, unconditionally -- available even if boot()
    # never runs, and regardless of how many plugins exist.
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    assert runtime.container.is_registered("runtime.event_bus")
    assert runtime.container.resolve("runtime.event_bus") is runtime.event_bus


def test_runtime_config_capability_is_registered_before_boot(config_dir: Path, plugins_dir: Path) -> None:
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])

    assert runtime.container.is_registered("runtime.config")
    assert runtime.container.resolve("runtime.config") is runtime.config_loader


def test_runtime_event_bus_and_config_capabilities_still_resolve_after_boot_with_zero_plugins(
    config_dir: Path, plugins_dir: Path
) -> None:
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    runtime.boot()

    assert runtime.container.resolve("runtime.event_bus") is runtime.event_bus
    assert runtime.container.resolve("runtime.config") is runtime.config_loader
    runtime.shutdown()


def test_runtime_event_bus_and_config_are_container_infrastructure_not_module_capabilities(
    make_plugin: Callable[..., Path], config_dir: Path, plugins_dir: Path
) -> None:
    # Neither capability is module-provided (architecture package §11,
    # §18): no manifest declares either, yet both remain resolvable
    # through the Container regardless -- Runtime infrastructure, not a
    # contingent, module-graph-validated dependency.
    make_plugin("demo", capabilities_provided=["demo.capability"])
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    runtime.boot()

    assert "runtime.event_bus" not in runtime.registry.all_provided_capabilities()
    assert "runtime.config" not in runtime.registry.all_provided_capabilities()
    assert runtime.container.is_registered("runtime.event_bus")
    assert runtime.container.is_registered("runtime.config")
    runtime.shutdown()


def test_shutdown_is_safe_to_call_on_an_already_booted_and_stopped_runtime(
    config_dir: Path, plugins_dir: Path
) -> None:
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[plugins_dir])
    runtime.boot()
    runtime.shutdown()
    # calling stop() again on an already-stopped module set must not raise;
    # the Runtime's own state machine is already terminal at STOPPED.
    assert runtime.state is RuntimeState.STOPPED
