"""Requirement Synthesis's own stage logic.

Implements Requirement Synthesis Engine Specification v1.1 §4 exactly:
eight deterministic stages, zero Reasoning Engine calls. Connector
resolution reuses `discovery.engine.resolve_connector` directly rather
than reimplementing it — the same `FilesystemConnector` direct-
construction technique, the same class, wrapped only to translate
Discovery's own error type into this package's own (§7).

Every extraction rule below is syntactic or schema-based (an AST
decorator/assignment shape, a JSON key, a TOML table) — never a judgment
about what the extracted fact *means* (§1, "extracts facts only").
"""

from __future__ import annotations

import ast
import json
import re
import time
import tomllib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from discovery.contract import DiscoveredFile, RepositoryFileType, RepositoryInventory
from discovery.engine import resolve_connector as discovery_resolve_connector
from discovery.errors import DiscoveryError_
from integration.connectors.filesystem.connector import FilesystemConnector

from synthesis.contract import (
    ApiFact,
    ComponentFact,
    ConfigurationFact,
    DependencyFact,
    EntryPointFact,
    ExtensionPointFact,
    ExtractionMethod,
    ModuleFact,
    RepositoryFacts,
    ServiceFact,
    SynthesisRequest,
    SynthesisStatistics,
    UnresolvedFact,
)
from synthesis.errors import RepositoryInventoryStaleError

# -- §5 Hook Extraction rule table -- a fixed, closed vocabulary, never guessed --------------------

_HOOK_CONFIG_KEYS = frozenset(
    {
        "app_name",
        "app_title",
        "app_publisher",
        "app_description",
        "app_email",
        "app_license",
        "app_include_js",
        "app_include_css",
        "web_include_js",
        "web_include_css",
    }
)
_HOOK_SERVICE_KEYS = frozenset({"scheduler_events"})
_HOOK_DOC_EVENT_KEYS = frozenset({"doc_events"})
_HOOK_OVERRIDE_KEYS = frozenset({"override_whitelisted_methods"})
_HOOKS_FILENAME = "hooks.py"

_PEP508_NAME_PATTERN = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(.*)$")


@dataclass
class Budget:
    """Shared, mutable budget threaded through every extraction stage by
    `synthesize_requirements()` (and, identically, by `synthesis.module`'s
    own stage wrappers) so the combined file count and wall-clock deadline
    are respected across all four extraction stages together — mirrors
    `discovery.engine.walk_tree`'s own budget model, applied across stages
    rather than within one walk. Not part of the Specification's own
    Public Contract (§2) — a package-internal type shared between sibling
    files in this package only.
    """

    remaining_files: int
    deadline: float
    truncated: bool = field(default=False)

    def consume(self) -> bool:
        if self.remaining_files <= 0 or time.monotonic() > self.deadline:
            self.truncated = True
            return False
        self.remaining_files -= 1
        return True


