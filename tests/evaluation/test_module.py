"""Tests for `evaluation.module` (Architecture Evaluation Engine Specification v1.0 §2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, StageOutcome

from discovery.contract import DiscoveryRequest
from discovery.engine import discover_repository
from synthesis.contract import SynthesisRequest
from synthesis.engine import synthesize_requirements

from evaluation.contract import ArchitectureEvaluation, EvaluationRequest
from evaluation.module import (
    CAPABILITY_ASSEMBLE_EVALUATION,
    CAPABILITY_EXECUTE_RULES,
    CAPABILITY_INDEX_FACTS,
    EvaluationModule,
)

_ALL_CAPABILITIES = (CAPABILITY_INDEX_FACTS, CAPABILITY_EXECUTE_RULES, CAPABILITY_ASSEMBLE_EVALUATION)


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="evaluation",
        display_name="Architecture Evaluation",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=_ALL_CAPABILITIES,
        entry_point="module:create",
    )


def _context() -> PipelineContext:
    return PipelineContext(
        pipeline_run_id="run-1",
        correlation_id="corr-1",
        pipeline_name="evaluation.architecture",
        started_at=datetime.now(UTC),
    )


def test_evaluation_module_is_a_module() -> None:
    assert isinstance(EvaluationModule(_manifest()), Module)


def test_health_check_is_healthy_before_init() -> None:
    assert EvaluationModule(_manifest()).health_check().healthy is True


def test_health_check_is_healthy_after_init() -> None:
    module = EvaluationModule(_manifest())
    module.init(Container())
    assert module.health_check().healthy is True


def test_manifest_requires_no_capabilities() -> None:
    assert _manifest().capabilities_required == ()


def test_init_registers_all_three_stage_capabilities() -> None:
    module = EvaluationModule(_manifest())
    container = Container()

    module.init(container)

    for capability in _ALL_CAPABILITIES:
        assert container.is_registered(capability)


def test_init_calls_no_container_resolve() -> None:
    module = EvaluationModule(_manifest())

    module.init(Container())


def test_full_three_stage_sequence_produces_an_architecture_evaluation(tmp_path: Path) -> None:
    (tmp_path / "hooks.py").write_text('app_name = "test_app"\n')
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    facts = synthesize_requirements(
        SynthesisRequest(repository_inventory=inventory, correlation_id="c", requested_by="r")
    )
    request = EvaluationRequest(repository_facts=facts, correlation_id="corr-1", requested_by="test")

    module = EvaluationModule(_manifest())
    container = Container()
    module.init(container)
    context = _context()

    data, outcome = container.resolve(CAPABILITY_INDEX_FACTS)(request, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_EXECUTE_RULES)(data, context)
    assert outcome is StageOutcome.SUCCESS
    evaluation, outcome = container.resolve(CAPABILITY_ASSEMBLE_EVALUATION)(data, context)
    assert outcome is StageOutcome.SUCCESS

    assert isinstance(evaluation, ArchitectureEvaluation)
    assert evaluation.source_facts_id == facts.facts_id
