"""Recommendation Engine's own stage logic.

Implements Recommendation Engine Architecture Specification v1.0 §11
exactly: three stages, composing `recommendation.scoring`'s own grouping,
scoring, template, and conflict-detection functions. Zero Reasoning
Engine calls, zero filesystem access.

`build_recommendations`, `assemble_recommendation_set`, and
`generate_recommendations` are package-internal-shared, used identically
by `recommendation.module`'s own Container-registered stage wrappers — no
duplicated stage logic between the plain-function interface and the
Pipeline-Engine-driven one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from evaluation.contract import Finding

from recommendation.contract import (
    Priority,
    Recommendation,
    RecommendationRequest,
    RecommendationSet,
    RecommendationStatistics,
    SkippedGrouping,
)
from recommendation.scoring import (
    detect_conflicts,
    group_findings,
    rationale_for,
    score_group,
    title_for,
    union_affected_files,
    union_affected_modules,
    union_evidence,
)

# -- Stage 2: build one Recommendation per finding group -----------------------------------------------


def _build_recommendation(group: tuple[Finding, ...]) -> Recommendation:
    affected_files = union_affected_files(group)
    affected_modules = union_affected_modules(group)
    evidence = union_evidence(group)
    breakdown, priority = score_group(group, affected_files)

    return Recommendation(
        recommendation_id=str(uuid.uuid4()),
        title=title_for(group),
        category=group[0].category,
        priority=priority,
        priority_score=breakdown.total,
        rationale=rationale_for(group, priority, breakdown, affected_files, affected_modules),
        supporting_findings=tuple(finding.rule_id for finding in group),
        evidence=evidence,
        affected_files=affected_files,
        affected_modules=affected_modules,
    )


def build_recommendations(groups: list[tuple[Finding, ...]]) -> tuple[Recommendation, ...]:
    return tuple(_build_recommendation(group) for group in groups)


# -- Stage 3: conflict detection + assembly -------------------------------------------------------------


def _count_conflict_pairs(recommendations: tuple[Recommendation, ...]) -> int:
    pairs: set[frozenset[str]] = set()
    for recommendation in recommendations:
        for other_id in recommendation.conflicts_with:
            pairs.add(frozenset((recommendation.recommendation_id, other_id)))
    return len(pairs)


def assemble_recommendation_set(
    request: RecommendationRequest,
    recommendations: tuple[Recommendation, ...],
    skipped_groupings: tuple[SkippedGrouping, ...],
) -> RecommendationSet:
    recommendations = detect_conflicts(recommendations)

    by_priority: dict[Priority, int] = {}
    for recommendation in recommendations:
        by_priority[recommendation.priority] = by_priority.get(recommendation.priority, 0) + 1

    statistics = RecommendationStatistics(
        findings_considered=len(request.architecture_evaluation.findings),
        recommendations_produced=len(recommendations),
        groupings_skipped=len(skipped_groupings),
        recommendations_by_priority=by_priority,
        conflicts_detected=_count_conflict_pairs(recommendations),
    )
    return RecommendationSet(
        recommendation_set_id=str(uuid.uuid4()),
        source_evaluation_id=request.architecture_evaluation.evaluation_id,
        repository_root=request.architecture_evaluation.repository_root,
        generated_at=datetime.now(UTC).isoformat(),
        correlation_id=request.correlation_id,
        recommendations=recommendations,
        skipped_groupings=skipped_groupings,
        statistics=statistics,
    )


# -- §3's public interface: the plain-function composition of all three stages -------------------------


def generate_recommendations(request: RecommendationRequest) -> RecommendationSet:
    """The single, plain-function composition of all three stages — §3's
    first interface: no Container, no Module, no Pipeline Engine required.
    """

    findings = request.architecture_evaluation.findings
    groups, skipped_groupings = group_findings(findings)
    recommendations = build_recommendations(groups)
    return assemble_recommendation_set(request, recommendations, skipped_groupings)
