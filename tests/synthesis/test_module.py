"""Tests for `synthesis.module` (Requirement Synthesis Engine Specification v1.1 §2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, StageOutcome

from discovery.contract import DiscoveryRequest
from discovery.engine import discover_repository
from synthesis.contract import RepositoryFacts, SynthesisRequest
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


def _context() -> PipelineContext:
    return PipelineContext(
        pipeline_run_id="run-1",
        correlation_id="corr-1",
        pipeline_name="synthesis.repository_facts",
        started_at=datetime.now(UTC),
    )


def test_synthesis_module_is_a_module() -> None:
    assert isinstance(SynthesisModule(_manifest()), Module)


def test_health_check_is_healthy_before_init() -> None:
    assert SynthesisModule(_manifest()).health_check().healthy is True


def test_health_check_is_healthy_after_init() -> None:
    module = SynthesisModule(_manifest())
    module.init(Container())
    assert module.health_check().healthy is True


def test_manifest_requires_no_capabilities() -> None:
    assert _manifest().capabilities_required == ()


def test_init_registers_all_eight_stage_capabilities() -> None:
    module = SynthesisModule(_manifest())
    container = Container()

    module.init(container)

    for capability in _ALL_CAPABILITIES:
        assert container.is_registered(capability)


def test_init_calls_no_container_resolve() -> None:
    # A completely empty Container has nothing registered -- if init() ever
    # called container.resolve(...) on anything, that call would raise
    # CapabilityResolutionError immediately.
    module = SynthesisModule(_manifest())

    module.init(Container())


def test_full_eight_stage_sequence_produces_repository_facts(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text('app_name = "test_app"\n')
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    request = SynthesisRequest(repository_inventory=inventory, correlation_id="corr-1", requested_by="test")

    module = SynthesisModule(_manifest())
    container = Container()
    module.init(container)
    context = _context()

    data, outcome = container.resolve(CAPABILITY_PARTITION_INVENTORY)(request, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_IDENTIFY_MODULES)(data, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_RESOLVE_CONNECTOR)(data, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_EXTRACT_HOOKS)(data, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_EXTRACT_COMPONENTS)(data, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_EXTRACT_APIS)(data, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_EXTRACT_DEPENDENCIES)(data, context)
    assert outcome is StageOutcome.SUCCESS
    facts, outcome = container.resolve(CAPABILITY_ASSEMBLE_FACTS)(data, context)
    assert outcome is StageOutcome.SUCCESS

    assert isinstance(facts, RepositoryFacts)
    assert any(f.key == "app_name" for f in facts.configuration)
