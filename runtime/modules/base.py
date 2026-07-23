"""The Module lifecycle interface.

Implements docs/runtime/MODULE_SYSTEM.md §3: every module implements
validate() / init() / start() / stop() / health_check(), invoked by the
Runtime at the points defined in LIFECYCLE.md and RUNTIME_BOOT_SEQUENCE.md.
A module never reaches outside the Container it's handed in init() — see
DEPENDENCY_INJECTION.md §1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

from runtime.modules.manifest import ModuleManifest

if TYPE_CHECKING:
    from runtime.container.di import Container


class HealthCheckResult(BaseModel):
    """A module's current health, per LOGGING_AND_OBSERVABILITY.md §4."""

    healthy: bool
    detail: str = ""


class Module(ABC):
    """Base class every plugin's entry-point factory returns an instance of.

    `manifest` is supplied at construction time by whatever created this
    instance (normally the Plugin Registry, from the `module.yaml` it
    discovered alongside this module's code) — a Module never invents its
    own manifest, and the two must agree (enforced by the Registry, not by
    this class, which has no way to see the file on disk).
    """

    def __init__(self, manifest: ModuleManifest) -> None:
        self.manifest = manifest

    def validate(self) -> None:
        """Check this module's own configuration/preconditions are satisfiable.

        The default implementation does nothing — most modules have nothing
        beyond what MODULE_SYSTEM.md §2's manifest fields already declare
        (checked separately, by the Plugin Registry, not by this hook).
        Override when a module has additional preconditions only it can
        check (e.g. a required external binary being on PATH).
        """

    @abstractmethod
    def init(self, container: Container) -> None:
        """Resolve `capabilities_required` from `container` and construct
        internal state. Must never reach for a dependency any other way.
        """

    def start(self) -> None:
        """Begin ongoing behavior (event subscriptions, stage handlers, ...).

        Default implementation does nothing — a module with no ongoing
        behavior beyond what init() set up (uncommon, but valid) doesn't
        need to override this.
        """

    def stop(self) -> None:
        """Release everything acquired in start(). Always called on shutdown,
        even after an abnormal Runtime stop (LIFECYCLE.md §3).
        """

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Report current health. Called at boot (RUNTIME_BOOT_SEQUENCE.md §7)
        and on demand (`architect doctor`).
        """
