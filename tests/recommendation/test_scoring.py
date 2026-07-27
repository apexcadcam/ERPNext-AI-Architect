"""Tests for `recommendation.scoring` (Recommendation Engine Architecture Specification v1.0
§6, §7, §8, §9)."""

from __future__ import annotations

import pytest

from evaluation.contract import Confidence, Evidence, Finding, Severity

from recommendation.contract import Priority
from recommendation.scoring import (
    CATEGORY_IMPACT_WEIGHTS,
    OPPOSING_CATEGORY_PAIRS,
    PRIORITY_WEIGHTS,
    ScoreBreakdown,
    detect_conflicts,
    get_category_impact_weight,
    get_weight,
    group_findings,
    rationale_for,
    score_group,
    title_for,
    union_affected_files,
    union_affected_modules,
    union_evidence,
)

# -- Fixture builders --------------------------------------------------------------------------------


def _evidence(path: str = "x.py", summary: str = "s") -> Evidence:
    return Evidence(fact_kind="ApiFact", fact_summary=summary, relative_path=path)


def _finding(
    rule_id: str,
    *,
    category: str = "extension_mechanisms",
    severity: Severity = Severity.MEDIUM,
    confidence: Confidence = Confidence.HIGH,
    affected_files: tuple[str, ...] = ("a.py",),
    affected_modules: tuple[str, ...] = ("app",),
) -> Finding:
    return Finding(
        rule_id=rule_id,
        rule_name=f"Rule {rule_id}",
        category=category,
        severity=severity,
        confidence=confidence,
        metric_value=1.0,
        explanation="x",
        evidence=(_evidence(path=affected_files[0] if affected_files else "x.py"),),
        affected_files=affected_files,
        affected_modules=affected_modules,
    )


# -- Weight registries -------------------------------------------------------------------------------


def test_get_weight_returns_the_registered_value() -> None:
    assert get_weight("severity") == 3.0


def test_get_weight_raises_for_an_unregistered_weight() -> None:
    with pytest.raises(KeyError):
        get_weight("does_not_exist")


def test_every_priority_weight_is_heuristic_default() -> None:
    # No production data exists yet for this engine -- see the module's own docstring.
    assert {spec.calibration_status for spec in PRIORITY_WEIGHTS} == {"heuristic_default"}


def test_get_category_impact_weight_returns_the_registered_value() -> None:
    assert get_category_impact_weight("modularity") == 3.0


def test_get_category_impact_weight_returns_the_default_for_an_unregistered_category() -> None:
    assert get_category_impact_weight("some_future_category") == 2.0


def test_every_category_impact_weight_is_heuristic_default() -> None:
    assert {spec.calibration_status for spec in CATEGORY_IMPACT_WEIGHTS} == {"heuristic_default"}


def test_category_impact_weights_cover_every_real_evaluation_rule_category() -> None:
    real_categories = {
        "modularity",
        "cohesion",
        "extension_mechanisms",
        "dependency_structure",
        "configuration_quality",
        "api_exposure",
        "service_organization",
        "maintainability_indicators",
        "framework_usage",
    }
    registered = {spec.category for spec in CATEGORY_IMPACT_WEIGHTS}
    assert real_categories <= registered


# -- Grouping (§7) -----------------------------------------------------------------------------------


def test_group_findings_groups_same_category_overlapping_modules() -> None:
    findings = (
        _finding("MOD-001", category="modularity", affected_modules=("app",)),
        _finding("MOD-002", category="modularity", affected_modules=("app", "app.sub")),
    )
    groups, skipped = group_findings(findings)
    assert skipped == ()
    assert len(groups) == 1
    assert {f.rule_id for f in groups[0]} == {"MOD-001", "MOD-002"}


def test_group_findings_groups_same_category_both_empty_modules() -> None:
    # The real DEP-001/DEP-002 case -- dependencies are never module-scoped.
    findings = (
        _finding("DEP-001", category="dependency_structure", affected_modules=()),
        _finding("DEP-002", category="dependency_structure", affected_modules=()),
    )
    groups, skipped = group_findings(findings)
    assert skipped == ()
    assert len(groups) == 1
    assert {f.rule_id for f in groups[0]} == {"DEP-001", "DEP-002"}


