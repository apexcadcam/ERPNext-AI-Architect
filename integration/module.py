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

    `connector_search_paths` may still be set by hand by whoever assembles
    the Runtime, before `init()` runs, exactly as originally designed —
    that path is unchanged and always takes priority if already set.
    `init()` additionally resolves it from the Configuration System, via
    the `"runtime.config"` capability (Sprint 6 Architecture Package §7.3,
    §18 ADR Candidate B), closing `ADR-0009`'s own long-named
    `connector_search_paths` wiring gap generically — no special-casing of
    Integration by name anywhere in `runtime/boot.py`, the same "resolve
    it yourself, don't have the Runtime hand it to you" discipline
    `runtime.event_bus` already established for `knowledge/extraction/
    module.py`/`knowledge/validation/module.py`. Empty by default: with no
    search paths configured (by hand or by config), `init()` discovers
    zero connectors, a normal and expected state per Phase 3's own scope
    ("no actual connectors") — not an error, the same way an empty
    `plugin_search_paths` list is a normal, working Runtime configuration
    today.
    """

    def __init__(self, manifest: ModuleManifest) -> None:
        super().__init__(manifest)
        self.registry = ConnectorRegistry()
        self.connector_search_paths: list[Path] = []

    def init(self, container: Container) -> None:
        if not self.connector_search_paths and container.is_registered("runtime.config"):
            config_loader = container.resolve("runtime.config")
            resolved = config_loader.resolve(module_id=self.manifest.module_id, strict=False)
            self.connector_search_paths = [Path(p) for p in resolved.get("connector_search_paths", [])]

        discovered = self.registry.discover(self.connector_search_paths)
        self.registry.register_all(discovered)
        self.registry.validate()

        container.register(CAPABILITY_CONNECTOR_REGISTRY, lambda: self.registry, override=True)

    def health_check(self) -> HealthCheckResult:
        connector_count = len(self.registry.all_connectors())
        return HealthCheckResult(healthy=True, detail=f"{connector_count} connector(s) registered")
