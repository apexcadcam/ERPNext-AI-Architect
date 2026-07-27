"""Tests for `evaluation.contract` (Architecture Evaluation Engine Specification v1.0 §2, §3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from discovery.contract import RepositoryInventory, RepositoryMetadata, RepositoryStatistics
from evaluation.contract import (
    ArchitectureEvaluation,
    Confidence,
    EvaluationRequest,
    EvaluationStatistics,
    Evidence,
    Finding,
    RuleThresholdSpec,
    Severity,
    SkippedRule,
)
from synthesis.contract import RepositoryFacts, SynthesisStatistics


def _facts() -> RepositoryFacts:
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


def _evidence() -> Evidence:
    return Evidence(fact_kind="ModuleFact", fact_summary="frappe_app: test_app", relative_path="test_app")


# -- EvaluationRequest ------------------------------------------------------------------------------


def test_evaluation_request_wraps_repository_facts() -> None:
    request = EvaluationRequest(repository_facts=_facts(), correlation_id="corr-1", requested_by="test-suite")
    assert request.repository_facts.facts_id == "facts-1"


def test_evaluation_request_applies_documented_defaults() -> None:
    request = EvaluationRequest(repository_facts=_facts(), correlation_id="corr-1", requested_by="test-suite")
    assert request.max_findings == 100
    assert request.timeout_seconds == 30.0


def test_evaluation_request_is_frozen() -> None:
    request = EvaluationRequest(repository_facts=_facts(), correlation_id="corr-1", requested_by="test-suite")
    with pytest.raises(ValidationError):
        request.correlation_id = "other"


def test_evaluation_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvaluationRequest(
            repository_facts=_facts(),
            correlation_id="corr-1",
            requested_by="test-suite",
            unknown_field=1,  # type: ignore[call-arg]
        )


# -- Severity / Confidence --------------------------------------------------------------------------


def test_severity_defines_every_documented_value() -> None:
    assert {member.value for member in Severity} == {"info", "low", "medium", "high", "critical"}


def test_confidence_defines_every_documented_value() -> None:
    assert {member.value for member in Confidence} == {"low", "medium", "high"}


# -- Evidence ----------------------------------------------------------------------------------------


def test_evidence_round_trips_through_json() -> None:
    evidence = _evidence()
    restored = Evidence.model_validate_json(evidence.model_dump_json())
    assert restored == evidence


# -- Finding -------------------------------------------------------------------------------------------


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
        affected_files=("test_app/hooks.py",),
        affected_modules=("test_app",),
    )


def test_finding_round_trips_through_json() -> None:
    finding = _finding()
    restored = Finding.model_validate_json(finding.model_dump_json())
    assert restored == finding


def test_finding_requires_at_least_one_evidence_entry() -> None:
    # "No finding may exist without traceable evidence" -- enforced by the
    # schema itself, not merely by convention.
    with pytest.raises(ValidationError):
        Finding(
            rule_id="EXT-001",
            rule_name="External Framework Method Override",
            category="extension_mechanisms",
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            metric_value=1.0,
            explanation="x",
            evidence=(),
            affected_files=(),
            affected_modules=(),
        )


# -- SkippedRule -----------------------------------------------------------------------------------


def test_skipped_rule_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SkippedRule(rule_id="EXT-001", reason="")


# -- EvaluationStatistics --------------------------------------------------------------------------


def test_evaluation_statistics_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        EvaluationStatistics(
            rules_evaluated=-1, rules_skipped=0, findings_produced=0, findings_by_severity={}
        )


def test_evaluation_statistics_findings_by_severity_is_keyed_by_the_enum() -> None:
    statistics = EvaluationStatistics(
        rules_evaluated=12, rules_skipped=0, findings_produced=1, findings_by_severity={Severity.MEDIUM: 1}
    )
    assert statistics.findings_by_severity[Severity.MEDIUM] == 1


# -- ArchitectureEvaluation ------------------------------------------------------------------------


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


def test_architecture_evaluation_round_trips_through_json() -> None:
    evaluation = _evaluation()
    restored = ArchitectureEvaluation.model_validate_json(evaluation.model_dump_json())
    assert restored == evaluation


def test_architecture_evaluation_is_frozen() -> None:
    evaluation = _evaluation()
    with pytest.raises(ValidationError):
        evaluation.truncated = True


def test_architecture_evaluation_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ArchitectureEvaluation(  # type: ignore[call-arg]
            evaluation_id="eval-1",
            source_facts_id="facts-1",
            repository_root="/repo",
            evaluated_at="2026-07-27T12:00:00+00:00",
            correlation_id="corr-1",
            findings=(),
            skipped_rules=(),
            truncated=False,
            statistics=EvaluationStatistics(
                rules_evaluated=0, rules_skipped=0, findings_produced=0, findings_by_severity={}
            ),
            unexpected="field",
        )


# -- RuleThresholdSpec ------------------------------------------------------------------------------


def test_rule_threshold_spec_round_trips_through_json() -> None:
    spec = RuleThresholdSpec(
        rule_id="MOD-002",
        threshold_name="share_medium",
        value=0.8,
        calibration_status="heuristic_default",
        justification="80/20-style dominant-partition heuristic; not measured against real data.",
    )
    restored = RuleThresholdSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec


def test_rule_threshold_spec_requires_a_justification() -> None:
    with pytest.raises(ValidationError):
        RuleThresholdSpec(
            rule_id="MOD-002",
            threshold_name="share_medium",
            value=0.8,
            calibration_status="heuristic_default",
            justification="",
        )
