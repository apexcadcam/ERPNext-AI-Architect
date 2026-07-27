"""Tests for `discovery.pipeline` (Repository Discovery Engine Specification v1.1 §5, §7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.container.di import Container
from runtime.errors import PipelineDefinitionError
from runtime.lifecycle import PipelineRunState
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineEngine

from discovery.contract import DiscoveryRequest, RepositoryInventory
from discovery.engine import discover_repository
from discovery.module import (
    CAPABILITY_ASSEMBLE_INVENTORY,
    CAPABILITY_CLASSIFY_ENTRIES,
    CAPABILITY_RESOLVE_ROOT,
    CAPABILITY_WALK_TREE,
    DiscoveryModule,
)
from discovery.pipeline import DISCOVERY_REPOSITORY_PIPELINE, register_discovery_pipeline


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


def _booted_engine() -> PipelineEngine:
    container = Container()
    module = DiscoveryModule(_manifest())
    module.init(container)
    engine = PipelineEngine(container)
    register_discovery_pipeline(engine)
    return engine


def test_discovery_repository_pipeline_has_the_four_specified_stages_in_order() -> None:
    assert [stage.name for stage in DISCOVERY_REPOSITORY_PIPELINE.stages] == [
        "resolve_root",
        "walk_tree",
        "classify_entries",
        "assemble_inventory",
    ]


def test_no_stage_declares_a_rollback_capability() -> None:
    # §6 "Recovery behavior": every stage is read-only, deliberately.
    assert all(stage.rollback_capability is None for stage in DISCOVERY_REPOSITORY_PIPELINE.stages)


def test_register_discovery_pipeline_registers_it_by_name() -> None:
    engine = _booted_engine()
    assert "discovery.repository" in engine.registered_pipelines()


def test_registering_twice_raises() -> None:
    engine = _booted_engine()
    with pytest.raises(PipelineDefinitionError):
        register_discovery_pipeline(engine)


def test_running_the_pipeline_against_a_real_tree_completes_and_produces_an_inventory(
    tmp_path: Path,
) -> None:
    (tmp_path / "hooks.py").write_text("# hook\n")
    engine = _booted_engine()
    request = DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")

    result = engine.run("discovery.repository", initial_input=request, correlation_id="corr-1")

    assert result.state is PipelineRunState.COMPLETED
    assert result.succeeded
    assert isinstance(result.output, RepositoryInventory)
    assert [record.stage_name for record in result.stage_records] == [
        "resolve_root",
        "walk_tree",
        "classify_entries",
        "assemble_inventory",
    ]
    assert any(f.relative_path == "hooks.py" for f in result.output.files)


def test_pipeline_output_matches_the_plain_function_interface(tmp_path: Path) -> None:
    # Proves the two public interfaces (§2) never diverge -- both compose
    # the exact same package-internal stage functions.
    (tmp_path / "hooks.py").write_text("# hook\n")
    (tmp_path / "a.py").write_text("x" * 5)
    request = DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")

    via_pipeline = (
        _booted_engine().run("discovery.repository", initial_input=request, correlation_id="corr-1").output
    )
    via_plain_function = discover_repository(request)

    strip = {"inventory_id": "x", "discovered_at": "x"}
    assert via_pipeline.model_copy(update=strip) == via_plain_function.model_copy(update=strip)


def test_running_the_pipeline_against_a_missing_root_fails(tmp_path: Path) -> None:
    engine = _booted_engine()
    request = DiscoveryRequest(
        repository_root=str(tmp_path / "missing"), correlation_id="corr-1", requested_by="test"
    )

    result = engine.run("discovery.repository", initial_input=request, correlation_id="corr-1")

    assert result.state is PipelineRunState.ROLLED_BACK
    assert not result.succeeded
