"""The Integration module — the Connector framework's Runtime-facing host.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §5.1: exactly one new entry in
`docs/runtime/MODULE_SYSTEM.md §5`'s domain-module table, declaring itself
against the ordinary `runtime.modules.base.Module` contract like Crawler,
Extractor, or Validator — nothing about the Runtime, the top-level
`PluginRegistry`, or the Container changes to accommodate it.

Per §5.1/§14: this module exposes only one, generic capability —
"give me the connector registry" — and never references a concrete
connector anywhere in its own code. Per §5.2/§11.1, it hosts its own
nested `ConnectorRegistry`, invisible to the Runtime's top-level
`PluginRegistry`, which sees only this one module.
"""

from __future__ import annotations

from pathlib import Path

from integration.registry import ConnectorRegistry
from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.modules.manifest import ModuleManifest

#: The one capability this module provides — resolves to the
#: `ConnectorRegistry` instance itself, per §6.3: a future caller (an
#: Agent/Skill's Tool execution layer, unbuilt) resolves this capability
#: through the ordinary Container, then queries the registry object for
#: `capability_providers(...)`/`instantiate(...)` — this module never
#: forwards an individual connector's capability into the Container
#: directly, since capabilities_provided is a *static*, manifest-declared
#: set validated before any module's init() runs
#: (`docs/runtime/PLUGIN_REGISTRY.md §4`), while connector registration
#: happens dynamically, inside this module's own init().
CAPABILITY_CONNECTOR_REGISTRY = "integration.connector_registry"


class IntegrationModule(Module):
    """Hosts the nested `ConnectorRegistry`. Provides
    `integration.connector_registry`; requires nothing.

    `connector_search_paths` is set by whoever assembles the Runtime,
    before `init()` runs — mirroring how `Runtime.__init__` itself takes
    `plugin_search_paths` explicitly (`runtime/boot.py`) rather than a
    module inventing its own configuration-resolution mechanism. Empty by
    default: with no search paths configured, `init()` discovers zero
    connectors, a normal and expected state per Phase 3's own scope ("no
    actual connectors") — not an error, the same way an empty
    `plugin_search_paths` list is a normal, working Runtime configuration
    today.
    """

    def __init__(self, manifest: ModuleManifest) -> None:
        super().__init__(manifest)
        self.registry = ConnectorRegistry()
        self.connector_search_paths: list[Path] = []

    def init(self, container: Container) -> None:
        discovered = self.registry.discover(self.connector_search_paths)
        self.registry.register_all(discovered)
        self.registry.validate()

        container.register(CAPABILITY_CONNECTOR_REGISTRY, lambda: self.registry, override=True)

    def health_check(self) -> HealthCheckResult:
        connector_count = len(self.registry.all_connectors())
        return HealthCheckResult(healthy=True, detail=f"{connector_count} connector(s) registered")
