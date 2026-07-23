"""The Connector Lifecycle interface.

Implements the four lifecycle hooks named in Sprint 3 Phase 3's own task
description — `initialize`, `connect`, `disconnect`, `health_check` — as
the Connector-level generalization of `runtime.modules.base.Module`'s
five-hook lifecycle (`validate`/`init`/`start`/`stop`/`health_check`) one
layer down, per SPRINT3_ARCHITECTURE_PACKAGE.md §5.4's "validated by the
same... checks... applied one level down."

No implementation logic and no networking live here — this is an abstract
interface only. A concrete connector (a later phase, explicitly out of
Phase 3's scope) supplies real `connect()`/`health_check()` behavior
against a real external system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from integration.contract import ConnectorManifest


class ConnectorHealth(BaseModel):
    """A connector's current health — §6.1 declaration 9's probe result.
    Mirrors `runtime.modules.base.HealthCheckResult` exactly, one layer
    down.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    healthy: bool
    detail: str = ""


class ConnectorLifecycle(ABC):
    """Base class every connector's entry-point factory returns an
    instance of. `manifest` is supplied at construction time by whatever
    created this instance (normally `ConnectorRegistry.instantiate()`,
    from the `connector.yaml` it discovered alongside this connector's
    code) — a connector never invents its own manifest, mirroring
    `runtime.modules.base.Module`'s identical contract.
    """

    def __init__(self, manifest: ConnectorManifest) -> None:
        self.manifest = manifest

    def initialize(self) -> None:
        """Construct whatever internal state this connector needs from its
        own manifest, before `connect()` may be called. Default: no-op —
        many connectors need nothing here beyond what `__init__` already
        set up, the same default `runtime.modules.base.Module.validate()`
        already establishes for the hook one layer up.
        """

    @abstractmethod
    def connect(self) -> None:
        """Establish whatever connection state this connector needs before
        any operation can run. §5.3: a connector must never allow an
        operation to run before this has succeeded.
        """

    def disconnect(self) -> None:
        """Release whatever `connect()` acquired. Default: no-op, mirroring
        `runtime.modules.base.Module.stop()`'s identical default.
        """

    @abstractmethod
    def health_check(self) -> ConnectorHealth:
        """§6.1 declaration 9: a lightweight, read-only, side-effect-free
        probe — always present, regardless of what this connector's real
        Operation Catalog contains.
        """
