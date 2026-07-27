"""Tests for `recommendation.engine` (Recommendation Engine Architecture
Specification v1.0 §3, §7, §8, §9).
"""

from __future__ import annotations

from pathlib import Path

from discovery.contract import DiscoveryRequest
from discovery.engine import discover_repository
from evaluation.contract import ArchitectureEvaluation, EvaluationRequest, EvaluationStatistics
from evaluation.engine import evaluate_architecture
from synthesis.contract import SynthesisRequest
from synthesis.engine import synthesize_requirements

import pytest

from recommendation.contract import Priority, Recommendation, RecommendationRequest
from recommendation.engine import assemble_recommendation_set, build_recommendations, generate_recommendations

# -- Fixture -- a real Frappe-app-shaped tree, chained through all four real engines --------------------

_HOOKS_PY = """
app_name = "apex_dashboard"
scheduler_events = {
    "daily": ["apex_dashboard.tasks.clear_cache"],
}
override_whitelisted_methods = {
    "frappe.desk.desktop.get_desktop_page": "apex_dashboard.overrides.get_desktop_page_override",
}
"""

_OVERRIDES_PY = """
import frappe


@frappe.whitelist()
@frappe.read_only()
def get_desktop_page_override(page):
    return {}
"""


def _build_apex_dashboard_like_app(root: Path) -> None:
    app = root / "apex_dashboard"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "hooks.py").write_text(_HOOKS_PY)
    (app / "overrides.py").write_text(_OVERRIDES_PY)


def _real_architecture_evaluation(root: Path) -> ArchitectureEvaluation:
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(root), correlation_id="c", requested_by="r")
    )
    facts = synthesize_requirements(
        SynthesisRequest(repository_inventory=inventory, correlation_id="c", requested_by="r")
    )
    return evaluate_architecture(
        EvaluationRequest(repository_facts=facts, correlation_id="c", requested_by="r")
    )


def _empty_architecture_evaluation() -> ArchitectureEvaluation:
    return ArchitectureEvaluation(
        evaluation_id="eval-empty",
        source_facts_id="facts-empty",
        repository_root="/repo",
        evaluated_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        findings=(),
        skipped_rules=(),
        truncated=False,
        statistics=EvaluationStatistics(
            rules_evaluated=12, rules_skipped=0, findings_produced=0, findings_by_severity={}
        ),
    )


# -- end to end, through the real Discovery -> Synthesis -> Evaluation -> Recommendation chain ----------


