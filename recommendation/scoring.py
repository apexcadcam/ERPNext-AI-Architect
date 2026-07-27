"""Recommendation Engine's own grouping, scoring, and conflict-detection
logic.

Implements Recommendation Engine Architecture Specification v1.0 §6, §7,
§8, and §9 in full. Zero Reasoning Engine calls: every input here
(`Severity`, `Confidence`, `category`, file/module counts) is already a
closed-vocabulary or countable value by the time it reaches this module —
turning already-evidence-backed findings into a prioritized, grouped list
is aggregation and arithmetic, not judgment (§10 of the specification).

**A design correction made during implementation, not after shipping it:**
an early version of the scoring formula let `affected_files` count alone
push an `INFO`-severity finding (e.g. FWK-001 on a repository with many
identified Python packages) to a `HIGH` priority score, purely from
volume — precisely the "fine-grained module count dilutes a ratio"
failure mode the Production Validation Report already found in
Evaluation's own API-001. `_SEVERITY_PRIORITY_CEILING` exists specifically
to make this structurally impossible: no `Priority` may ever exceed the
ceiling its own group's worst-case `Severity` allows, regardless of how
scope or category impact would otherwise inflate the raw score.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.contract import Confidence, Evidence, Finding, Severity

from recommendation.contract import (
    CategoryImpactSpec,
    Priority,
    PriorityWeightSpec,
    Recommendation,
    SkippedGrouping,
)

# -- Ordering tables -- reused directly as scoring weights where the enum ordinal IS the weight ------

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}
_CONFIDENCE_ORDER: dict[Confidence, int] = {
    Confidence.LOW: 1,
    Confidence.MEDIUM: 2,
    Confidence.HIGH: 3,
}
_PRIORITY_ORDER: dict[Priority, int] = {
    Priority.LOW: 0,
    Priority.MEDIUM: 1,
    Priority.HIGH: 2,
    Priority.CRITICAL: 3,
}

#: §6's severity ceiling -- see this module's own docstring for why it exists.
_SEVERITY_PRIORITY_CEILING: dict[Severity, Priority] = {
    Severity.INFO: Priority.MEDIUM,
    Severity.LOW: Priority.MEDIUM,
    Severity.MEDIUM: Priority.HIGH,
    Severity.HIGH: Priority.CRITICAL,
    Severity.CRITICAL: Priority.CRITICAL,
}

# -- Rule Metadata Registry -- Threshold Documentation & Rule Metadata Addendum's own pattern, reused --

PRIORITY_WEIGHTS: tuple[PriorityWeightSpec, ...] = (
    PriorityWeightSpec(
        weight_name="severity",
        value=3.0,
        calibration_status="heuristic_default",
        justification="No production RecommendationSet data exists yet -- every weight in this "
        "registry is a placeholder, disclosed as such (Architecture Specification v1.0 §6).",
    ),
    PriorityWeightSpec(
        weight_name="confidence",
        value=2.0,
        calibration_status="heuristic_default",
        justification="Weighted below severity -- confidence should influence but not dominate ordering.",
    ),
    PriorityWeightSpec(
        weight_name="scope",
        value=1.0,
        calibration_status="heuristic_default",
        justification="Deliberately the smallest per-unit weight, combined with scope_cap, so file-count "
        "volume alone cannot dominate a score the way it would have without the severity ceiling.",
    ),
    PriorityWeightSpec(
        weight_name="scope_cap",
        value=10.0,
        calibration_status="heuristic_default",
        justification="Caps affected_files' contribution so one large-footprint finding cannot "
        "single-handedly dominate the score.",
    ),
    PriorityWeightSpec(
        weight_name="impact",
        value=2.0,
        calibration_status="heuristic_default",
        justification="Applied to the category impact weight (see CATEGORY_IMPACT_WEIGHTS below).",
    ),
    PriorityWeightSpec(
        weight_name="critical_cutoff",
        value=25.0,
        calibration_status="heuristic_default",
        justification="~74% of the theoretical maximum score (34.0); unvalidated against production data.",
    ),
    PriorityWeightSpec(
        weight_name="high_cutoff",
        value=17.0,
        calibration_status="heuristic_default",
        justification="~50% of the theoretical maximum score; unvalidated against production data.",
    ),
    PriorityWeightSpec(
        weight_name="medium_cutoff",
        value=9.0,
        calibration_status="heuristic_default",
        justification="~26% of the theoretical maximum score; unvalidated against production data.",
    ),
)


def get_weight(name: str) -> float:
    for spec in PRIORITY_WEIGHTS:
        if spec.weight_name == name:
            return spec.value
    raise KeyError(f"no priority weight registered for '{name}'")


#: Every category the twelve Evaluation rules actually produce today.
CATEGORY_IMPACT_WEIGHTS: tuple[CategoryImpactSpec, ...] = (
    CategoryImpactSpec(
        category="configuration_quality",
        impact_weight=1.0,
        calibration_status="heuristic_default",
        justification="Typically a single missing key -- narrow, mechanical fix.",
    ),
    CategoryImpactSpec(
        category="framework_usage",
        impact_weight=1.0,
        calibration_status="heuristic_default",
        justification="Informational signal (matches FWK-001's own INFO severity), rarely actionable alone.",
    ),
    CategoryImpactSpec(
        category="service_organization",
        impact_weight=1.5,
        calibration_status="heuristic_default",
        justification="Operational volume concern, not structural.",
    ),
    CategoryImpactSpec(
        category="maintainability_indicators",
        impact_weight=1.5,
        calibration_status="heuristic_default",
        justification="Signals code health but the fix is per-file, not structural.",
    ),
    CategoryImpactSpec(
        category="api_exposure",
        impact_weight=2.0,
        calibration_status="heuristic_default",
        justification="Surface-area concern; kept conservative pending API-001's own recalibration "
        "per the Production Validation Report's §9 threshold review.",
    ),
    CategoryImpactSpec(
        category="dependency_structure",
        impact_weight=2.0,
        calibration_status="heuristic_default",
        justification="External coupling, but mechanically addressable.",
    ),
    CategoryImpactSpec(
        category="extension_mechanisms",
        impact_weight=2.5,
        calibration_status="heuristic_default",
        justification="Framework coupling (the real EXT-001 pattern) -- harder to unwind than a config key.",
    ),
    CategoryImpactSpec(
        category="modularity",
        impact_weight=3.0,
        calibration_status="heuristic_default",
        justification="Structural, cross-cutting by nature.",
    ),
    CategoryImpactSpec(
        category="cohesion",
        impact_weight=3.0,
        calibration_status="heuristic_default",
        justification="Structural, cross-cutting by nature.",
    ),
)

#: Returned for any category not present above (e.g. a future Evaluation
#: rule introducing a new category) -- a neutral default, never a crash.
_DEFAULT_CATEGORY_IMPACT_WEIGHT = 2.0


def get_category_impact_weight(category: str) -> float:
    for spec in CATEGORY_IMPACT_WEIGHTS:
        if spec.category == category:
            return spec.impact_weight
    return _DEFAULT_CATEGORY_IMPACT_WEIGHT


# -- §7 Grouping -----------------------------------------------------------------------------------


def _union_find_groups(findings: tuple[Finding, ...]) -> list[tuple[Finding, ...]]:
    """Two findings (already known to share one category) are grouped iff
    their `affected_modules` intersect, or both are empty (e.g.
    DEP-001/DEP-002, which are never module-scoped).
    """

    ordered = tuple(sorted(findings, key=lambda f: f.rule_id))
    count = len(ordered)
    parent = list(range(count))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[max(root_i, root_j)] = min(root_i, root_j)

    for i in range(count):
        for j in range(i + 1, count):
            modules_i = set(ordered[i].affected_modules)
            modules_j = set(ordered[j].affected_modules)
            if (modules_i and modules_j and modules_i & modules_j) or (not modules_i and not modules_j):
                union(i, j)

    groups_by_root: dict[int, list[Finding]] = {}
    for i in range(count):
        groups_by_root.setdefault(find(i), []).append(ordered[i])

    return [tuple(members) for _, members in sorted(groups_by_root.items())]


def group_findings(
    findings: tuple[Finding, ...],
) -> tuple[list[tuple[Finding, ...]], tuple[SkippedGrouping, ...]]:
    """§4 Stage 1. Groups findings first by shared `category`, then within
    each category by `_union_find_groups`. A category whose grouping step
    fails unexpectedly falls back to one singleton group per finding in
    that category, recorded via `SkippedGrouping` -- never dropped.
    """

    by_category: dict[str, list[Finding]] = {}
    for finding in findings:
        by_category.setdefault(finding.category, []).append(finding)

    groups: list[tuple[Finding, ...]] = []
    skipped: list[SkippedGrouping] = []
    for category in sorted(by_category):
        category_findings = tuple(by_category[category])
        try:
            groups.extend(_union_find_groups(category_findings))
        except Exception as exc:  # a raising grouping step is recorded, never propagated
            skipped.append(SkippedGrouping(category=category, reason=str(exc)))
            groups.extend((finding,) for finding in sorted(category_findings, key=lambda f: f.rule_id))

    return groups, tuple(skipped)


# -- Shared aggregation helpers ----------------------------------------------------------------------


def union_affected_files(group: tuple[Finding, ...]) -> tuple[str, ...]:
    return tuple(sorted({path for finding in group for path in finding.affected_files}))


def union_affected_modules(group: tuple[Finding, ...]) -> tuple[str, ...]:
    return tuple(sorted({module for finding in group for module in finding.affected_modules}))


def union_evidence(group: tuple[Finding, ...]) -> tuple[Evidence, ...]:
    seen: set[tuple[str, str, str]] = set()
    result: list[Evidence] = []
    for finding in group:
        for evidence in finding.evidence:
            key = (evidence.fact_kind, evidence.fact_summary, evidence.relative_path)
            if key not in seen:
                seen.add(key)
                result.append(evidence)
    return tuple(result)


def _group_severity(group: tuple[Finding, ...]) -> Severity:
    # Worst case drives urgency.
    return max(group, key=lambda finding: _SEVERITY_ORDER[finding.severity]).severity


def _group_confidence(group: tuple[Finding, ...]) -> Confidence:
    # Weakest link drives how much to trust the group as a whole.
    return min(group, key=lambda finding: _CONFIDENCE_ORDER[finding.confidence]).confidence


# -- §6 Prioritization ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreBreakdown:
    """Package-internal. Kept so `priority_score`'s components are always
    individually visible to the rationale template (§9) -- "no opaque
    scoring" applied to this engine's own output, not just Evaluation's.
    """

    severity_component: float
    confidence_component: float
    scope_component: float
    impact_component: float

    @property
    def total(self) -> float:
        return (
            self.severity_component + self.confidence_component + self.scope_component + self.impact_component
        )


def _priority_from_score(score: float) -> Priority:
    if score >= get_weight("critical_cutoff"):
        return Priority.CRITICAL
    if score >= get_weight("high_cutoff"):
        return Priority.HIGH
    if score >= get_weight("medium_cutoff"):
        return Priority.MEDIUM
    return Priority.LOW


def score_group(
    group: tuple[Finding, ...], affected_files: tuple[str, ...]
) -> tuple[ScoreBreakdown, Priority]:
    severity = _group_severity(group)
    confidence = _group_confidence(group)
    category = group[0].category  # every finding in a group shares one category, by construction (§7)
    scope = min(len(affected_files), get_weight("scope_cap"))

    breakdown = ScoreBreakdown(
        severity_component=_SEVERITY_ORDER[severity] * get_weight("severity"),
        confidence_component=_CONFIDENCE_ORDER[confidence] * get_weight("confidence"),
        scope_component=scope * get_weight("scope"),
        impact_component=get_category_impact_weight(category) * get_weight("impact"),
    )

    priority_from_score = _priority_from_score(breakdown.total)
    ceiling = _SEVERITY_PRIORITY_CEILING[severity]
    priority = (
        priority_from_score if _PRIORITY_ORDER[priority_from_score] <= _PRIORITY_ORDER[ceiling] else ceiling
    )
    return breakdown, priority


# -- §9 Explainability templates ----------------------------------------------------------------------

_MAX_LISTED_ITEMS = 5


def _format_capped_list(items: tuple[str, ...]) -> str:
    if not items:
        return ""
    if len(items) <= _MAX_LISTED_ITEMS:
        return ", ".join(items)
    shown = ", ".join(items[:_MAX_LISTED_ITEMS])
    remaining = len(items) - _MAX_LISTED_ITEMS
    return f"{shown}, and {remaining} more"


def title_for(group: tuple[Finding, ...]) -> str:
    if len(group) == 1:
        return group[0].rule_name
    category_label = group[0].category.replace("_", " ")
    return f"Multiple {category_label} findings ({len(group)})"


def rationale_for(
    group: tuple[Finding, ...],
    priority: Priority,
    breakdown: ScoreBreakdown,
    affected_files: tuple[str, ...],
    affected_modules: tuple[str, ...],
) -> str:
    rule_names = ", ".join(finding.rule_name for finding in group)
    category = group[0].category
    files_desc = f"{len(affected_files)} file(s)"
    if affected_files:
        files_desc += f" including {_format_capped_list(affected_files)}"
    modules_desc = f" across module(s) {_format_capped_list(affected_modules)}" if affected_modules else ""
    return (
        f"Derived from {len(group)} finding(s) ({rule_names}) in category '{category}'. "
        f"Affects {files_desc}{modules_desc}. "
        f"Priority {priority.value} (score {breakdown.total:.1f} = "
        f"severity {breakdown.severity_component:.1f} + confidence {breakdown.confidence_component:.1f} "
        f"+ scope {breakdown.scope_component:.1f} + category_impact {breakdown.impact_component:.1f})."
    )


# -- §8 Conflict Resolution ----------------------------------------------------------------------------

#: Pairs of categories declared to represent potentially contradictory
#: guidance. Empty in v1.0 -- no such pair exists among the current
#: twelve Evaluation rules (disclosed, not fabricated to justify the
#: mechanism below).
OPPOSING_CATEGORY_PAIRS: tuple[tuple[str, str], ...] = ()


def detect_conflicts(recommendations: tuple[Recommendation, ...]) -> tuple[Recommendation, ...]:
    """Never drops or auto-resolves a conflict -- only makes it visible via
    `conflicts_with`, since choosing a winner is explicitly out of this
    engine's scope (§8).
    """

    if not OPPOSING_CATEGORY_PAIRS:
        return recommendations

    opposing_pairs = {frozenset(pair) for pair in OPPOSING_CATEGORY_PAIRS}
    conflicts: dict[str, list[str]] = {rec.recommendation_id: [] for rec in recommendations}
    for i, first in enumerate(recommendations):
        for second in recommendations[i + 1 :]:
            if frozenset((first.category, second.category)) in opposing_pairs:
                conflicts[first.recommendation_id].append(second.recommendation_id)
                conflicts[second.recommendation_id].append(first.recommendation_id)

    if not any(conflicts.values()):
        return recommendations

    return tuple(
        rec.model_copy(update={"conflicts_with": tuple(sorted(conflicts[rec.recommendation_id]))})
        for rec in recommendations
    )
