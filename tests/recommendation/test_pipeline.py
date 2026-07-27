"""Tests for `recommendation.pipeline` (Recommendation Engine Architecture Specification v1.0 §7, §8, §9)."""

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
from evaluation.contract import EvaluationRequest
from evaluation.engine import evaluate_architecture
from synthesis.contract import SynthesisRequest
from synthesis.engine import synthesize_requirements

from recommendation.contract import RecommendationRequest, RecommendationSet
from recommendation.engine import generate_recommendations
from recommendation.module import (
    CAPABILITY_ASSEMBLE_RECOMMENDATION_SET,
    CAPABILITY_BUILD_RECOMMENDATIONS,
    CAPABILITY_GROUP_FINDINGS,
    RecommendationModule,
)
from recommendation.pipeline import RECOMMENDATION_ENGINE_PIPELINE, register_recommendation_pipeline

_ALL_CAPABILITIES = (
    CAPABILITY_GROUP_FINDINGS,
    CAPABILITY_BUILD_RECOMMENDATIONS,
    CAPABILITY_ASSEMBLE_RECOMMENDATION_SET,
)


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="recommendation",
        display_name="Recommendation Engine",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=_ALL_CAPABILITIES,
        entry_point="module:create",
    )


def _booted_engine() -> PipelineEngine:
    container = Container()
    module = RecommendationModule(_manifest())
    module.init(container)
    engine = PipelineEngine(container)
    register_recommendation_pipeline(engine)
    return engine


def _real_request(tmp_path: Path) -> RecommendationRequest:
    app = tmp_path / "apex_dashboard"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "hooks.py").write_text(
        'app_name = "apex_dashboard"\n'
        "override_whitelisted_methods = {\n"
        '    "frappe.desk.desktop.get_desktop_page": "apex_dashboard.overrides.x",\n'
        "}\n"
    )
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="corr-1", requested_by="test")
    )
    facts = synthesize_requirements(
        SynthesisRequest(repository_inventory=inventory, correlation_id="corr-1", requested_by="test")
    )
    evaluation = evaluate_architecture(
        EvaluationRequest(repository_facts=facts, correlation_id="corr-1", requested_by="test")
    )
    return RecommendationRequest(
        architecture_evaluation=evaluation, correlation_id="corr-1", requested_by="test"
    )


def test_recommendation_engine_pipeline_has_the_three_specified_stages_in_order() -> None:
    assert [stage.name for stage in RECOMMENDATION_ENGINE_PIPELINE.stages] == [
        "group_findings",
        "build_recommendations",
        "assemble_recommendation_set",
    ]


def test_no_stage_declares_a_rollback_capability() -> None:
    assert all(stage.rollback_capability is None for stage in RECOMMENDATION_ENGINE_PIPELINE.stages)


def test_register_recommendation_pipeline_registers_it_by_name() -> None:
    engine = _booted_engine()
    assert "recommendation.engine" in engine.registered_pipelines()


def test_registering_twice_raises() -> None:
    engine = _booted_engine()
    with pytest.raises(PipelineDefinitionError):
        register_recommendation_pipeline(engine)


def test_running_the_pipeline_against_real_evaluation_completes_and_produces_a_recommendation_set(
    tmp_path: Path,
) -> None:
    request = _real_request(tmp_path)
    engine = _booted_engine()

    result = engine.run("recommendation.engine", initial_input=request, correlation_id="corr-1")

    assert result.state is PipelineRunState.COMPLETED
    assert result.succeeded
    assert isinstance(result.output, RecommendationSet)
    assert [record.stage_name for record in result.stage_records] == [
        "group_findings",
        "build_recommendations",
        "assemble_recommendation_set",
    ]


def test_pipeline_output_matches_the_plain_function_interface(tmp_path: Path) -> None:
    request = _real_request(tmp_path)

    via_pipeline = (
        _booted_engine().run("recommendation.engine", initial_input=request, correlation_id="corr-1").output
    )
    via_plain_function = generate_recommendations(request)

    strip_set = {"recommendation_set_id": "x", "generated_at": "x"}
    strip_rec = {"recommendation_id": "x"}
    pipeline_normalized = via_pipeline.model_copy(
        update={
            **strip_set,
            "recommendations": tuple(r.model_copy(update=strip_rec) for r in via_pipeline.recommendations),
        }
    )
    plain_normalized = via_plain_function.model_copy(
        update={
            **strip_set,
            "recommendations": tuple(
                r.model_copy(update=strip_rec) for r in via_plain_function.recommendations
            ),
        }
    )
    assert pipeline_normalized == plain_normalized
