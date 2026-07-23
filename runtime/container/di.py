"""The Dependency Injection Container.

Implements docs/runtime/DEPENDENCY_INJECTION.md: modules never instantiate
each other — every capability is resolved through this Container, by
capability name, never by concrete type or module name (§2). This is what
lets a future second provider, or a test double, satisfy an existing
dependency with zero change to the requesting module's own code (§4).
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from runtime.errors import CapabilityResolutionError

logger = logging.getLogger(__name__)


class CapabilityScope(enum.Enum):
    """See DEPENDENCY_INJECTION.md §3."""

    #: Resolved once, lives for the Runtime process lifetime.
    SINGLETON = "singleton"
    #: Resolved once per pipeline-run id, torn down at that run's end.
    PIPELINE_RUN = "pipeline_run"
    #: Resolved once per CLI invocation / external call, torn down after.
    REQUEST = "request"


Provider = Callable[[], Any]


@dataclass(frozen=True)
class _Registration:
    capability: str
    provider: Provider
    scope: CapabilityScope


class Container:
    """Resolves capabilities. Holds no domain knowledge of what any of them do."""

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}
        self._singleton_cache: dict[str, Any] = {}
        self._scoped_cache: dict[tuple[CapabilityScope, str, str], Any] = {}

    def register(
        self,
        capability: str,
        provider: Provider,
        *,
        scope: CapabilityScope = CapabilityScope.SINGLETON,
        override: bool = False,
    ) -> None:
        """Register a provider (a zero-argument factory) for `capability`.

        `override=True` is the seam DEPENDENCY_INJECTION.md §4 describes for
        test doubles — substituting a real provider with a minimal fake that
        satisfies the identical capability contract, invisibly to whatever
        resolves it.
        """

        if capability in self._registrations and not override:
            raise CapabilityResolutionError(
                f"capability '{capability}' is already registered "
                f"(pass override=True to replace it, e.g. for a test double)"
            )
        self._registrations[capability] = _Registration(capability, provider, scope)
        # A re-registration invalidates any cached singleton instance, so a
        # test override never accidentally returns the previous provider's
        # cached value.
        self._singleton_cache.pop(capability, None)

    def is_registered(self, capability: str) -> bool:
        return capability in self._registrations

    def provided_capabilities(self) -> frozenset[str]:
        return frozenset(self._registrations)

    def resolve(self, capability: str, *, scope_id: str | None = None) -> Any:
        """Resolve `capability`.

        `scope_id` is required for PIPELINE_RUN/REQUEST-scoped capabilities
        (e.g. the pipeline_run_id or a CLI invocation id) and ignored for
        SINGLETON ones. Per DEPENDENCY_INJECTION.md §5: a resolution failure
        here for a capability that already passed Plugin Registry dependency
        validation is a Runtime defect, not a configuration problem — this
        method does not attempt to be forgiving about it.
        """

        registration = self._registrations.get(capability)
        if registration is None:
            raise CapabilityResolutionError(
                f"no provider registered for capability '{capability}' — this should have "
                f"been caught by dependency validation before any module reached init()"
            )

        if registration.scope is CapabilityScope.SINGLETON:
            if capability not in self._singleton_cache:
                self._singleton_cache[capability] = registration.provider()
            return self._singleton_cache[capability]

        if scope_id is None:
            raise CapabilityResolutionError(
                f"capability '{capability}' is {registration.scope.value}-scoped and requires a scope_id"
            )
        cache_key = (registration.scope, capability, scope_id)
        if cache_key not in self._scoped_cache:
            self._scoped_cache[cache_key] = registration.provider()
        return self._scoped_cache[cache_key]

    def close_scope(self, scope: CapabilityScope, scope_id: str) -> None:
        """Evict every cached instance for one pipeline-run/request scope.

        Called when a pipeline run completes/fails or a CLI invocation ends
        — DEPENDENCY_INJECTION.md §3's "the Container is responsible for
        tearing down scoped instances at the end of their scope's lifetime."
        """

        keys_to_drop = [key for key in self._scoped_cache if key[0] is scope and key[2] == scope_id]
        for key in keys_to_drop:
            del self._scoped_cache[key]
