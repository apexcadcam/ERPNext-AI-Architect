"""The Plugin Registry: discovery, registration, dependency validation.

Implements docs/runtime/PLUGIN_REGISTRY.md in full:

  §1 Discovery       — enumerate module.yaml manifests, no hardcoded imports
  §2 Registration     — index by module_id, no code executed yet
  §3 Enable / Disable  — explicit per-module state, config-driven
  §4 Dependency Validation — satisfied / acyclic / unambiguous
  §5 Capability Discovery   — query the graph after validation

"Plugins should be loadable even if none currently exist" (Sprint 1): every
method below degrades gracefully to empty results on an empty or missing
search path — that is a normal, expected state, never an error.
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from runtime.errors import DependencyValidationError, ManifestError, ModuleLifecycleError
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest, load_manifest

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "module.yaml"


@dataclass(frozen=True)
class DiscoveredPlugin:
    """One module found on disk: its manifest plus where its code lives."""

    manifest: ModuleManifest
    plugin_dir: Path


@dataclass
class DependencyValidationReport:
    """The result of PLUGIN_REGISTRY.md §4's three checks, always fully computed
    (never short-circuited) so every issue can be reported at once.
    """

    unsatisfied_requirements: list[str] = field(default_factory=list)
    ambiguous_capabilities: list[str] = field(default_factory=list)
    cycle: list[str] | None = None

    @property
    def ok(self) -> bool:
        return not self.unsatisfied_requirements and not self.ambiguous_capabilities and self.cycle is None

    def as_issues(self) -> list[str]:
        issues = list(self.unsatisfied_requirements) + list(self.ambiguous_capabilities)
        if self.cycle is not None:
            issues.append(f"dependency cycle detected: {' -> '.join(self.cycle)}")
        return issues


class PluginRegistry:
    """Discovers, registers, and validates modules. Executes none of their
    code beyond dynamic import at explicit instantiation time — discovery
    and dependency validation operate on manifest data alone.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, DiscoveredPlugin] = {}
        self._enabled_overrides: dict[str, bool] = {}
        self._validated = False

    # -- §1 Discovery ----------------------------------------------------

    def discover(self, search_paths: Iterable[Path]) -> list[DiscoveredPlugin]:
        """Scan each path for immediate subdirectories containing a manifest.

        Does not register anything — call register() (or register_all()) on
        the result. Kept separate so a caller can inspect what was found
        before committing it to the registry (useful for `architect doctor`
        style diagnostics).
        """

        found: list[DiscoveredPlugin] = []
        for base in search_paths:
            if not base.is_dir():
                logger.debug("plugin search path does not exist, skipping", extra={"path": str(base)})
                continue
            for child in sorted(p for p in base.iterdir() if p.is_dir()):
                manifest_path = child / _MANIFEST_FILENAME
                if not manifest_path.is_file():
                    continue
                manifest = load_manifest(manifest_path)
                found.append(DiscoveredPlugin(manifest=manifest, plugin_dir=child))
                logger.info(
                    "discovered plugin manifest",
                    extra={"module_id": manifest.module_id, "path": str(manifest_path)},
                )
        return found

    # -- §2 Registration ---------------------------------------------------

    def register(self, plugin: DiscoveredPlugin) -> None:
        existing = self._plugins.get(plugin.manifest.module_id)
        if existing is not None and existing.plugin_dir != plugin.plugin_dir:
            raise ManifestError(
                f"duplicate module_id '{plugin.manifest.module_id}' found at both "
                f"{existing.plugin_dir} and {plugin.plugin_dir}"
            )
        self._plugins[plugin.manifest.module_id] = plugin
        self._validated = False

    def register_all(self, plugins: Iterable[DiscoveredPlugin]) -> None:
        for plugin in plugins:
            self.register(plugin)

    def all_plugins(self) -> tuple[DiscoveredPlugin, ...]:
        return tuple(self._plugins.values())

    def get(self, module_id: str) -> DiscoveredPlugin | None:
        return self._plugins.get(module_id)

    # -- §3 Enable / Disable ------------------------------------------------

    def set_enabled(self, module_id: str, enabled: bool) -> None:
        self._enabled_overrides[module_id] = enabled
        self._validated = False

    def is_enabled(self, module_id: str) -> bool:
        if module_id in self._enabled_overrides:
            return self._enabled_overrides[module_id]
        plugin = self._plugins.get(module_id)
        return plugin.manifest.enabled_by_default if plugin is not None else False

    def enabled_plugins(self) -> tuple[DiscoveredPlugin, ...]:
        return tuple(p for p in self._plugins.values() if self.is_enabled(p.manifest.module_id))

    # -- §4 Dependency Validation --------------------------------------------

    def _build_dependency_graph(
        self, enabled: tuple[DiscoveredPlugin, ...]
    ) -> tuple[dict[str, list[str]], dict[str, set[str]], DependencyValidationReport]:
        """Shared by validate_dependencies() and dependency_order() so the two
        can never disagree about what "depends on" means for this graph.
        """

        provider_of: dict[str, list[str]] = {}
        for plugin in enabled:
            for capability in plugin.manifest.capabilities_provided:
                provider_of.setdefault(capability, []).append(plugin.manifest.module_id)

        report = DependencyValidationReport()
        for capability, providers in provider_of.items():
            if len(providers) > 1:
                report.ambiguous_capabilities.append(
                    f"capability '{capability}' is provided by more than one enabled module: {sorted(providers)}"
                )

        depends_on: dict[str, set[str]] = {}
        for plugin in enabled:
            module_id = plugin.manifest.module_id
            deps: set[str] = set()
            for requirement in plugin.manifest.capabilities_required:
                providers = provider_of.get(requirement, [])
                if not providers:
                    report.unsatisfied_requirements.append(
                        f"module '{module_id}' requires capability '{requirement}', "
                        f"which no enabled module provides"
                    )
                elif len(providers) == 1:
                    deps.add(providers[0])
                # len(providers) > 1 is already reported as ambiguous above;
                # we don't also report it as a dependency-graph edge, since
                # which provider would even be depended on is itself undefined.
            depends_on[module_id] = deps

        return provider_of, depends_on, report

    def validate_dependencies(self, *, raise_on_failure: bool = True) -> DependencyValidationReport:
        """Run all three checks against the currently-enabled plugin set.

        Never short-circuits on the first problem — every issue is
        collected so a single validation pass can report everything wrong,
        per the same "report all, not just the first" discipline the
        Configuration System uses.
        """

        enabled = self.enabled_plugins()
        _, depends_on, report = self._build_dependency_graph(enabled)
        report.cycle = _find_cycle(depends_on)

        self._validated = report.ok

        if raise_on_failure and not report.ok:
            formatted = "\n".join(f"  - {issue}" for issue in report.as_issues())
            raise DependencyValidationError(f"plugin dependency validation failed:\n{formatted}")

        return report

    def dependency_order(self) -> tuple[str, ...]:
        """Every enabled module_id, ordered so a module always appears after
        everything it depends on (Kahn's algorithm). Requires the current
        enabled set to already be valid — call validate_dependencies() first;
        this method assumes an acyclic graph and does not re-check.

        Used by the boot sequence to start modules dependencies-first, and
        by shutdown (in reverse) to stop them dependents-first, per
        LIFECYCLE.md §3.
        """

        enabled = self.enabled_plugins()
        _, depends_on, _ = self._build_dependency_graph(enabled)

        in_degree = {module_id: len(deps) for module_id, deps in depends_on.items()}
        # dependents[x] = modules that depend on x, i.e. reverse edges
        dependents: dict[str, list[str]] = {module_id: [] for module_id in depends_on}
        for module_id, deps in depends_on.items():
            for dep in deps:
                dependents.setdefault(dep, []).append(module_id)

        ready = sorted(module_id for module_id, degree in in_degree.items() if degree == 0)
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependent in sorted(dependents.get(node, ())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)

        return tuple(order)

    @property
    def validated(self) -> bool:
        """Whether the currently-enabled set last passed validate_dependencies()."""

        return self._validated

    # -- §5 Capability Discovery ---------------------------------------------

    def capability_providers(self, capability: str) -> tuple[str, ...]:
        return tuple(
            p.manifest.module_id for p in self.enabled_plugins() if capability in p.manifest.capabilities_provided
        )

    def all_provided_capabilities(self) -> frozenset[str]:
        return frozenset(
            capability for plugin in self.enabled_plugins() for capability in plugin.manifest.capabilities_provided
        )

    # -- Instantiation (dynamic import, per manifest's declared entry_point) --

    def instantiate(self, module_id: str) -> Module:
        """Dynamically import a plugin's declared entry point and construct
        its Module instance. The Runtime never has a static `import
        crawler_module` anywhere — this is the one, generic, manifest-driven
        loading path every plugin goes through identically.
        """

        plugin = self._plugins.get(module_id)
        if plugin is None:
            raise ManifestError(f"no plugin registered with module_id '{module_id}'")

        entry_file = plugin.plugin_dir / f"{plugin.manifest.entry_module_name}.py"
        if not entry_file.is_file():
            raise ManifestError(
                f"module '{module_id}' declares entry_point '{plugin.manifest.entry_point}' "
                f"but {entry_file} does not exist"
            )

        spec = importlib.util.spec_from_file_location(
            f"runtime_plugin_{module_id}_{plugin.manifest.entry_module_name}", entry_file
        )
        if spec is None or spec.loader is None:
            raise ManifestError(f"could not load entry point module from {entry_file}")

        py_module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(py_module)
        except Exception as exc:
            raise ModuleLifecycleError(f"module '{module_id}' entry point raised on import: {exc}") from exc

        factory = getattr(py_module, plugin.manifest.entry_factory_name, None)
        if factory is None or not callable(factory):
            raise ManifestError(
                f"module '{module_id}' entry_point '{plugin.manifest.entry_point}' does not "
                f"resolve to a callable factory"
            )

        try:
            instance = factory(plugin.manifest)
        except Exception as exc:
            raise ModuleLifecycleError(f"module '{module_id}' factory raised: {exc}") from exc

        if not isinstance(instance, Module):
            raise ManifestError(
                f"module '{module_id}' entry_point '{plugin.manifest.entry_point}' factory "
                f"returned {type(instance).__name__}, which is not a Module subclass"
            )

        return instance


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    """Depth-first cycle detection (white/gray/black coloring).

    Returns the cycle as an ordered list of module_ids if one exists,
    else None. Deterministic: iterates nodes and edges in a stable
    (insertion) order so the same graph always reports the same cycle.
    """

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(graph, WHITE)
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for neighbor in graph.get(node, ()):
            neighbor_color = color.get(neighbor, WHITE)
            if neighbor_color == GRAY:
                cycle_start = path.index(neighbor)
                return [*path[cycle_start:], neighbor]
            if neighbor_color == WHITE:
                result = visit(neighbor)
                if result is not None:
                    return result
        color[node] = BLACK
        path.pop()
        return None

    for node in graph:
        if color[node] == WHITE:
            found = visit(node)
            if found is not None:
                return found
    return None
