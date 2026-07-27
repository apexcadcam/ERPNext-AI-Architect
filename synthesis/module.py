"""The Synthesis module — Runtime-facing host for Requirement Synthesis's
eight pipeline stages.

Implements Requirement Synthesis Engine Specification v1.1 §2's Module
lifecycle. Like `discovery.module.DiscoveryModule`, `init()` calls zero
`container.resolve(...)`: every stage function is pure and self-contained
(`synthesis.engine`), constructing its own `FilesystemConnector` from data
already present in its own input rather than depending on any other
module's capability — `capabilities_required` is empty.

Each stage wrapper below delegates to the exact same package-internal
functions `synthesis.engine.synthesize_requirements()` itself composes —
no duplicated stage logic between the plain-function interface and the
Pipeline-Engine-driven one.
"""

from __future__ import annotations

import time
from typing import Any

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.pipeline.engine import PipelineContext, StageOutcome

from discovery.contract import RepositoryFileType
from synthesis.contract import SynthesisRequest
from synthesis.engine import (
    Budget,
    assemble_facts,
    extract_apis,
    extract_components,
    extract_dependencies,
    extract_hooks,
    identify_modules,
    partition_inventory,
    resolve_connector,
)

#: The eight Container capabilities this module provides — one per
#: Requirement Synthesis stage (§4), matching `synthesis.pipeline`'s own
#: `StageDefinition.capability` bindings exactly.
CAPABILITY_PARTITION_INVENTORY = "synthesis.partition_inventory"
CAPABILITY_IDENTIFY_MODULES = "synthesis.identify_modules"
CAPABILITY_RESOLVE_CONNECTOR = "synthesis.resolve_connector"
CAPABILITY_EXTRACT_HOOKS = "synthesis.extract_hooks"
CAPABILITY_EXTRACT_COMPONENTS = "synthesis.extract_components"
CAPABILITY_EXTRACT_APIS = "synthesis.extract_apis"
CAPABILITY_EXTRACT_DEPENDENCIES = "synthesis.extract_dependencies"
CAPABILITY_ASSEMBLE_FACTS = "synthesis.assemble_facts"

#: Kinds this engine's supported scope (§5) knows how to extract from —
#: identical to synthesis.engine's own module-level constant, restated
#: here since the pipeline path computes files_skipped in this stage
#: rather than inside synthesize_requirements().
_RELEVANT_TYPES = (
    RepositoryFileType.HOOK,
    RepositoryFileType.DOCTYPE,
    RepositoryFileType.PYTHON_SOURCE,
    RepositoryFileType.CONFIG,
)


def _partition_inventory_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request: SynthesisRequest = data
    inventory = request.repository_inventory
    partitioned = partition_inventory(inventory)
    relevant_count = sum(len(partitioned.get(file_type, ())) for file_type in _RELEVANT_TYPES)
    files_skipped = len(inventory.files) - relevant_count
    return (request, partitioned, files_skipped), StageOutcome.SUCCESS


def _identify_modules_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, partitioned, files_skipped = data
    modules = identify_modules(request.repository_inventory)
    return (request, partitioned, files_skipped, modules), StageOutcome.SUCCESS


def _resolve_connector_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, partitioned, files_skipped, modules = data
    connector = resolve_connector(request.repository_inventory.repository_root)
    budget = Budget(remaining_files=request.max_files, deadline=time.monotonic() + request.timeout_seconds)
    return (request, partitioned, files_skipped, modules, connector, budget), StageOutcome.SUCCESS


def _extract_hooks_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, partitioned, files_skipped, modules, connector, budget = data
    configuration, services, extension_points, entry_points, unresolved = extract_hooks(
        partitioned.get(RepositoryFileType.HOOK, ()), connector, budget
    )
    return (
        request,
        partitioned,
        files_skipped,
        modules,
        connector,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved,
    ), StageOutcome.SUCCESS


def _extract_components_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    (
        request,
        partitioned,
        files_skipped,
        modules,
        connector,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved,
    ) = data
    components, unresolved_components = extract_components(
        partitioned.get(RepositoryFileType.DOCTYPE, ()), connector, budget
    )
    return (
        request,
        partitioned,
        files_skipped,
        modules,
        connector,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved + unresolved_components,
        components,
    ), StageOutcome.SUCCESS


def _extract_apis_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    (
        request,
        partitioned,
        files_skipped,
        modules,
        connector,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved,
        components,
    ) = data
    apis, unresolved_apis = extract_apis(
        partitioned.get(RepositoryFileType.PYTHON_SOURCE, ()), connector, budget
    )
    return (
        request,
        partitioned,
        files_skipped,
        modules,
        connector,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved + unresolved_apis,
        components,
        apis,
    ), StageOutcome.SUCCESS


def _extract_dependencies_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    (
        request,
        partitioned,
        files_skipped,
        modules,
        connector,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved,
        components,
        apis,
    ) = data
    dependencies, unresolved_dependencies = extract_dependencies(
        partitioned.get(RepositoryFileType.CONFIG, ()), connector, budget
    )
    return (
        request,
        files_skipped,
        modules,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved + unresolved_dependencies,
        components,
        apis,
        dependencies,
    ), StageOutcome.SUCCESS


def _assemble_facts_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    (
        request,
        files_skipped,
        modules,
        budget,
        configuration,
        services,
        extension_points,
        entry_points,
        unresolved,
        components,
        apis,
        dependencies,
    ) = data
    facts = assemble_facts(
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
        files_examined=request.max_files - budget.remaining_files,
        files_skipped=files_skipped,
        truncated=budget.truncated,
    )
    return facts, StageOutcome.SUCCESS


class SynthesisModule(Module):
    """Provides the eight Requirement Synthesis stage capabilities.
    Requires nothing — see this module's own docstring.
    """

    def init(self, container: Container) -> None:
        container.register(CAPABILITY_PARTITION_INVENTORY, lambda: _partition_inventory_stage)
        container.register(CAPABILITY_IDENTIFY_MODULES, lambda: _identify_modules_stage)
        container.register(CAPABILITY_RESOLVE_CONNECTOR, lambda: _resolve_connector_stage)
        container.register(CAPABILITY_EXTRACT_HOOKS, lambda: _extract_hooks_stage)
        container.register(CAPABILITY_EXTRACT_COMPONENTS, lambda: _extract_components_stage)
        container.register(CAPABILITY_EXTRACT_APIS, lambda: _extract_apis_stage)
        container.register(CAPABILITY_EXTRACT_DEPENDENCIES, lambda: _extract_dependencies_stage)
        container.register(CAPABILITY_ASSEMBLE_FACTS, lambda: _assemble_facts_stage)

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="Synthesis stages ready")
