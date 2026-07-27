"""Tests for `synthesis.pipeline` (Requirement Synthesis Engine Specification v1.1 §6, §7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.container.di import Container
from runtime.errors import PipelineDefinitionError
from runtime.lifecycle import PipelineRunState
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineEngine

from discovery.contract import DiscoveryRequest
from discovery.engine import discover_repository
from synthesis.contract import RepositoryFacts, SynthesisRequest
from synthesis.engine import synthesize_requirements
from synthesis.module import (
    CAPABILITY_ASSEMBLE_FACTS,
    CAPABILITY_EXTRACT_APIS,
    CAPABILITY_EXTRACT_COMPONENTS,
    CAPABILITY_EXTRACT_DEPENDENCIES,
    CAPABILITY_EXTRACT_HOOKS,
    CAPABILITY_IDENTIFY_MODULES,
    CAPABILITY_PARTITION_INVENTORY,
    CAPABILITY_RESOLVE_CONNECTOR,
    SynthesisModule,
)
from synthesis.pipeline import SYNTHESIS_REPOSITORY_FACTS_PIPELINE, register_synthesis_pipeline

_ALL_CAPABILITIES = (
    CAPABILITY_PARTITION_INVENTORY,
    CAPABILITY_IDENTIFY_MODULES,
    CAPABILITY_RESOLVE_CONNECTOR,
    CAPABILITY_EXTRACT_HOOKS,
    CAPABILITY_EXTRACT_COMPONENTS,
    CAPABILITY_EXTRACT_APIS,
    CAPABILITY_EXTRACT_DEPENDENCIES,
    CAPABILITY_ASSEMBLE_FACTS,
)


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="synthesis",
        display_name="Requirement Synthesis",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=_ALL_CAPABILITIES,
        entry_point="module:create",
    )


def _booted_engine() -> PipelineEngine:
    container = Container()
    module = SynthesisModule(_manifest())
    module.init(container)
    engine = PipelineEngine(container)
    register_synthesis_pipeline(engine)
    return engine


def test_synthesis_pipeline_has_the_eight_specified_stages_in_order() -> None:
    assert [stage.name for stage in SYNTHESIS_REPOSITORY_FACTS_PIPELINE.stages] == [
        "partition_inventory",
        "identify_modules",
        "resolve_connector",
        "extract_hooks",
        "extract_components",
        "extract_apis",
        "extract_dependencies",
        "assemble_facts",
    ]


def test_no_stage_declares_a_rollback_capability() -> None:
    assert all(stage.rollback_capability is None for stage in SYNTHESIS_REPOSITORY_FACTS_PIPELINE.stages)


def test_register_synthesis_pipeline_registers_it_by_name() -> None:
    engine = _booted_engine()
    assert "synthesis.repository_facts" in engine.registered_pipelines()


def test_registering_twice_raises() -> None:
    engine = _booted_engine()
    with pytest.raises(PipelineDefinitionError):
        register_synthesis_pipeline(engine)


def test_running_the_pipeline_against_a_real_inventory_completes_and_produces_facts(
    tmp_path: Path,
) -> None:
    (tmp_path / "hooks.py").write_text('app_name = "test_app"\n')
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")
    )
    request = SynthesisRequest(repository_inventory=inventory, correlation_id="corr-1", requested_by="test")
    engine = _booted_engine()

    result = engine.run("synthesis.repository_facts", initial_input=request, correlation_id="corr-1")

    assert result.state is PipelineRunState.COMPLETED
    assert result.succeeded
    assert isinstance(result.output, RepositoryFacts)
    assert [record.stage_name for record in result.stage_records] == [
        "partition_inventory",
        "identify_modules",
        "resolve_connector",
        "extract_hooks",
        "extract_components",
        "extract_apis",
        "extract_dependencies",
        "assemble_facts",
    ]
    assert any(f.key == "app_name" for f in result.output.configuration)


def test_pipeline_output_matches_the_plain_function_interface(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text('app_name = "test_app"\n')
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")
    )
    request = SynthesisRequest(repository_inventory=inventory, correlation_id="corr-1", requested_by="test")

    via_pipeline = (
        _booted_engine()
        .run("synthesis.repository_facts", initial_input=request, correlation_id="corr-1")
        .output
    )
    via_plain_function = synthesize_requirements(request)

    strip = {"facts_id": "x", "synthesized_at": "x"}
    assert via_pipeline.model_copy(update=strip) == via_plain_function.model_copy(update=strip)


def test_running_the_pipeline_against_a_stale_repository_root_fails(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text('app_name = "test_app"\n')
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")
    )
    import shutil

    shutil.rmtree(tmp_path)
    request = SynthesisRequest(repository_inventory=inventory, correlation_id="corr-1", requested_by="test")
    engine = _booted_engine()

    result = engine.run("synthesis.repository_facts", initial_input=request, correlation_id="corr-1")

    assert result.state is PipelineRunState.ROLLED_BACK
    assert not result.succeeded
