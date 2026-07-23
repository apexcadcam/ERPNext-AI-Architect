"""Tests for the Runtime/Module/PipelineRun state machines (LIFECYCLE.md)."""

from __future__ import annotations

import pytest

from runtime.lifecycle import (
    InvalidTransitionError,
    ModuleState,
    PipelineRunState,
    RuntimeState,
    new_module_lifecycle,
    new_pipeline_run_lifecycle,
    new_runtime_lifecycle,
)


def test_runtime_lifecycle_starts_at_starting() -> None:
    machine = new_runtime_lifecycle()
    assert machine.state is RuntimeState.STARTING


def test_runtime_lifecycle_follows_the_documented_boot_order() -> None:
    machine = new_runtime_lifecycle()
    order = [
        RuntimeState.PLUGIN_DISCOVERY,
        RuntimeState.DEPENDENCY_VALIDATION,
        RuntimeState.CONFIG_LOADING,
        RuntimeState.PIPELINE_REGISTRATION,
        RuntimeState.CONNECTOR_REGISTRATION,
        RuntimeState.HEALTH_CHECKING,
        RuntimeState.READY,
    ]
    for target in order:
        machine.transition(target)
    assert machine.state is RuntimeState.READY
    assert machine.history[0] is RuntimeState.STARTING


def test_runtime_lifecycle_rejects_skipping_a_step() -> None:
    machine = new_runtime_lifecycle()
    with pytest.raises(InvalidTransitionError):
        machine.transition(RuntimeState.READY)


def test_runtime_lifecycle_any_step_may_fail() -> None:
    machine = new_runtime_lifecycle()
    machine.transition(RuntimeState.PLUGIN_DISCOVERY)
    machine.transition(RuntimeState.FAILED)
    assert machine.state is RuntimeState.FAILED
    assert machine.can_transition(RuntimeState.READY) is False  # terminal


def test_module_lifecycle_restart_reenters_at_initialized_not_registered() -> None:
    machine = new_module_lifecycle()
    for target in (ModuleState.VALIDATED, ModuleState.INITIALIZED, ModuleState.STARTED, ModuleState.RUNNING):
        machine.transition(target)
    machine.transition(ModuleState.STOPPING)
    machine.transition(ModuleState.STOPPED)

    machine.transition(ModuleState.INITIALIZED)  # restart
    assert machine.state is ModuleState.INITIALIZED
    assert not machine.can_transition(ModuleState.REGISTERED)  # never goes backward


def test_pipeline_run_lifecycle_failure_path_goes_through_rollback() -> None:
    machine = new_pipeline_run_lifecycle()
    machine.transition(PipelineRunState.RUNNING)
    machine.transition(PipelineRunState.FAILED)
    machine.transition(PipelineRunState.ROLLING_BACK)
    machine.transition(PipelineRunState.ROLLED_BACK)
    assert machine.state is PipelineRunState.ROLLED_BACK


def test_pipeline_run_lifecycle_completed_is_terminal() -> None:
    machine = new_pipeline_run_lifecycle()
    machine.transition(PipelineRunState.RUNNING)
    machine.transition(PipelineRunState.COMPLETED)
    assert machine.can_transition(PipelineRunState.ROLLING_BACK) is False
