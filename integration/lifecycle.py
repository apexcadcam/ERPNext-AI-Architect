"""The Connector Lifecycle interface.

Implements the four lifecycle hooks named in Sprint 3 Phase 3's own task
description — `initialize`, `connect`, `disconnect`, `health_check` — as
the Connector-level generalization of `runtime.modules.base.Module`'s
five-hook lifecycle (`validate`/`init`/`start`/`stop`/`health_check`) one
layer down, per SPRINT3_ARCHITECTURE_PACKAGE.md §5.4's "validated by the
same... checks... applied one level down."

Sprint 5, Phase 1 adds one more abstract method, `invoke()` — completing
SPRINT3_ARCHITECTURE_PACKAGE.md §6.2's own Connector Request/Response
Envelope design, never implemented until now (`ADR-0009`'s C1 finding).
Per the Sprint 5 Architecture Package §9.1's own Design Rationale, `invoke()`
belongs on this same class rather than a separate interface: the connection
state it needs is exactly the state `connect()` already sets up on the same
instance, and splitting the two would not reduce that coupling, only add a
second contract for no offsetting benefit.

No implementation logic and no networking live here — this is an abstract
interface only. A concrete connector supplies real `connect()`/
`health_check()`/`invoke()` behavior against a real external system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from integration.contract import ConnectorManifest, ConnectorRequest, ConnectorResponse


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

    @abstractmethod
    def invoke(self, request: ConnectorRequest) -> ConnectorResponse:
        """§6.2's Connector Request/Response Envelope: the one, generic way
        every operation in this connector's Operation Catalog is called.
        Dispatches on `request.operation` (matching a declared
        `ConnectorOperation.name`/`.capability`) to this connector's own
        implementation of that operation.

        Must never be called before `connect()` has succeeded (§5.3) — a
        connector raises `ConnectorLifecycleError` if it is. An ordinary
        operational failure (a missing file, an invalid parameter, a
        downstream error) is never raised — it is reported as
        `ConnectorResponse(status="failure", diagnostics=...)`; raising is
        reserved for a genuine lifecycle-contract violation.
        """
