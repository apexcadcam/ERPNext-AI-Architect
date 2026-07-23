"""Runtime, Module, and Pipeline Run state machines.

Implements exactly the three state machines specified in
docs/runtime/LIFECYCLE.md — no additional states, no additional
transitions. This module owns *only* Runtime-level lifecycle; it says
nothing about Engineering Rule status, RM sync state, or Knowledge
Document staleness, which remain owned by their own already-frozen
lifecycle documents (see LIFECYCLE.md §5).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Generic, TypeVar


class InvalidTransitionError(Exception):
    """Raised when a transition is attempted that the state machine forbids."""

    def __init__(self, current: enum.Enum, target: enum.Enum, allowed: frozenset[enum.Enum]) -> None:
        self.current = current
        self.target = target
        self.allowed = allowed
        allowed_names = ", ".join(sorted(s.name for s in allowed)) or "(terminal state)"
        super().__init__(
            f"cannot transition {type(current).__name__}.{current.name} -> {target.name}; "
            f"allowed next states: {allowed_names}"
        )


class RuntimeState(enum.Enum):
    """The Runtime process's own lifecycle. See LIFECYCLE.md §1."""

    STARTING = "starting"
    PLUGIN_DISCOVERY = "plugin_discovery"
    DEPENDENCY_VALIDATION = "dependency_validation"
    CONFIG_LOADING = "config_loading"
    PIPELINE_REGISTRATION = "pipeline_registration"
    CONNECTOR_REGISTRATION = "connector_registration"
    HEALTH_CHECKING = "health_checking"
    READY = "ready"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


class ModuleState(enum.Enum):
    """A single module's lifecycle. See LIFECYCLE.md §2."""

    REGISTERED = "registered"
    VALIDATED = "validated"
    INITIALIZED = "initialized"
    STARTED = "started"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class PipelineRunState(enum.Enum):
    """A single pipeline run's lifecycle. See LIFECYCLE.md §4."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


# Boot sequence is strictly linear up to READY (RUNTIME_BOOT_SEQUENCE.md §0),
# any step may fail into FAILED, and RUNNING may return to STARTING only via
# a brand-new Runtime instance (a restart is a new process lifecycle, not a
# transition — see LIFECYCLE.md §9's restart-vs-cold-boot distinction).
_RUNTIME_TRANSITIONS: dict[RuntimeState, frozenset[RuntimeState]] = {
    RuntimeState.STARTING: frozenset({RuntimeState.PLUGIN_DISCOVERY, RuntimeState.FAILED}),
    RuntimeState.PLUGIN_DISCOVERY: frozenset({RuntimeState.DEPENDENCY_VALIDATION, RuntimeState.FAILED}),
    RuntimeState.DEPENDENCY_VALIDATION: frozenset({RuntimeState.CONFIG_LOADING, RuntimeState.FAILED}),
    RuntimeState.CONFIG_LOADING: frozenset({RuntimeState.PIPELINE_REGISTRATION, RuntimeState.FAILED}),
    RuntimeState.PIPELINE_REGISTRATION: frozenset({RuntimeState.CONNECTOR_REGISTRATION, RuntimeState.FAILED}),
    RuntimeState.CONNECTOR_REGISTRATION: frozenset({RuntimeState.HEALTH_CHECKING, RuntimeState.FAILED}),
    RuntimeState.HEALTH_CHECKING: frozenset({RuntimeState.READY, RuntimeState.FAILED}),
    RuntimeState.READY: frozenset({RuntimeState.RUNNING, RuntimeState.FAILED}),
    RuntimeState.RUNNING: frozenset({RuntimeState.DRAINING, RuntimeState.FAILED}),
    RuntimeState.DRAINING: frozenset({RuntimeState.STOPPED, RuntimeState.FAILED}),
    RuntimeState.STOPPED: frozenset(),
    RuntimeState.FAILED: frozenset(),
}

# A restart re-enters at INITIALIZED, not REGISTERED (MODULE_SYSTEM.md §3 /
# LIFECYCLE.md §2) — the manifest and its validation result don't change on
# restart, only the module's own runtime state does.
_MODULE_TRANSITIONS: dict[ModuleState, frozenset[ModuleState]] = {
    ModuleState.REGISTERED: frozenset({ModuleState.VALIDATED, ModuleState.FAILED}),
    ModuleState.VALIDATED: frozenset({ModuleState.INITIALIZED, ModuleState.FAILED}),
    ModuleState.INITIALIZED: frozenset({ModuleState.STARTED, ModuleState.FAILED}),
    ModuleState.STARTED: frozenset({ModuleState.RUNNING, ModuleState.FAILED}),
    ModuleState.RUNNING: frozenset({ModuleState.STOPPING, ModuleState.FAILED}),
    ModuleState.STOPPING: frozenset({ModuleState.STOPPED, ModuleState.FAILED}),
    ModuleState.STOPPED: frozenset({ModuleState.INITIALIZED}),  # restart
    ModuleState.FAILED: frozenset({ModuleState.INITIALIZED}),  # restart after recovery
}

_PIPELINE_RUN_TRANSITIONS: dict[PipelineRunState, frozenset[PipelineRunState]] = {
    PipelineRunState.QUEUED: frozenset({PipelineRunState.RUNNING, PipelineRunState.CANCELLED}),
    PipelineRunState.RUNNING: frozenset(
        {PipelineRunState.COMPLETED, PipelineRunState.FAILED, PipelineRunState.CANCELLED}
    ),
    PipelineRunState.COMPLETED: frozenset(),
    PipelineRunState.FAILED: frozenset({PipelineRunState.ROLLING_BACK}),
    PipelineRunState.CANCELLED: frozenset({PipelineRunState.ROLLING_BACK}),
    PipelineRunState.ROLLING_BACK: frozenset({PipelineRunState.ROLLED_BACK}),
    PipelineRunState.ROLLED_BACK: frozenset(),
}


StateT = TypeVar("StateT", bound=enum.Enum)


@dataclass
class StateMachine(Generic[StateT]):
    """A generic, strictly-validated state holder.

    Not exported directly — use new_runtime_lifecycle() / new_module_lifecycle()
    / new_pipeline_run_lifecycle() below, which bind this to the correct
    transition table so an invalid transition is caught at the state-table
    level, not scattered across ad hoc if/else checks.
    """

    state: StateT
    _transitions: dict[StateT, frozenset[StateT]] = field(repr=False)
    _history: list[StateT] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._history.append(self.state)

    def can_transition(self, target: StateT) -> bool:
        return target in self._transitions.get(self.state, frozenset())

    def transition(self, target: StateT) -> None:
        if not self.can_transition(target):
            raise InvalidTransitionError(self.state, target, self._transitions.get(self.state, frozenset()))
        self.state = target
        self._history.append(target)

    @property
    def history(self) -> tuple[StateT, ...]:
        return tuple(self._history)


def new_runtime_lifecycle() -> StateMachine[RuntimeState]:
    return StateMachine(state=RuntimeState.STARTING, _transitions=_RUNTIME_TRANSITIONS)


def new_module_lifecycle() -> StateMachine[ModuleState]:
    return StateMachine(state=ModuleState.REGISTERED, _transitions=_MODULE_TRANSITIONS)


def new_pipeline_run_lifecycle() -> StateMachine[PipelineRunState]:
    return StateMachine(state=PipelineRunState.QUEUED, _transitions=_PIPELINE_RUN_TRANSITIONS)
