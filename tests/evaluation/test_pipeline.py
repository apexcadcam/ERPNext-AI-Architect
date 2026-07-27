"""Tests for `evaluation.pipeline` (Architecture Evaluation Engine Specification v1.0 §6, §7)."""

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
from synthesis.contract import SynthesisRequest
from synthesis.engine import synthesize_requirements

from evaluation.contract import ArchitectureEvaluation, EvaluationRequest
from evaluation.engine import evaluate_architecture
from evaluation.module import (
    CAPABILITY_ASSEMBLE_EVALUATION,
    CAPABILITY_EXECUTE_RULES,
    CAPABILITY_INDEX_FACTS,
    EvaluationModule,
)
from evaluation.pipeline import EVALUATION_ARCHITECTURE_PIPELINE, register_evaluation_pipeline

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


def _booted_engine() -> PipelineEngine:
    container = Container()
    module = EvaluationModule(_manifest())
    module.init(container)
    engine = PipelineEngine(container)
    register_evaluation_pipeline(engine)
    return engine


def _real_request(tmp_path: Path) -> EvaluationRequest:
    (tmp_path / "hooks.py").write_text('app_name = "test_app"\n')
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")
    )
    facts = synthesize_requirements(
        SynthesisRequest(repository_inventory=inventory, correlation_id="corr-1", requested_by="test")
    )
    return EvaluationRequest(repository_facts=facts, correlation_id="corr-1", requested_by="test")


def test_evaluation_architecture_pipeline_has_the_three_specified_stages_in_order() -> None:
    assert [stage.name for stage in EVALUATION_ARCHITECTURE_PIPELINE.stages] == [
        "index_facts",
        "execute_rules",
        "assemble_evaluation",
    ]


def test_no_stage_declares_a_rollback_capability() -> None:
    assert all(stage.rollback_capability is None for stage in EVALUATION_ARCHITECTURE_PIPELINE.stages)


def test_register_evaluation_pipeline_registers_it_by_name() -> None:
    engine = _booted_engine()
    assert "evaluation.architecture" in engine.registered_pipelines()


def test_registering_twice_raises() -> None:
    engine = _booted_engine()
    with pytest.raises(PipelineDefinitionError):
        register_evaluation_pipeline(engine)


def test_running_the_pipeline_against_real_facts_completes_and_produces_an_evaluation(tmp_path: Path) -> None:
    request = _real_request(tmp_path)
    engine = _booted_engine()

    result = engine.run("evaluation.architecture", initial_input=request, correlation_id="corr-1")

    assert result.state is PipelineRunState.COMPLETED
    assert result.succeeded
    assert isinstance(result.output, ArchitectureEvaluation)
    assert [record.stage_name for record in result.stage_records] == [
        "index_facts",
        "execute_rules",
        "assemble_evaluation",
    ]


def test_pipeline_output_matches_the_plain_function_interface(tmp_path: Path) -> None:
    request = _real_request(tmp_path)

    via_pipeline = (
        _booted_engine().run("evaluation.architecture", initial_input=request, correlation_id="corr-1").output
    )
    via_plain_function = evaluate_architecture(request)

    strip = {"evaluation_id": "x", "evaluated_at": "x"}
    assert via_pipeline.model_copy(update=strip) == via_plain_function.model_copy(update=strip)
