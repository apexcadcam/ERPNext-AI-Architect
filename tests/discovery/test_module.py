"""Tests for `discovery.module` (Repository Discovery Engine Specification v1.1 §2)."""

from __future__ import annotations

from pathlib import Path

from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, StageOutcome

from discovery.contract import DiscoveryRequest, RepositoryInventory
from discovery.module import (
    CAPABILITY_ASSEMBLE_INVENTORY,
    CAPABILITY_CLASSIFY_ENTRIES,
    CAPABILITY_RESOLVE_ROOT,
    CAPABILITY_WALK_TREE,
    DiscoveryModule,
)


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="discovery",
        display_name="Repository Discovery",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(
            CAPABILITY_RESOLVE_ROOT,
            CAPABILITY_WALK_TREE,
            CAPABILITY_CLASSIFY_ENTRIES,
            CAPABILITY_ASSEMBLE_INVENTORY,
        ),
        entry_point="module:create",
    )


def _context() -> PipelineContext:
    from datetime import UTC, datetime

    return PipelineContext(
        pipeline_run_id="run-1",
        correlation_id="corr-1",
        pipeline_name="discovery.repository",
        started_at=datetime.now(UTC),
    )


def test_discovery_module_is_a_module() -> None:
    assert isinstance(DiscoveryModule(_manifest()), Module)


def test_health_check_is_healthy_before_init() -> None:
    assert DiscoveryModule(_manifest()).health_check().healthy is True


def test_health_check_is_healthy_after_init() -> None:
    module = DiscoveryModule(_manifest())
    module.init(Container())
    assert module.health_check().healthy is True


def test_manifest_requires_no_capabilities() -> None:
    # The first Module in this codebase whose own manifest requires
    # nothing from any other module (Repository Discovery Engine
    # Specification v1.1 §2's own disclosed finding).
    assert _manifest().capabilities_required == ()


def test_init_registers_all_four_stage_capabilities() -> None:
    module = DiscoveryModule(_manifest())
    container = Container()

    module.init(container)

    assert container.is_registered(CAPABILITY_RESOLVE_ROOT)
    assert container.is_registered(CAPABILITY_WALK_TREE)
    assert container.is_registered(CAPABILITY_CLASSIFY_ENTRIES)
    assert container.is_registered(CAPABILITY_ASSEMBLE_INVENTORY)


def test_init_calls_no_container_resolve() -> None:
    # A completely empty Container has nothing registered -- if init() ever
    # called container.resolve(...) on anything, that call would raise
    # CapabilityResolutionError immediately. DiscoveryModule requires
    # nothing (its own manifest declares capabilities_required=()), so
    # init() against an empty container must succeed.
    module = DiscoveryModule(_manifest())

    module.init(Container())


def test_resolve_root_stage_callable_produces_a_connected_connector(tmp_path: Path) -> None:
    module = DiscoveryModule(_manifest())
    container = Container()
    module.init(container)
    stage = container.resolve(CAPABILITY_RESOLVE_ROOT)

    request = DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")
    output, outcome = stage(request, _context())

    assert outcome is StageOutcome.SUCCESS
    result_request, connector = output
    assert result_request is request
    assert connector.health_check().healthy is True


def test_full_four_stage_sequence_produces_a_repository_inventory(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text("# hook\n")
    module = DiscoveryModule(_manifest())
    container = Container()
    module.init(container)

    request = DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")
    context = _context()

    data, outcome = container.resolve(CAPABILITY_RESOLVE_ROOT)(request, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_WALK_TREE)(data, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_CLASSIFY_ENTRIES)(data, context)
    assert outcome is StageOutcome.SUCCESS
    inventory, outcome = container.resolve(CAPABILITY_ASSEMBLE_INVENTORY)(data, context)
    assert outcome is StageOutcome.SUCCESS

    assert isinstance(inventory, RepositoryInventory)
    assert any(f.relative_path == "hooks.py" for f in inventory.files)