def test_group_findings_does_not_group_same_category_disjoint_modules() -> None:
    findings = (
        _finding("MOD-002", category="modularity", affected_modules=("app_a",)),
        _finding("MOD-002-other", category="modularity", affected_modules=("app_b",)),
    )
    groups, skipped = group_findings(findings)
    assert skipped == ()
    assert len(groups) == 2


def test_group_findings_does_not_group_across_categories() -> None:
    findings = (
        _finding("EXT-001", category="extension_mechanisms", affected_modules=("app",)),
        _finding("SVC-001", category="service_organization", affected_modules=("app",)),
    )
    groups, skipped = group_findings(findings)
    assert len(groups) == 2


def test_group_findings_does_not_group_one_empty_one_nonempty_module_set() -> None:
    findings = (
        _finding("DEP-001", category="dependency_structure", affected_modules=()),
        _finding("DEP-002", category="dependency_structure", affected_modules=("app",)),
    )
    groups, _ = group_findings(findings)
    assert len(groups) == 2


def test_group_findings_handles_a_single_finding() -> None:
    findings = (_finding("EXT-001"),)
    groups, skipped = group_findings(findings)
    assert skipped == ()
    assert groups == [(findings[0],)]


def test_group_findings_handles_zero_findings() -> None:
    groups, skipped = group_findings(())
    assert groups == []
    assert skipped == ()


def test_group_findings_records_skipped_grouping_when_union_find_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The category grouping step is never allowed to abort the whole run --
    # a raising `_union_find_groups` degrades to one singleton group per
    # finding in that category, recorded via `SkippedGrouping`.
    import recommendation.scoring as scoring_module

    def _broken(findings: tuple[Finding, ...]) -> list[tuple[Finding, ...]]:
        raise ValueError("deliberately broken for this test")

    monkeypatch.setattr(scoring_module, "_union_find_groups", _broken)

    findings = (
        _finding("MOD-001", category="modularity"),
        _finding("MOD-002", category="modularity"),
    )
    groups, skipped = group_findings(findings)

    assert len(skipped) == 1
    assert skipped[0].category == "modularity"
    assert "deliberately broken" in skipped[0].reason
    assert [tuple(f.rule_id for f in group) for group in groups] == [("MOD-001",), ("MOD-002",)]


# -- Aggregation helpers ------------------------------------------------------------------------------


def test_union_affected_files_deduplicates_and_sorts() -> None:
    group = (
        _finding("A", affected_files=("b.py", "a.py")),
        _finding("B", affected_files=("a.py", "c.py")),
    )
    assert union_affected_files(group) == ("a.py", "b.py", "c.py")


def test_union_affected_modules_deduplicates_and_sorts() -> None:
    group = (
        _finding("A", affected_modules=("b", "a")),
        _finding("B", affected_modules=("a", "c")),
    )
    assert union_affected_modules(group) == ("a", "b", "c")


def test_union_evidence_deduplicates_identical_entries() -> None:
    shared = _evidence(path="x.py", summary="same")
    finding_a = _finding("A").model_copy(update={"evidence": (shared,)})
    finding_b = _finding("B").model_copy(update={"evidence": (shared,)})
    assert union_evidence((finding_a, finding_b)) == (shared,)


# -- Scoring (§6) -- including the severity-ceiling correction --------------------------------------


def test_score_group_medium_severity_high_confidence() -> None:
    group = (
        _finding(
            "EXT-001", category="extension_mechanisms", severity=Severity.MEDIUM, confidence=Confidence.HIGH
        ),
    )
    breakdown, priority = score_group(group, affected_files=("a.py",))
    assert isinstance(breakdown, ScoreBreakdown)
    assert priority is Priority.HIGH


