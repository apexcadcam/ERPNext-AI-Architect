"""Tests for `recommendation.contract` (Recommendation Engine Architecture Specification v1.0 §3, §4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from discovery.contract import RepositoryInventory, RepositoryMetadata, RepositoryStatistics
from evaluation.contract import (
    ArchitectureEvaluation,
    Confidence,
    EvaluationStatistics,
    Evidence,
    Finding,
    Severity,
)
from synthesis.contract import RepositoryFacts, SynthesisStatistics

from recommendation.contract import (
    CategoryImpactSpec,
    Priority,
    PriorityWeightSpec,
    Recommendation,
    RecommendationRequest,
    RecommendationSet,
    RecommendationStatistics,
    SkippedGrouping,
)


def _evidence() -> Evidence:
    return Evidence(
        fact_kind="ExtensionPointFact",
        fact_summary="override_whitelisted_method: x.y",
        relative_path="hooks.py",
    )


def _finding() -> Finding:
    return Finding(
        rule_id="EXT-001",
        rule_name="External Framework Method Override",
        category="extension_mechanisms",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        metric_value=1.0,
        explanation="1 extension point overrides an external method.",
        evidence=(_evidence(),),
        affected_files=("hooks.py",),
        affected_modules=("app",),
    )


def _evaluation() -> ArchitectureEvaluation:
    return ArchitectureEvaluation(
        evaluation_id="eval-1",
        source_facts_id="facts-1",
        repository_root="/repo",
        evaluated_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        findings=(_finding(),),
        skipped_rules=(),
        truncated=False,
        statistics=EvaluationStatistics(
            rules_evaluated=12,
            rules_skipped=0,
            findings_produced=1,
            findings_by_severity={Severity.MEDIUM: 1},
        ),
    )


def _facts_for_reference() -> RepositoryFacts:
    # Not used directly by these tests -- kept only to demonstrate the full,
    # real chain each contract type ultimately traces back to.
    inventory = RepositoryInventory(
        inventory_id="inv-1",
        repository_root="/repo",
        discovered_at="2026-07-27T10:00:00+00:00",
        correlation_id="corr-1",
        files=(),
        truncated=False,
        excluded_paths=(),
        errors=(),
        statistics=RepositoryStatistics(
            total_files=0,
            total_directories=0,
            total_size_bytes=0,
            files_by_type={},
            largest_file_size=0,
            largest_file_path=None,
        ),
        metadata=RepositoryMetadata(repository_name="repo"),
    )
    return RepositoryFacts(
        facts_id="facts-1",
        source_inventory_id=inventory.inventory_id,
        repository_root="/repo",
        synthesized_at="2026-07-27T11:00:00+00:00",
        correlation_id="corr-1",
        modules=(),
        components=(),
        apis=(),
        services=(),
        configuration=(),
        dependencies=(),
        extension_points=(),
        entry_points=(),
        unresolved=(),
        truncated=False,
        statistics=SynthesisStatistics(files_examined=0, files_skipped=0, files_failed=0, facts_extracted=0),
    )


# -- RecommendationRequest --------------------------------------------------------------------------


def test_recommendation_request_wraps_architecture_evaluation() -> None:
    request = RecommendationRequest(
        architecture_evaluation=_evaluation(), correlation_id="corr-1", requested_by="test-suite"
    )
    assert request.architecture_evaluation.evaluation_id == "eval-1"


def test_recommendation_request_is_frozen() -> None:
    request = RecommendationRequest(
        architecture_evaluation=_evaluation(), correlation_id="corr-1", requested_by="test-suite"
    )
    with pytest.raises(ValidationError):
        request.correlation_id = "other"


def test_recommendation_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(
            architecture_evaluation=_evaluation(),
            correlation_id="corr-1",
            requested_by="test-suite",
            unknown_field=1,  # type: ignore[call-arg]
        )


# -- Priority ----------------------------------------------------------------------------------------


def test_priority_defines_every_documented_value() -> None:
    assert {member.value for member in Priority} == {"low", "medium", "high", "critical"}


# -- Recommendation ------------------------------------------------------------------------------------


def _recommendation() -> Recommendation:
    return Recommendation(
        recommendation_id="rec-1",
        title="External Framework Method Override",
        category="extension_mechanisms",
        priority=Priority.HIGH,
        priority_score=18.0,
        rationale="Derived from 1 finding (EXT-001) in category 'extension_mechanisms'.",
        supporting_findings=("EXT-001",),
        evidence=(_evidence(),),
        affected_files=("hooks.py",),
        affected_modules=("app",),
    )


def test_recommendation_round_trips_through_json() -> None:
    recommendation = _recommendation()
    restored = Recommendation.model_validate_json(recommendation.model_dump_json())
    assert restored == recommendation


def test_recommendation_conflicts_with_defaults_to_empty() -> None:
    assert _recommendation().conflicts_with == ()


def test_recommendation_requires_at_least_one_supporting_finding() -> None:
    with pytest.raises(ValidationError):
        Recommendation(
            recommendation_id="rec-1",
            title="x",
            category="extension_mechanisms",
            priority=Priority.HIGH,
            priority_score=18.0,
            rationale="x",
            supporting_findings=(),
            evidence=(_evidence(),),
            affected_files=(),
            affected_modules=(),
        )


def test_recommendation_requires_at_least_one_evidence_entry() -> None:
    # "No recommendation may exist without evidence" -- schema-enforced.
    with pytest.raises(ValidationError):
        Recommendation(
            recommendation_id="rec-1",
            title="x",
            category="extension_mechanisms",
            priority=Priority.HIGH,
            priority_score=18.0,
            rationale="x",
            supporting_findings=("EXT-001",),
            evidence=(),
            affected_files=(),
            affected_modules=(),
        )


# -- SkippedGrouping --------------------------------------------------------------------------------


def test_skipped_grouping_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SkippedGrouping(category="extension_mechanisms", reason="")


# -- RecommendationStatistics ------------------------------------------------------------------------


def test_recommendation_statistics_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        RecommendationStatistics(
            findings_considered=-1,
            recommendations_produced=0,
            groupings_skipped=0,
            recommendations_by_priority={},
            conflicts_detected=0,
        )


def test_recommendation_statistics_by_priority_is_keyed_by_the_enum() -> None:
    statistics = RecommendationStatistics(
        findings_considered=1,
        recommendations_produced=1,
        groupings_skipped=0,
        recommendations_by_priority={Priority.HIGH: 1},
        conflicts_detected=0,
    )
    assert statistics.recommendations_by_priority[Priority.HIGH] == 1


# -- RecommendationSet -----------------------------------------------------------------------------


def _recommendation_set() -> RecommendationSet:
    return RecommendationSet(
        recommendation_set_id="recset-1",
        source_evaluation_id="eval-1",
        repository_root="/repo",
        generated_at="2026-07-27T13:00:00+00:00",
        correlation_id="corr-1",
        recommendations=(_recommendation(),),
        skipped_groupings=(),
        statistics=RecommendationStatistics(
            findings_considered=1,
            recommendations_produced=1,
            groupings_skipped=0,
            recommendations_by_priority={Priority.HIGH: 1},
            conflicts_detected=0,
        ),
    )


def test_recommendation_set_round_trips_through_json() -> None:
    recommendation_set = _recommendation_set()
    restored = RecommendationSet.model_validate_json(recommendation_set.model_dump_json())
    assert restored == recommendation_set


def test_recommendation_set_is_frozen() -> None:
    recommendation_set = _recommendation_set()
    with pytest.raises(ValidationError):
        recommendation_set.correlation_id = "other"


def test_recommendation_set_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RecommendationSet(  # type: ignore[call-arg]
            recommendation_set_id="recset-1",
            source_evaluation_id="eval-1",
            repository_root="/repo",
            generated_at="2026-07-27T13:00:00+00:00",
            correlation_id="corr-1",
            recommendations=(),
            skipped_groupings=(),
            statistics=RecommendationStatistics(
                findings_considered=0,
                recommendations_produced=0,
                groupings_skipped=0,
                recommendations_by_priority={},
                conflicts_detected=0,
            ),
            unexpected="field",
        )


# -- PriorityWeightSpec / CategoryImpactSpec ---------------------------------------------------------


def test_priority_weight_spec_round_trips_through_json() -> None:
    spec = PriorityWeightSpec(
        weight_name="severity", value=3.0, calibration_status="heuristic_default", justification="x"
    )
    restored = PriorityWeightSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec


def test_priority_weight_spec_requires_justification() -> None:
    with pytest.raises(ValidationError):
        PriorityWeightSpec(
            weight_name="severity", value=3.0, calibration_status="heuristic_default", justification=""
        )


def test_category_impact_spec_round_trips_through_json() -> None:
    spec = CategoryImpactSpec(
        category="modularity", impact_weight=3.0, calibration_status="heuristic_default", justification="x"
    )
    restored = CategoryImpactSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
