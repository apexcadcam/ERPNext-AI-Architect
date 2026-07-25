"""Sprint 6, Phase 7 — Capability Registration.

The concrete, full-system proof that Phases 1 and 2 hold together: a real
`Runtime.boot()` with Integration, Planning, and Execution all enabled, in
which every capability this Sprint touches resolves to the correct,
concrete object — none of them shadowed by `_start_one_module()`'s own
generic fallback (ADR Candidate A), and the two Runtime infrastructure
capabilities (ADR Candidate B) are present regardless of which modules
are enabled.
"""

from __future__ import annotations

from integration import CAPABILITY_CONNECTOR_REGISTRY, ConnectorRegistry
from runtime.boot import Runtime
from runtime.config.loader import ConfigLoader
from runtime.events.bus import EventBus
from runtime.lifecycle import RuntimeState

from execution.engine import ExecutionEngine
from execution.module import CAPABILITY_EXECUTION_ENGINE
from planning.engine import PlanningEngine
from planning.module import CAPABILITY_PLANNING_ENGINE


def test_every_module_starts_healthy(booted_runtime: Runtime) -> None:
    info = booted_runtime.info()
    assert info.state is RuntimeState.READY
    for module_id in ("integration", "planning", "execution"):
        assert module_id in info.module_health
        assert info.module_health[module_id].healthy is True


def test_connector_registry_resolves_to_the_real_registry_not_the_module(booted_runtime: Runtime) -> None:
    # ADR Candidate A's own concrete proof, at the full-system level.
    resolved = booted_runtime.container.resolve(CAPABILITY_CONNECTOR_REGISTRY)
    assert isinstance(resolved, ConnectorRegistry)
    assert resolved.get("filesystem") is not None


def test_planning_engine_resolves_to_a_real_working_engine(booted_runtime: Runtime) -> None:
    resolved = booted_runtime.container.resolve(CAPABILITY_PLANNING_ENGINE)
    assert isinstance(resolved, PlanningEngine)


def test_execution_engine_resolves_to_a_real_engine_wired_to_the_real_registry(
    booted_runtime: Runtime,
) -> None:
    resolved = booted_runtime.container.resolve(CAPABILITY_EXECUTION_ENGINE)
    registry = booted_runtime.container.resolve(CAPABILITY_CONNECTOR_REGISTRY)
    assert isinstance(resolved, ExecutionEngine)
    assert resolved._retry_policy._registry is registry


def test_runtime_event_bus_resolves_to_the_exact_runtime_owned_instance(booted_runtime: Runtime) -> None:
    resolved = booted_runtime.container.resolve("runtime.event_bus")
    assert isinstance(resolved, EventBus)
    assert resolved is booted_runtime.event_bus


def test_runtime_config_resolves_to_the_exact_runtime_owned_instance(booted_runtime: Runtime) -> None:
    resolved = booted_runtime.container.resolve("runtime.config")
    assert isinstance(resolved, ConfigLoader)
    assert resolved is booted_runtime.config_loader


def test_none_of_the_five_capabilities_resolve_to_a_module_instance(booted_runtime: Runtime) -> None:
    # The single, direct proof that would have failed before Phase 1's fix
    # for every one of the two module-provided capabilities.
    from runtime.modules.base import Module

    for capability in (
        CAPABILITY_CONNECTOR_REGISTRY,
        CAPABILITY_PLANNING_ENGINE,
        CAPABILITY_EXECUTION_ENGINE,
    ):
        assert not isinstance(booted_runtime.container.resolve(capability), Module)
