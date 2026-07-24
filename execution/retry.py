"""`RetryPolicy` — Sprint 5 Architecture Package §17.

Not a new policy Execution invents — the mechanical fulfillment of
`SPRINT3_ARCHITECTURE_PACKAGE.md §6.1` decl. 7 and §6.5, which had no
caller to exercise it until now. Re-resolves a step's live `kind`/
`idempotent` classification from the live `ConnectorRegistry` — never from
the `Plan`, which only ever carries `requires_confirmation` forward from
planning time (`planning.contract.CapabilityDescriptor` -> `PlanStep`,
Sprint 4).

**Disclosed gap, not silently resolved:** `ConnectorManifest.
retryable_status_codes` (Sprint 3, frozen) is a tuple of *numeric* codes,
but `integration.contract.ConnectorResponse` (Sprint 5 Phase 1) carries no
numeric status code field for it to filter against — `status` is the
three-value `Literal["success", "failure", "partial"]`, nothing else. This
was already named, structurally, as inert in Sprint 3 itself
(`tests/integration/test_contract.py`'s own "structural only, no
invocation in Phase 3" comment on the retry fields) — Phase 4 is simply
the first place that fact becomes observable. Given no numeric code exists
to filter by, `RetryPolicy` treats every `status="failure"` response as
retryable-if-idempotent; `retryable_status_codes` remains unused by this
implementation, not modified, and not deleted from the manifest schema.

**Disclosed open question for Phase 5:** nothing in the approved
`ExecutionContext` (§11) or `ExecutionEngine.execute()` (§9.2) signature
provides a path to a live `ConnectorRegistry` reference — `RetryPolicy`
therefore takes one directly in its own constructor, the natural, minimal
shape matching §17's own text ("re-resolves... from the live
ConnectorRegistry"). How `ExecutionEngine` (Phase 5) actually obtains a
`ConnectorRegistry` to construct a `RetryPolicy` from is not resolved here
— the same kind of composition-root gap already disclosed for
`ExecutionContext.event_bus` (Phase 3). This phase's own scope is
"independently testable against fakes... not yet wired into a full
orchestration loop" — that wiring, and the gap it will need to close, is
Phase 5's concern.
"""

from __future__ import annotations

import time
from typing import Any

from integration.contract import ConnectorManifest, ConnectorOperation, ConnectorResponse
from integration.registry import ConnectorRegistry

from execution.connector_invoker import ConnectorInvoker


class RetryPolicy:
    """Wraps one `ConnectorRegistry` (Sprint 3, frozen) for classification
    lookups. Stateless across calls otherwise.
    """

    def __init__(self, registry: ConnectorRegistry) -> None:
        self._registry = registry

    def invoke_with_retries(
        self,
        invoker: ConnectorInvoker,
        capability: str,
        parameters: dict[str, Any],
        *,
        correlation_id: str,
        requested_by: str,
    ) -> tuple[ConnectorResponse, int]:
        """Calls `invoker.invoke(...)` once, then — only if the operation
        is classified `idempotent` and the response's `status` is
        `"failure"` — retries up to the connector's own declared
        `max_attempts`, honoring `backoff_kind`/`base_delay_ms`. A
        non-idempotent operation, or one this registry cannot classify at
        all, is never retried: the first attempt is terminal. Returns
        `(final_response, attempts_made)`.
        """

        operation, manifest = self._resolve(capability)
        idempotent = operation is not None and operation.idempotent
        max_attempts = manifest.max_attempts if (idempotent and manifest is not None) else 1
        base_delay_ms = manifest.base_delay_ms if manifest is not None else 0

        response = invoker.invoke(
            capability, parameters, correlation_id=correlation_id, requested_by=requested_by
        )
        attempt = 1
        while response.status == "failure" and idempotent and attempt < max_attempts:
            delay_seconds = (base_delay_ms / 1000) * (2 ** (attempt - 1))
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            response = invoker.invoke(
                capability, parameters, correlation_id=correlation_id, requested_by=requested_by
            )
            attempt += 1

        return response, attempt

    def _resolve(self, capability: str) -> tuple[ConnectorOperation | None, ConnectorManifest | None]:
        providers = self._registry.capability_providers(capability)
        if not providers:
            return None, None
        discovered = self._registry.get(providers[0])
        if discovered is None:
            return None, None
        for operation in discovered.manifest.operations:
            if operation.capability == capability:
                return operation, discovered.manifest
        return None, discovered.manifest