def _flatten_strings(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            found.extend(_flatten_strings(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            found.extend(_flatten_strings(v))
    return found


def _split_pep508_name(spec: str) -> tuple[str, str]:
    match = _PEP508_NAME_PATTERN.match(spec.strip())
    if not match:
        return spec.strip(), ""
    return match.group(1), match.group(2).strip()


# -- Stage 1: Inventory Partitioning -----------------------------------------------------------------


def partition_inventory(
    inventory: RepositoryInventory,
) -> dict[RepositoryFileType, tuple[DiscoveredFile, ...]]:
    partitioned: dict[RepositoryFileType, list[DiscoveredFile]] = {}
    for discovered_file in inventory.files:
        partitioned.setdefault(discovered_file.file_type, []).append(discovered_file)
    return {file_type: tuple(files) for file_type, files in partitioned.items()}


# -- Stage 2: Module Identification -------------------------------------------------------------------


def identify_modules(inventory: RepositoryInventory) -> tuple[ModuleFact, ...]:
    modules: list[ModuleFact] = []

    package_dirs = sorted(
        {
            str(Path(discovered_file.relative_path).parent)
            for discovered_file in inventory.files
            if Path(discovered_file.relative_path).name == "__init__.py"
        }
    )
    for package_dir in package_dirs:
        if package_dir in (".", ""):
            continue
        modules.append(
            ModuleFact(
                name=package_dir.replace("/", "."),
                relative_path=package_dir,
                module_kind="python_package",
                detection_method=ExtractionMethod.DETERMINISTIC,
            )
        )

    hooks_paths = {
        discovered_file.relative_path
        for discovered_file in inventory.files
        if Path(discovered_file.relative_path).name == _HOOKS_FILENAME
    }
    for top_level_directory in inventory.metadata.top_level_directories:
        if f"{top_level_directory}/{_HOOKS_FILENAME}" in hooks_paths:
            modules.append(
                ModuleFact(
                    name=top_level_directory,
                    relative_path=top_level_directory,
                    module_kind="frappe_app",
                    detection_method=ExtractionMethod.DETERMINISTIC,
                )
            )

    return tuple(modules)


# -- Stage 3: Connector Resolution ---------------------------------------------------------------------


def resolve_connector(repository_root: str) -> FilesystemConnector:
    """Reuses `discovery.engine.resolve_connector` unmodified, translating
    Discovery's own error type into this package's own — every other
    package in this project raises its own errors rather than leaking a
    sibling package's exception type.
    """

    try:
        return discovery_resolve_connector(repository_root)
    except DiscoveryError_ as exc:
        raise RepositoryInventoryStaleError(str(exc)) from exc


# -- Stage 4: Hook Extraction --------------------------------------------------------------------------


def extract_hooks(
    hook_files: Sequence[DiscoveredFile],
    connector: FilesystemConnector,
    budget: Budget | None = None,
) -> tuple[
    tuple[ConfigurationFact, ...],
    tuple[ServiceFact, ...],
    tuple[ExtensionPointFact, ...],
    tuple[EntryPointFact, ...],
    tuple[UnresolvedFact, ...],
]:
    configuration: list[ConfigurationFact] = []
    services: list[ServiceFact] = []
    extension_points: list[ExtensionPointFact] = []
    entry_points: list[EntryPointFact] = []
    unresolved: list[UnresolvedFact] = []

    for discovered_file in hook_files:
        if budget is not None and not budget.consume():
            break
        try:
            content = connector.read_text(discovered_file.relative_path)
            tree = ast.parse(content, filename=discovered_file.relative_path)
        except (SyntaxError, OSError) as exc:
            unresolved.append(UnresolvedFact(relative_path=discovered_file.relative_path, reason=str(exc)))
            continue

        if Path(discovered_file.relative_path).name == _HOOKS_FILENAME:
            entry_points.append(
                EntryPointFact(
                    name=_HOOKS_FILENAME,
                    relative_path=discovered_file.relative_path,
                    entry_kind="frappe_app_entry",
                    detection_method=ExtractionMethod.DETERMINISTIC,
                )
            )

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.Assign):
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                value = None

            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                key = target.id

                if key in _HOOK_SERVICE_KEYS and isinstance(value, dict):
                    for name in _flatten_strings(value):
                        services.append(
                            ServiceFact(
                                name=name,
                                relative_path=discovered_file.relative_path,
                                service_kind="scheduled_task",
                                declared_via=key,
                                detection_method=ExtractionMethod.DETERMINISTIC,
                            )
                        )
                elif key in _HOOK_DOC_EVENT_KEYS and isinstance(value, dict):
                    for name in _flatten_strings(value):
                        extension_points.append(
                            ExtensionPointFact(
                                name=name,
                                relative_path=discovered_file.relative_path,
                                extension_kind="doc_event",
                                detection_method=ExtractionMethod.DETERMINISTIC,
                            )
                        )
                elif key in _HOOK_OVERRIDE_KEYS and isinstance(value, dict):
                    for name in value:
                        extension_points.append(
                            ExtensionPointFact(
                                name=str(name),
                                relative_path=discovered_file.relative_path,
                                extension_kind="override_whitelisted_method",
                                detection_method=ExtractionMethod.DETERMINISTIC,
                            )
                        )
                elif key in _HOOK_CONFIG_KEYS:
                    configuration.append(
                        ConfigurationFact(
                            key=key,
                            value="" if value is None else str(value),
                            relative_path=discovered_file.relative_path,
                            detection_method=ExtractionMethod.DETERMINISTIC,
                        )
                    )

    return (
        tuple(configuration),
        tuple(services),
        tuple(extension_points),
        tuple(entry_points),
        tuple(unresolved),
    )


# -- Stage 5: Component Extraction ---------------------------------------------------------------------


def extract_components(
    doctype_files: Sequence[DiscoveredFile],
    connector: FilesystemConnector,
    budget: Budget | None = None,
) -> tuple[tuple[ComponentFact, ...], tuple[UnresolvedFact, ...]]:
    components: list[ComponentFact] = []
    unresolved: list[UnresolvedFact] = []

    for discovered_file in doctype_files:
        if budget is not None and not budget.consume():
            break
        try:
            content = connector.read_text(discovered_file.relative_path)
            data = json.loads(content)
        except (OSError, json.JSONDecodeError) as exc:
            unresolved.append(UnresolvedFact(relative_path=discovered_file.relative_path, reason=str(exc)))
            continue

        name = data.get("name") if isinstance(data, dict) else None
        if not name:
            name = Path(discovered_file.relative_path).stem
        components.append(
            ComponentFact(
                name=str(name),
                relative_path=discovered_file.relative_path,
                component_kind="doctype",
                detection_method=ExtractionMethod.DETERMINISTIC,
            )
        )

    return tuple(components), tuple(unresolved)


# -- Stage 6: API Extraction -----------------------------------------------------------------------------


def _is_whitelist_decorator(decorator: ast.expr) -> bool:
    func = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(func, ast.Attribute):
        return func.attr == "whitelist"
    if isinstance(func, ast.Name):
        return func.id == "whitelist"
    return False


def _format_signature(args: ast.arguments) -> str:
    return "(" + ", ".join(argument.arg for argument in args.args) + ")"


def extract_apis(
    python_files: Sequence[DiscoveredFile],
    connector: FilesystemConnector,
    budget: Budget | None = None,
) -> tuple[tuple[ApiFact, ...], tuple[UnresolvedFact, ...]]:
    apis: list[ApiFact] = []
    unresolved: list[UnresolvedFact] = []

    for discovered_file in python_files:
        if budget is not None and not budget.consume():
            break
        try:
            content = connector.read_text(discovered_file.relative_path)
            tree = ast.parse(content, filename=discovered_file.relative_path)
        except (SyntaxError, OSError) as exc:
            unresolved.append(UnresolvedFact(relative_path=discovered_file.relative_path, reason=str(exc)))
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_is_whitelist_decorator(decorator) for decorator in node.decorator_list):
                apis.append(
                    ApiFact(
                        name=node.name,
                        relative_path=discovered_file.relative_path,
                        signature=_format_signature(node.args),
                        api_kind="whitelisted_method",
                        detection_method=ExtractionMethod.DETERMINISTIC,
                    )
                )

    return tuple(apis), tuple(unresolved)


# -- Stage 7: Dependency Extraction --------------------------------------------------------------------


def extract_dependencies(
    config_files: Sequence[DiscoveredFile],
    connector: FilesystemConnector,
    budget: Budget | None = None,
) -> tuple[tuple[DependencyFact, ...], tuple[UnresolvedFact, ...]]:
    dependencies: list[DependencyFact] = []
    unresolved: list[UnresolvedFact] = []

    for discovered_file in config_files:
        if budget is not None and not budget.consume():
            break
        filename = Path(discovered_file.relative_path).name
        try:
            content = connector.read_text(discovered_file.relative_path)
        except OSError as exc:
            unresolved.append(UnresolvedFact(relative_path=discovered_file.relative_path, reason=str(exc)))
            continue

        if filename == "pyproject.toml":
            try:
                data = tomllib.loads(content)
            except tomllib.TOMLDecodeError as exc:
                unresolved.append(
                    UnresolvedFact(relative_path=discovered_file.relative_path, reason=str(exc))
                )
                continue
            for dep_spec in data.get("project", {}).get("dependencies", []):
                dep_name, constraint = _split_pep508_name(dep_spec)
                dependencies.append(
                    DependencyFact(
                        name=dep_name,
                        version_constraint=constraint,
                        relative_path=discovered_file.relative_path,
                        dependency_kind="python",
                        detection_method=ExtractionMethod.DETERMINISTIC,
                    )
                )
        elif filename == "package.json":
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                unresolved.append(
                    UnresolvedFact(relative_path=discovered_file.relative_path, reason=str(exc))
                )
                continue
            for section in ("dependencies", "devDependencies"):
                for dep_name, constraint in data.get(section, {}).items():
                    dependencies.append(
                        DependencyFact(
                            name=dep_name,
                            version_constraint=str(constraint),
                            relative_path=discovered_file.relative_path,
                            dependency_kind="javascript",
                            detection_method=ExtractionMethod.DETERMINISTIC,
                        )
                    )
        elif filename == "requirements.txt":
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                dep_name, constraint = _split_pep508_name(stripped)
                dependencies.append(
                    DependencyFact(
                        name=dep_name,
                        version_constraint=constraint,
                        relative_path=discovered_file.relative_path,
                        dependency_kind="python",
                        detection_method=ExtractionMethod.DETERMINISTIC,
                    )
                )
        # Any other CONFIG-classified filename (.cfg/.ini/other .toml) is not a
        # recognized dependency manifest in v1.0 -- nothing extracted, not an error.

    return tuple(dependencies), tuple(unresolved)


# -- Stage 8: Facts Assembly -------------------------------------------------------------------------


def assemble_facts(
    request: SynthesisRequest,
    *,
    modules: tuple[ModuleFact, ...],
    components: tuple[ComponentFact, ...],
    apis: tuple[ApiFact, ...],
    services: tuple[ServiceFact, ...],
    configuration: tuple[ConfigurationFact, ...],
    dependencies: tuple[DependencyFact, ...],
    extension_points: tuple[ExtensionPointFact, ...],
    entry_points: tuple[EntryPointFact, ...],
    unresolved: tuple[UnresolvedFact, ...],
    files_examined: int,
    files_skipped: int,
    truncated: bool,
) -> RepositoryFacts:
    facts_extracted = (
        len(modules)
        + len(components)
        + len(apis)
        + len(services)
        + len(configuration)
        + len(dependencies)
        + len(extension_points)
        + len(entry_points)
    )
    statistics = SynthesisStatistics(
        files_examined=files_examined,
        files_skipped=files_skipped,
        files_failed=len(unresolved),
        facts_extracted=facts_extracted,
    )
    return RepositoryFacts(
        facts_id=str(uuid.uuid4()),
        source_inventory_id=request.repository_inventory.inventory_id,
        repository_root=request.repository_inventory.repository_root,
        synthesized_at=datetime.now(UTC).isoformat(),
        correlation_id=request.correlation_id,
        modules=modules,
        components=components,
        apis=apis,
        services=services,
        configuration=configuration,
        dependencies=dependencies,
        extension_points=extension_points,
        entry_points=entry_points,
        unresolved=unresolved,
        truncated=truncated,
        statistics=statistics,
    )


# -- §2's public interface: the plain-function composition of all eight stages -----------------------

#: Kinds Discovery's own classification identifies that this engine's
#: supported scope (§5) knows how to extract from. Anything else in the
#: inventory is counted in files_skipped, never attempted.
_RELEVANT_TYPES = (
    RepositoryFileType.HOOK,
    RepositoryFileType.DOCTYPE,
    RepositoryFileType.PYTHON_SOURCE,
    RepositoryFileType.CONFIG,
)


def synthesize_requirements(request: SynthesisRequest) -> RepositoryFacts:
    """The single, plain-function composition of all eight stages — §2's
    first interface: no Container, no Module, no Pipeline Engine required.
    """

    inventory = request.repository_inventory
    partitioned = partition_inventory(inventory)
    modules = identify_modules(inventory)
    connector = resolve_connector(inventory.repository_root)

    relevant_count = sum(len(partitioned.get(file_type, ())) for file_type in _RELEVANT_TYPES)
    files_skipped = len(inventory.files) - relevant_count
    budget = Budget(remaining_files=request.max_files, deadline=time.monotonic() + request.timeout_seconds)

    configuration, services, extension_points, entry_points, unresolved_hooks = extract_hooks(
        partitioned.get(RepositoryFileType.HOOK, ()), connector, budget
    )
    components, unresolved_components = extract_components(
        partitioned.get(RepositoryFileType.DOCTYPE, ()), connector, budget
    )
    apis, unresolved_apis = extract_apis(
        partitioned.get(RepositoryFileType.PYTHON_SOURCE, ()), connector, budget
    )
    dependencies, unresolved_dependencies = extract_dependencies(
        partitioned.get(RepositoryFileType.CONFIG, ()), connector, budget
    )

    unresolved = unresolved_hooks + unresolved_components + unresolved_apis + unresolved_dependencies
    # budget.remaining_files started at request.max_files and was decremented once per
    # file actually consumed across all four stages combined -- this is exact whether
    # or not truncation occurred (if relevant_count < max_files, nothing was truncated
    # and this equals relevant_count naturally).
    files_examined = request.max_files - budget.remaining_files

    return assemble_facts(
        request,
        modules=modules,
        components=components,
        apis=apis,
        services=services,
        configuration=configuration,
        dependencies=dependencies,
        extension_points=extension_points,
        entry_points=entry_points,
        unresolved=unresolved,
        files_examined=files_examined,
        files_skipped=files_skipped,
        truncated=budget.truncated,
    )
