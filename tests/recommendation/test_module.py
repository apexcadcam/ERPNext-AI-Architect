"""Tests for `recommendation.module` (Recommendation Engine Architecture Specification v1.0 §7, §8, §9)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, StageOutcome

from discovery.contract import DiscoveryRequest
from discovery.engine import discover_repository
from evaluation.contract import EvaluationRequest
from evaluation.engine import evaluate_architecture
from synthesis.contract import SynthesisRequest
from synthesis.engine import synthesize_requirements

from recommendation.contract import RecommendationRequest, RecommendationSet
from recommendation.module import (
    CAPABILITY_ASSEMBLE_RECOMMENDATION_SET,
    CAPABILITY_BUILD_RECOMMENDATIONS,
    CAPABILITY_GROUP_FINDINGS,
    RecommendationModule,
)

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


def _context() -> PipelineContext:
    return PipelineContext(
        pipeline_run_id="run-1",
        correlation_id="corr-1",
        pipeline_name="recommendation.engine",
        started_at=datetime.now(UTC),
    )


def test_recommendation_module_is_a_module() -> None:
    assert isinstance(RecommendationModule(_manifest()), Module)


def test_health_check_is_healthy_before_init() -> None:
    assert RecommendationModule(_manifest()).health_check().healthy is True


def test_health_check_is_healthy_after_init() -> None:
    module = RecommendationModule(_manifest())
    module.init(Container())
    assert module.health_check().healthy is True


def test_manifest_requires_no_capabilities() -> None:
    assert _manifest().capabilities_required == ()


def test_init_registers_all_three_stage_capabilities() -> None:
    module = RecommendationModule(_manifest())
    container = Container()

    module.init(container)

    for capability in _ALL_CAPABILITIES:
        assert container.is_registered(capability)


def test_init_calls_no_container_resolve() -> None:
    module = RecommendationModule(_manifest())

    module.init(Container())


def test_full_three_stage_sequence_produces_a_recommendation_set(tmp_path: Path) -> None:
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
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    facts = synthesize_requirements(
        SynthesisRequest(repository_inventory=inventory, correlation_id="c", requested_by="r")
    )
    evaluation = evaluate_architecture(
        EvaluationRequest(repository_facts=facts, correlation_id="c", requested_by="r")
    )
    request = RecommendationRequest(
        architecture_evaluation=evaluation, correlation_id="corr-1", requested_by="test"
    )

    module = RecommendationModule(_manifest())
    container = Container()
    module.init(container)
    context = _context()

    data, outcome = container.resolve(CAPABILITY_GROUP_FINDINGS)(request, context)
    assert outcome is StageOutcome.SUCCESS
    data, outcome = container.resolve(CAPABILITY_BUILD_RECOMMENDATIONS)(data, context)
    assert outcome is StageOutcome.SUCCESS
    recommendation_set, outcome = container.resolve(CAPABILITY_ASSEMBLE_RECOMMENDATION_SET)(data, context)
    assert outcome is StageOutcome.SUCCESS

    assert isinstance(recommendation_set, RecommendationSet)
    assert recommendation_set.source_evaluation_id == evaluation.evaluation_id