def test_score_group_severity_ceiling_prevents_info_finding_from_reaching_high_priority() -> None:
    # The exact real scenario this design correction targets: an INFO-severity
    # finding (like FWK-001) with many affected files/modules must never be
    # inflated past its own severity's ceiling (MEDIUM), no matter how large
    # affected_scope or category_impact are.
    many_files = tuple(f"file_{i}.py" for i in range(50))
    many_modules = tuple(f"module_{i}" for i in range(50))
    group = (
        _finding(
            "FWK-001",
            category="modularity",  # the highest-impact category, to stress-test the ceiling
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            affected_files=many_files,
            affected_modules=many_modules,
        ),
    )
    breakdown, priority = score_group(group, affected_files=many_files)
    assert breakdown.total > get_weight("high_cutoff")  # the raw score alone WOULD be HIGH+
    assert priority is Priority.MEDIUM  # but the INFO severity ceiling caps it


def test_score_group_high_severity_reaches_critical_ceiling_when_score_warrants_it() -> None:
    many_files = tuple(f"file_{i}.py" for i in range(50))
    group = (
        _finding(
            "DEP-001",
            category="modularity",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            affected_files=many_files,
            affected_modules=(),
        ),
    )
    breakdown, priority = score_group(group, affected_files=many_files)
    assert priority is Priority.CRITICAL


def test_score_group_low_severity_never_exceeds_its_own_ceiling() -> None:
    group = (_finding("X", category="modularity", severity=Severity.LOW, confidence=Confidence.HIGH),)
    _, priority = score_group(group, affected_files=("a.py",) * 50)
    assert priority is Priority.MEDIUM


def test_score_group_returns_low_priority_below_the_medium_cutoff() -> None:
    group = (
        _finding(
            "CFG-001",
            category="configuration_quality",  # the lowest-impact category
            severity=Severity.INFO,
            confidence=Confidence.LOW,
            affected_files=(),
            affected_modules=(),
        ),
    )
    breakdown, priority = score_group(group, affected_files=())
    assert breakdown.total < get_weight("medium_cutoff")
    assert priority is Priority.LOW


def test_score_group_uses_worst_case_severity_across_the_group() -> None:
    group = (
        _finding("A", severity=Severity.INFO),
        _finding("B", severity=Severity.HIGH),
    )
    breakdown, _ = score_group(group, affected_files=("a.py",))
    assert breakdown.severity_component == 3 * get_weight("severity")  # HIGH's ordinal, not INFO's


def test_score_group_uses_weakest_link_confidence_across_the_group() -> None:
    group = (
        _finding("A", confidence=Confidence.HIGH),
        _finding("B", confidence=Confidence.LOW),
    )
    breakdown, _ = score_group(group, affected_files=("a.py",))
    assert breakdown.confidence_component == 1 * get_weight("confidence")  # LOW's ordinal, not HIGH's


# -- Templates (§9) ----------------------------------------------------------------------------------


def test_title_for_a_single_finding_uses_its_rule_name() -> None:
    group = (_finding("EXT-001"),)
    assert title_for(group) == "Rule EXT-001"


def test_title_for_a_group_summarizes_the_category_and_count() -> None:
    group = (
        _finding("DEP-001", category="dependency_structure"),
        _finding("DEP-002", category="dependency_structure"),
    )
    assert title_for(group) == "Multiple dependency structure findings (2)"


def test_rationale_for_caps_a_long_affected_files_list() -> None:
    group = (_finding("EXT-001"),)
    breakdown = ScoreBreakdown(
        severity_component=6.0, confidence_component=6.0, scope_component=10.0, impact_component=5.0
    )
    files = tuple(f"file_{i}.py" for i in range(20))
    rationale = rationale_for(group, Priority.HIGH, breakdown, files, ())
    assert "and 15 more" in rationale
    assert "file_0.py" in rationale
    assert "file_19.py" not in rationale  # past the cap, never individually named


