"""The nested Connector Registry: discovery, registration, ambiguous-
capability validation, capability discovery, and instantiation — all
scoped one level inside the Integration module.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §5.2/§5.4/§6.3 and §11.1 in
full: "the same fractal shape at the layer above," mirroring
`runtime.registry.plugin_registry.PluginRegistry`'s Discovery/
Registration/Validation/Capability-Discovery shape exactly, applied to
Connectors instead of Modules. This registry is invisible to the Runtime's
own top-level `PluginRegistry`, which only ever sees one entry: "the
Integration module" — nothing here is discovered, registered, or validated
by that top-level registry, and this registry never registers a Module of
its own.

Unlike `PluginRegistry`, this registry has no dependency graph (no cycle
detection, no `capabilities_required`, no enable/disable): §6.1's ten
declarations name no `capabilities_required` field for a Connector — per
§5.3, a connector must never depend on another connector's state, so no
legitimate inter-connector dependency edge exists to validate in the first
place. The one validation this registry performs is §5.4's ambiguous-
capability check, the direct generalization of
`docs/runtime/PLUGIN_REGISTRY.md §4.3`'s identical check for Modules.
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from integration.contract import ConnectorManifest, load_connector_manifest
from integration.errors import ConnectorLifecycleError, ConnectorManifestError, ConnectorValidationError
from integration.lifecycle import ConnectorLifecycle

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "connector.yaml"


@dataclass(frozen=True)
class DiscoveredConnector:
    """One connector found on disk: its manifest plus where its code lives."""

    manifest: ConnectorManifest
    connector_dir: Path


@dataclass
class ConnectorValidationReport:
    """The result of §5.4's ambiguous-capability check, always fully
    computed (never short-circuited) so every issue can be reported at
    once — the same "report all, not just the first" discipline
    `docs/runtime/PLUGIN_REGISTRY.md §4` already establishes.
    """

    ambiguous_capabilities: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.ambiguous_capabilities

    def as_issues(self) -> list[str]:
        return list(self.ambiguous_capabilities)


class ConnectorRegistry:
    """Discovers, registers, and validates connectors. Executes none of
    their code beyond dynamic import at explicit `instantiate()` time —
    discovery and capability validation operate on manifest data alone,
    mirroring `PluginRegistry`'s identical discipline.

    Two `ConnectorRegistry` instances never share state — each is its own,
    fully independent instance, the way one Integration module's registry
    is isolated from any other's (§14's "least-privilege" boundary,
    applied structurally here as well as by policy).
    """

    def __init__(self) -> None:
        self._connectors: dict[str, DiscoveredConnector] = {}
        self._validated = False

    # -- §5.2 Discovery ----------------------------------------------------

    def discover(self, search_paths: Iterable[Path]) -> list[DiscoveredConnector]:
        """Scan each path for immediate subdirectories containing a
        `connector.yaml` manifest. Does not register anything — call
        `register()`/`register_all()` on the result, mirroring
        `PluginRegistry.discover()`'s identical separation.

        An empty or missing search path is a normal, expected state — "no
        actual connectors" (Phase 3's own scope) — never an error.
        """

        found: list[DiscoveredConnector] = []
        for base in search_paths:
            if not base.is_dir():
                logger.debug("connector search path does not exist, skipping", extra={"path": str(base)})
                continue
            for child in sorted(p for p in base.iterdir() if p.is_dir()):
                manifest_path = child / _MANIFEST_FILENAME
                if not manifest_path.is_file():
                    continue
                manifest = load_connector_manifest(manifest_path)
                found.append(DiscoveredConnector(manifest=manifest, connector_dir=child))
                logger.info(
                    "discovered connector manifest",
                    extra={"connector_id": manifest.connector_id, "path": str(manifest_path)},
                )
        return found

    # -- Registration ------------------------------------------------------

    def register(self, connector: DiscoveredConnector) -> None:
        existing = self._connectors.get(connector.manifest.connector_id)
        if existing is not None and existing.connector_dir != connector.connector_dir:
            raise ConnectorManifestError(
                f"duplicate connector_id '{connector.manifest.connector_id}' found at both "
                f"{existing.connector_dir} and {connector.connector_dir}"
            )
        self._connectors[connector.manifest.connector_id] = connector
        self._validated = False

    def register_all(self, connectors: Iterable[DiscoveredConnector]) -> None:
        for connector in connectors:
            self.register(connector)

    def all_connectors(self) -> tuple[DiscoveredConnector, ...]:
        return tuple(self._connectors.values())

    def get(self, connector_id: str) -> DiscoveredConnector | None:
        return self._connectors.get(connector_id)

    # -- §5.4 Validation (ambiguous capability only — see module docstring) --

    def validate(self, *, raise_on_failure: bool = True) -> ConnectorValidationReport:
        report = ConnectorValidationReport()
        provider_of: dict[str, list[str]] = {}
        for connector in self._connectors.values():
            for capability in connector.manifest.provided_capabilities:
                provider_of.setdefault(capability, []).append(connector.manifest.connector_id)

        for capability, providers in provider_of.items():
            if len(providers) > 1:
                report.ambiguous_capabilities.append(
                    f"capability '{capability}' is provided by more than one registered connector: "
                    f"{sorted(providers)}"
                )

        self._validated = report.ok

        if raise_on_failure and not report.ok:
            formatted = "\n".join(f"  - {issue}" for issue in report.as_issues())
            raise ConnectorValidationError(f"connector capability validation failed:\n{formatted}")

        return report

    @property
    def validated(self) -> bool:
        """Whether the currently-registered set last passed `validate()`."""

        return self._validated

    # -- §6.3 Capability Discovery -------------------------------------------

    def capability_providers(self, capability: str) -> tuple[str, ...]:
        return tuple(
            connector.manifest.connector_id
            for connector in self._connectors.values()
            if capability in connector.manifest.provided_capabilities
        )

    def all_provided_capabilities(self) -> frozenset[str]:
        return frozenset(
            capability
            for connector in self._connectors.values()
            for capability in connector.manifest.provided_capabilities
        )

    # -- Instantiation (dynamic import, per manifest's declared entry_point) --

    def instantiate(self, connector_id: str) -> ConnectorLifecycle:
        """Dynamically import a connector's declared entry point and
        construct its `ConnectorLifecycle` instance. Mirrors
        `PluginRegistry.instantiate()`'s identical, generic,
        manifest-driven loading path — this registry never has a static
        `import erpnext_connector` anywhere.
        """

        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ConnectorManifestError(f"no connector registered with connector_id '{connector_id}'")

        entry_file = connector.connector_dir / f"{connector.manifest.entry_module_name}.py"
        if not entry_file.is_file():
            raise ConnectorManifestError(
                f"connector '{connector_id}' declares entry_point '{connector.manifest.entry_point}' "
                f"but {entry_file} does not exist"
            )

        spec = importlib.util.spec_from_file_location(
            f"integration_connector_{connector_id}_{connector.manifest.entry_module_name}", entry_file
        )
        if spec is None or spec.loader is None:
            raise ConnectorManifestError(f"could not load entry point module from {entry_file}")

        py_module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(py_module)
        except Exception as exc:
            raise ConnectorLifecycleError(
                f"connector '{connector_id}' entry point raised on import: {exc}"
            ) from exc

        factory = getattr(py_module, connector.manifest.entry_factory_name, None)
        if factory is None or not callable(factory):
            raise ConnectorManifestError(
                f"connector '{connector_id}' entry_point '{connector.manifest.entry_point}' does not "
                f"resolve to a callable factory"
            )

        try:
            instance = factory(connector.manifest)
        except Exception as exc:
            raise ConnectorLifecycleError(f"connector '{connector_id}' factory raised: {exc}") from exc

        if not isinstance(instance, ConnectorLifecycle):
            raise ConnectorManifestError(
                f"connector '{connector_id}' entry_point '{connector.manifest.entry_point}' factory "
                f"returned {type(instance).__name__}, which is not a ConnectorLifecycle subclass"
            )

        return instance
