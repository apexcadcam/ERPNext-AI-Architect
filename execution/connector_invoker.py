"""`ConnectorInvoker` — Sprint 5 Architecture Package §9.3.

A structural `Protocol`, mirroring `planning.graph_reader.GraphReader`'s
exact narrowing shape: a read/invoke-only view of Integration's
`ConnectorRegistry` — `ExecutionContext.connector_invoker` is typed as this
narrow interface, never the full `ConnectorRegistry`, since Execution has
no legitimate reason to `register()` a new connector or `discover()` a
search path mid-run.

Unlike `GraphReader` (which had an already-existing object,
`InMemoryGraphStore`, to structurally satisfy it), no pre-existing object
matches this shape — `RegistryConnectorInvoker` is new code, the one
concrete implementation this Sprint ships, wrapping a real
`ConnectorRegistry` plus the resolved connector's own `invoke()`
(Sprint 5 Phase 1).

Per the Sprint 5 Implementation Plan's own Planning Notes, this is also
where `ConnectorInvoked`/`ConnectorSucceeded`/`ConnectorFailed` (`integration
.events`) would be published — but that remains contingent on the still
-unresolved `ExecutionContext.event_bus` architecture clarification, so no
publication happens here yet. `RegistryConnectorInvoker`'s dispatch logic
(resolve capability -> instantiate -> connect -> invoke) is complete and
independently tested without it.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from integration.contract import ConnectorRequest, ConnectorResponse
from integration.lifecycle import ConnectorLifecycle
from integration.registry import ConnectorRegistry


@runtime_checkable
class ConnectorInvoker(Protocol):
    """The read/invoke-only method surface `ExecutionContext` carries,
    instead of the full `ConnectorRegistry`.
    """

    def is_available(self, capability: str) -> bool: ...

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse: ...


class RegistryConnectorInvoker:
    """Wraps a real `ConnectorRegistry` (Sprint 3, frozen). Resolves a
    capability to its providing connector via `capability_providers()`,
    instantiates and connects it on first use, and caches the connected
    instance for reuse across subsequent calls to the same connector —
    `ConnectorRegistry.instantiate()` itself performs no caching and does
    not call `connect()`, both of which are this class's own
    responsibility, not the Registry's.
    """

    def __init__(self, registry: ConnectorRegistry) -> None:
        self._registry = registry
        self._connected: dict[str, ConnectorLifecycle] = {}

    def is_available(self, capability: str) -> bool:
        return len(self._registry.capability_providers(capability)) > 0

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        providers = self._registry.capability_providers(capability)
        if not providers:
            return ConnectorResponse(
                status="failure",
                diagnostics=f"no registered connector provides capability '{capability}'",
                correlation_id=correlation_id,
            )

        connector_id = providers[0]
        try:
            connector = self._connector_for(connector_id)
        except Exception as exc:
            return ConnectorResponse(
                status="failure",
                diagnostics=f"connector '{connector_id}' unavailable: {exc}",
                correlation_id=correlation_id,
            )

        request = ConnectorRequest(
            operation=capability,
            parameters=parameters,
            correlation_id=correlation_id,
            requested_by=requested_by,
        )
        return connector.invoke(request)

    def _connector_for(self, connector_id: str) -> ConnectorLifecycle:
        connector = self._connected.get(connector_id)
        if connector is None:
            connector = self._registry.instantiate(connector_id)
            connector.connect()
            self._connected[connector_id] = connector
        return connector
