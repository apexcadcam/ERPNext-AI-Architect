"""Shared Runtime exception hierarchy.

Every error a Runtime component raises during boot or operation is a
subclass of :class:`RuntimeError_`, so callers (notably the CLI and the
boot sequence) can catch "something in the Runtime went wrong" without
needing to know which subsystem raised it, while still being able to
narrow to a specific category when they need to.
"""

from __future__ import annotations


class RuntimeError_(Exception):
    """Base class for every error raised by the Runtime platform.

    Named with a trailing underscore to avoid shadowing the built-in
    ``RuntimeError``.
    """


class ConfigurationError(RuntimeError_):
    """A configuration value or layer failed validation.

    Per docs/runtime/CONFIGURATION_SYSTEM.md §4: a schema violation at
    any layer is boot-blocking, never a warning.
    """


class ManifestError(RuntimeError_):
    """A module manifest is missing, malformed, or fails schema validation.

    Per docs/runtime/RUNTIME_BOOT_SEQUENCE.md §2: a manifest that fails to
    parse is boot-blocking — its intended enabled/disabled state is itself
    unknown, so it cannot be safely defaulted.
    """


class DependencyValidationError(RuntimeError_):
    """The module capability graph failed validation.

    Raised for an unsatisfied capabilities_required entry, a dependency
    cycle, or ambiguous capability provision — the three checks in
    docs/runtime/PLUGIN_REGISTRY.md §4.
    """


class CapabilityResolutionError(RuntimeError_):
    """The Dependency Injection Container could not resolve a capability.

    Per docs/runtime/DEPENDENCY_INJECTION.md §5: this should never happen
    for a module that already passed dependency validation — if it does,
    it is treated as a Runtime defect, not a configuration problem.
    """


class ModuleLifecycleError(RuntimeError_):
    """A module's validate()/init()/start()/stop()/health_check() hook failed."""


class PipelineDefinitionError(RuntimeError_):
    """A Pipeline Definition is malformed or references an unbound stage."""


class StageExecutionError(RuntimeError_):
    """A pipeline stage failed in a way its retry policy could not recover from."""