def test_rationale_for_states_the_score_breakdown_transparently() -> None:
    group = (_finding("EXT-001"),)
    breakdown = ScoreBreakdown(
        severity_component=6.0, confidence_component=6.0, scope_component=1.0, impact_component=5.0
    )
    rationale = rationale_for(group, Priority.HIGH, breakdown, ("a.py",), ("app",))
    assert "severity 6.0" in rationale
    assert "confidence 6.0" in rationale
    assert "scope 1.0" in rationale
    assert "category_impact 5.0" in rationale


# -- Conflict detection (§8) --------------------------------------------------------------------------


def test_opposing_category_pairs_is_empty_in_v1() -> None:
    assert OPPOSING_CATEGORY_PAIRS == ()


def test_detect_conflicts_is_a_no_op_with_an_empty_registry() -> None:
    from recommendation.contract import Recommendation

    rec = Recommendation(
        recommendation_id="rec-1",
        title="x",
        category="modularity",
        priority=Priority.HIGH,
        priority_score=18.0,
        rationale="x",
        supporting_findings=("MOD-001",),
        evidence=(_evidence(),),
        affected_files=(),
        affected_modules=(),
    )
    result = detect_conflicts((rec,))
    assert result == (rec,)
    assert result[0].conflicts_with == ()


def test_detect_conflicts_flags_both_sides_when_the_registry_has_an_opposing_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from recommendation.contract import Recommendation

    import recommendation.scoring as scoring_module

    monkeypatch.setattr(scoring_module, "OPPOSING_CATEGORY_PAIRS", (("modularity", "cohesion"),))

    rec_a = Recommendation(
        recommendation_id="rec-a",
        title="a",
        category="modularity",
        priority=Priority.HIGH,
        priority_score=18.0,
        rationale="x",
        supporting_findings=("MOD-001",),
        evidence=(_evidence(),),
        affected_files=(),
        affected_modules=(),
    )
    rec_b = Recommendation(
        recommendation_id="rec-b",
        title="b",
        category="cohesion",
        priority=Priority.HIGH,
        priority_score=18.0,
        rationale="x",
        supporting_findings=("COH-001",),
        evidence=(_evidence(),),
        affected_files=(),
        affected_modules=(),
    )

    result = detect_conflicts((rec_a, rec_b))

    by_id = {r.recommendation_id: r for r in result}
    assert by_id["rec-a"].conflicts_with == ("rec-b",)
    assert by_id["rec-b"].conflicts_with == ("rec-a",)


def test_detect_conflicts_returns_unchanged_when_registry_has_pairs_but_none_actually_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A non-empty registry that happens not to match any category pair present
    # in this run must not fabricate a conflict.
    from recommendation.contract import Recommendation

    import recommendation.scoring as scoring_module

    monkeypatch.setattr(scoring_module, "OPPOSING_CATEGORY_PAIRS", (("modularity", "cohesion"),))

    rec_a = Recommendation(
        recommendation_id="rec-a",
        title="a",
        category="modularity",
        priority=Priority.HIGH,
        priority_score=18.0,
        rationale="x",
        supporting_findings=("MOD-001",),
        evidence=(_evidence(),),
        affected_files=(),
        affected_modules=(),
    )
    rec_b = Recommendation(
        recommendation_id="rec-b",
        title="b",
        category="extension_mechanisms",  # not the opposing category of "modularity"
        priority=Priority.HIGH,
        priority_score=18.0,
        rationale="x",
        supporting_findings=("EXT-001",),
        evidence=(_evidence(),),
        affected_files=(),
        affected_modules=(),
    )

    result = detect_conflicts((rec_a, rec_b))

    assert result == (rec_a, rec_b)
    assert all(r.conflicts_with == () for r in result)


def test_format_capped_list_returns_empty_string_for_no_items() -> None:
    # No higher-level caller reaches this branch: `rationale_for` only calls
    # `_format_capped_list` when `affected_files`/`affected_modules` is
    # already non-empty. Tested directly, following this project's own
    # precedent (e.g. `evaluation.rules._evidence_for`).
    from recommendation.scoring import _format_capped_list

    assert _format_capped_list(()) == ""
