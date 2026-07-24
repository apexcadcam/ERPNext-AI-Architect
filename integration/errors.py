"""Shared Integration Layer exception hierarchy.

Mirrors runtime/errors.py's discipline one level down: every error a
Connector Contract or the nested Connector Registry raises is a subclass of
:class:`IntegrationError_`, distinct from `runtime.errors`'s hierarchy —
this project's established pattern (see knowledge/, secrets_management/)
is for each new package to own its own narrow exceptions rather than
overload the Runtime's, even where the failure category is conceptually
similar.
"""

from __future__ import annotations


class IntegrationError_(Exception):
    """Base class for every error raised by the Integration Layer.

    Named with a trailing underscore for the same reason
    `runtime.errors.RuntimeError_` is: to avoid shadowing a built-in-shaped
    name at a glance.
    """


class ConnectorManifestError(IntegrationError_):
    """A connector manifest is missing, malformed, or fails schema
    validation. Per SPRINT3_ARCHITECTURE_PACKAGE.md §6.1: a connector that
    cannot truthfully complete its declarations does not qualify for
    registration — mirrors runtime.errors.ManifestError one level down.
    """


class ConnectorValidationError(IntegrationError_):
    """The connector capability set failed validation — a duplicate
    connector_id or an ambiguous (multiply-provided) capability, mirroring
    docs/runtime/PLUGIN_REGISTRY.md §4's checks, applied to Connectors
    instead of Modules per SPRINT3_ARCHITECTURE_PACKAGE.md §5.4.
    """


class ConnectorLifecycleError(IntegrationError_):
    """A connector's initialize()/connect()/disconnect()/health_check()/
    invoke() hook failed, or was invoked out of the declared lifecycle
    order — including `invoke()` being called before `connect()` has
    succeeded (Sprint 5, Phase 1). An ordinary operational failure inside
    an operation itself is never this — it is reported as a
    `ConnectorResponse(status="failure", ...)`, not raised.
    """