def test_generate_recommendations_end_to_end_through_the_real_engine_chain(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    evaluation = _real_architecture_evaluation(tmp_path)
    request = RecommendationRequest(
        architecture_evaluation=evaluation, correlation_id="corr-1", requested_by="test-suite"
    )

    recommendation_set = generate_recommendations(request)

    assert recommendation_set.source_evaluation_id == evaluation.evaluation_id
    assert recommendation_set.repository_root == evaluation.repository_root
    assert recommendation_set.statistics.findings_considered == len(evaluation.findings)
    assert recommendation_set.statistics.recommendations_produced == len(recommendation_set.recommendations)

    ext_recommendation = next(
        r for r in recommendation_set.recommendations if "EXT-001" in r.supporting_findings
    )
    assert ext_recommendation.category == "extension_mechanisms"
    assert "apex_dashboard" in ext_recommendation.affected_modules
    # A single-finding, MEDIUM-severity group can never exceed HIGH (the ceiling for MEDIUM).
    assert ext_recommendation.priority in (Priority.LOW, Priority.MEDIUM, Priority.HIGH)


def test_generate_recommendations_traces_every_recommendation_back_to_real_findings(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    evaluation = _real_architecture_evaluation(tmp_path)
    request = RecommendationRequest(
        architecture_evaluation=evaluation, correlation_id="corr-1", requested_by="test-suite"
    )

    recommendation_set = generate_recommendations(request)

    all_rule_ids = {finding.rule_id for finding in evaluation.findings}
    for recommendation in recommendation_set.recommendations:
        assert set(recommendation.supporting_findings) <= all_rule_ids
        assert recommendation.evidence  # schema already enforces this, re-asserted for clarity


# -- Determinism ------------------------------------------------------------------------------------


def test_generate_recommendations_is_deterministic_across_repeated_runs(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    evaluation = _real_architecture_evaluation(tmp_path)
    request = RecommendationRequest(
        architecture_evaluation=evaluation, correlation_id="corr-1", requested_by="test-suite"
    )

    first = generate_recommendations(request)
    second = generate_recommendations(request)

    strip_set = {"recommendation_set_id": "x", "generated_at": "x"}
    strip_rec = {"recommendation_id": "x"}
    first_normalized = first.model_copy(
        update={
            **strip_set,
            "recommendations": tuple(r.model_copy(update=strip_rec) for r in first.recommendations),
        }
    )
    second_normalized = second.model_copy(
        update={
            **strip_set,
            "recommendations": tuple(r.model_copy(update=strip_rec) for r in second.recommendations),
        }
    )
    assert first_normalized == second_normalized


# -- Empty input (real Express-repo-shaped observation from the Production Validation Report) ----------


def test_generate_recommendations_on_zero_findings_produces_a_valid_empty_recommendation_set() -> None:
    request = RecommendationRequest(
        architecture_evaluation=_empty_architecture_evaluation(),
        correlation_id="corr-1",
        requested_by="test-suite",
    )

    recommendation_set = generate_recommendations(request)

    assert recommendation_set.recommendations == ()
    assert recommendation_set.skipped_groupings == ()
    assert recommendation_set.statistics.findings_considered == 0
    assert recommendation_set.statistics.recommendations_produced == 0
    assert recommendation_set.statistics.conflicts_detected == 0
    assert recommendation_set.statistics.recommendations_by_priority == {}


# -- build_recommendations / assemble_recommendation_set (stage-level) ----------------------------------


def test_build_recommendations_returns_empty_tuple_for_no_groups() -> None:
    assert build_recommendations([]) == ()


def test_assemble_recommendation_set_counts_recommendations_by_priority(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    evaluation = _real_architecture_evaluation(tmp_path)
    request = RecommendationRequest(
        architecture_evaluation=evaluation, correlation_id="corr-1", requested_by="test-suite"
    )
    from recommendation.scoring import group_findings

    groups, skipped = group_findings(evaluation.findings)
    recommendations = build_recommendations(groups)

    recommendation_set = assemble_recommendation_set(request, recommendations, skipped)

    total_by_priority = sum(recommendation_set.statistics.recommendations_by_priority.values())
    assert total_by_priority == recommendation_set.statistics.recommendations_produced


def test_assemble_recommendation_set_counts_conflicts_as_unique_pairs_not_per_side(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Three mutually conflicting recommendations produce 3 unique pairs, not
    # 3 "recommendations with a conflict" (which `_count_conflict_pairs`
    # must not conflate).
    import recommendation.scoring as scoring_module

    monkeypatch.setattr(
        scoring_module,
        "OPPOSING_CATEGORY_PAIRS",
        (("modularity", "cohesion"), ("modularity", "extension_mechanisms")),
    )

    from evaluation.contract import Evidence

    evidence = (Evidence(fact_kind="ModuleFact", fact_summary="s", relative_path="a.py"),)

    def _recommendation(rec_id: str, category: str) -> Recommendation:
        return Recommendation(
            recommendation_id=rec_id,
            title=rec_id,
            category=category,
            priority=Priority.HIGH,
            priority_score=18.0,
            rationale="x",
            supporting_findings=("MOD-001",),
            evidence=evidence,
            affected_files=(),
            affected_modules=(),
        )

    _build_apex_dashboard_like_app(tmp_path)
    evaluation = _real_architecture_evaluation(tmp_path)
    request = RecommendationRequest(
        architecture_evaluation=evaluation, correlation_id="corr-1", requested_by="test-suite"
    )

    recommendations = (
        _recommendation("rec-a", "modularity"),
        _recommendation("rec-b", "cohesion"),
        _recommendation("rec-c", "extension_mechanisms"),
    )
    recommendation_set = assemble_recommendation_set(request, recommendations, skipped_groupings=())

    # rec-a conflicts with both rec-b and rec-c: 2 unique pairs total.
    assert recommendation_set.statistics.conflicts_detected == 2
