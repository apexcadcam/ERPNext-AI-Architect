"""The Integration Layer — Sprint 3, Phase 3, extended by Sprint 5, Phase 1.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §5 (Plugin Architecture), §6
(Connector Architecture — the Contract, and, since Sprint 5, the
Request/Response Envelope and `invoke()`), and §11.1 (the boot sequence's
nested Connector Registration).

No concrete connector beyond Filesystem, no networking beyond what
Filesystem's own local-path operations require, no live systems, no Graph
Builder/Adapter — all still later phases.
"""

from __future__ import annotations

from integration.contract import (
    KNOWN_TARGET_SYSTEM_TYPES,
    ConnectorManifest,
    ConnectorOperation,
    ConnectorRequest,
    ConnectorResponse,
    load_connector_manifest,
)
from integration.errors import ConnectorLifecycleError, ConnectorManifestError, ConnectorValidationError
from integration.events import CONNECTOR_FAILED, CONNECTOR_INVOKED, CONNECTOR_SUCCEEDED
from integration.lifecycle import ConnectorHealth, ConnectorLifecycle
from integration.module import CAPABILITY_CONNECTOR_REGISTRY, IntegrationModule
from integration.registry import ConnectorRegistry, ConnectorValidationReport, DiscoveredConnector

__all__ = [
    "CAPABILITY_CONNECTOR_REGISTRY",
    "CONNECTOR_FAILED",
    "CONNECTOR_INVOKED",
    "CONNECTOR_SUCCEEDED",
    "KNOWN_TARGET_SYSTEM_TYPES",
    "ConnectorHealth",
    "ConnectorLifecycle",
    "ConnectorLifecycleError",
    "ConnectorManifest",
    "ConnectorManifestError",
    "ConnectorOperation",
    "ConnectorRegistry",
    "ConnectorRequest",
    "ConnectorResponse",
    "ConnectorValidationError",
    "ConnectorValidationReport",
    "DiscoveredConnector",
    "IntegrationModule",
    "load_connector_manifest",
]
