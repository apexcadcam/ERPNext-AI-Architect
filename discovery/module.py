"""The Discovery module — Runtime-facing host for Repository Discovery's
four pipeline stages.

Implements Repository Discovery Engine Specification v1.1 §2's Module
lifecycle. Notably the first `Module` in this codebase whose `init()`
calls zero `container.resolve(...)`: every stage function is pure and
self-contained (`discovery.engine`), constructing its own
`FilesystemConnector` from its own input rather than depending on any
other module's capability — `capabilities_required` is empty.

Each stage wrapper below delegates to the exact same package-internal
functions `discovery.engine.discover_repository()` itself composes — no
duplicated stage logic between the plain-function interface and the
Pipeline-Engine-driven one.
"""

from __future__ import annotations

from typing import Any

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.pipeline.engine import PipelineContext, StageOutcome

from discovery.contract import DiscoveryRequest
from discovery.engine import assemble_inventory, classify_entries, resolve_connector, walk_tree

#: The four Container capabilities this module provides — one per
#: Repository Discovery stage (§3), matching `discovery.pipeline`'s own
#: `StageDefinition.capability` bindings exactly.
CAPABILITY_RESOLVE_ROOT = "discovery.resolve_root"
CAPABILITY_WALK_TREE = "discovery.walk_tree"
CAPABILITY_CLASSIFY_ENTRIES = "discovery.classify_entries"
CAPABILITY_ASSEMBLE_INVENTORY = "discovery.assemble_inventory"


def _resolve_root_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request: DiscoveryRequest = data
    connector = resolve_connector(request.repository_root)
    return (request, connector), StageOutcome.SUCCESS


def _walk_tree_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, connector = data
    walk_result = walk_tree(
        connector,
        exclude_patterns=request.exclude_patterns,
        max_files=request.max_files,
        timeout_seconds=request.timeout_seconds,
    )
    return (request, walk_result), StageOutcome.SUCCESS


def _classify_entries_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, walk_result = data
    files = classify_entries(request.repository_root, walk_result.relative_paths)
    return (request, walk_result, files), StageOutcome.SUCCESS


def _assemble_inventory_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, walk_result, files = data
    inventory = assemble_inventory(request, walk_result, files)
    return inventory, StageOutcome.SUCCESS


class DiscoveryModule(Module):
    """Provides the four Repository Discovery stage capabilities.
    Requires nothing — see this module's own docstring.
    """

    def init(self, container: Container) -> None:
        container.register(CAPABILITY_RESOLVE_ROOT, lambda: _resolve_root_stage)
        container.register(CAPABILITY_WALK_TREE, lambda: _walk_tree_stage)
        container.register(CAPABILITY_CLASSIFY_ENTRIES, lambda: _classify_entries_stage)
        container.register(CAPABILITY_ASSEMBLE_INVENTORY, lambda: _assemble_inventory_stage)

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="Discovery stages ready")
