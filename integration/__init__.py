"""The Integration Layer — Sprint 3, Phase 3.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §5 (Plugin Architecture), §6
framework (Connector Architecture — the Contract only, no concrete
connector), and §11.1 (the boot sequence's nested Connector Registration).

Phase 3 scope only: the Integration module, the Connector Contract, the
Connector Lifecycle interface, and the nested Connector Registry. No
concrete connector (Filesystem, ERPNext, GitHub, MCP, Docker, PostgreSQL,
Playwright), no networking, no live systems, no Graph Builder/Adapter — all
explicitly later phases.
"""

from __future__ import annotations

from integration.contract import (
    KNOWN_TARGET_SYSTEM_TYPES,
    ConnectorManifest,
    ConnectorOperation,
    load_connector_manifest,
)
from integration.errors import ConnectorLifecycleError, ConnectorManifestError, ConnectorValidationError
from integration.lifecycle import ConnectorHealth, ConnectorLifecycle
from integration.module import CAPABILITY_CONNECTOR_REGISTRY, IntegrationModule
from integration.registry import ConnectorRegistry, ConnectorValidationReport, DiscoveredConnector

__all__ = [
    "CAPABILITY_CONNECTOR_REGISTRY",
    "KNOWN_TARGET_SYSTEM_TYPES",
    "ConnectorHealth",
    "ConnectorLifecycle",
    "ConnectorLifecycleError",
    "ConnectorManifest",
    "ConnectorManifestError",
    "ConnectorOperation",
    "ConnectorRegistry",
    "ConnectorValidationError",
    "ConnectorValidationReport",
    "DiscoveredConnector",
    "IntegrationModule",
    "load_connector_manifest",
]
