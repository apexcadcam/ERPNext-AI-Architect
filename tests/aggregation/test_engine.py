"""Tests for `aggregation.engine` (Pattern Aggregation Engine Architecture
Specification v1.0 §10, §11).
"""

from __future__ import annotations

import pytest

from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceKind,
    EvidenceSet,
    EvidenceStatistics,
    Source,
)

from aggregation.contract import (
    AggregationRequest,
    AggregationStatus,
    Pattern,
    PatternSet,
    PopulationBasis,
    ResolutionStrategy,
)
from aggregation.engine import MIN_OCCURRENCES_THRESHOLD, aggregate_patterns

_COMMIT = "1d14ba16398db3a220873509565c60f2932bed81"
_HOOK_COLLECTOR = CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR
_API_COLLECTOR = CollectorName.WHITELISTED_API_DECORATION_COLLECTOR

# -- Fixture builders --------------------------------------------------------------------------------


def _evidence(
    *,
    symbol: str,
    subject: str,
    category: EvidenceCategory = EvidenceCategory.WHITELISTED_API_DECORATION,
    line: int = 1,
) -> Evidence:
    collector = _API_COLLECTOR if category is EvidenceCategory.WHITELISTED_API_DECORATION else _HOOK_COLLECTOR
    return Evidence(
        evidence_id=f"{category.value}|{symbol}|{subject}|{line}".ljust(64, "0")[:64],
        kind=EvidenceKind.IMPLEMENTATION,
        category=category,
        symbol=symbol,
        subject=subject,
        source=Source(
            repository=CanonicalRepository.ERPNEXT,
            version="v15.102.0",
            commit=_COMMIT,
            relative_path="erpnext/api.py",
            line=line,
        ),
        collector=collector,
        collected_at="2026-07-27T12:00:00+00:00",
    )


def _evidence_set(*records: Evidence) -> EvidenceSet:
    return EvidenceSet(
        evidence_set_id="evset-1",
        schema_version="1.0",
        repository=CanonicalRepository.ERPNEXT,
        version="v15.102.0",
        commit=_COMMIT,
        extracted_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=records,
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=len(records)
        ),
    )


def _request(*records: Evidence, min_occurrences: int = 2) -> AggregationRequest:
    return AggregationRequest(
        evidence_set=_evidence_set(*records),
        min_occurrences=min_occurrences,
        correlation_id="corr-1",
        requested_by="test-suite",
    )


def _whitelisted(symbol: str, *extra_subjects: str) -> list[Evidence]:
    """A whitelisted function plus any additional decorators on it."""
    records = [_evidence(symbol=symbol, subject="frappe.whitelist")]
    records += [_evidence(symbol=symbol, subject=subject) for subject in extra_subjects]
    return records


# -- End to end: both categories in one run ------------------------------------------------------------


def test_aggregates_one_category_and_skips_the_other_in_a_single_run() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        _evidence(
            symbol="erpnext.Customer.validate",
            subject="validate",
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        ),
        _evidence(
            symbol="erpnext.Supplier.validate",
            subject="validate",
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        ),
    ]

    result = aggregate_patterns(_request(*records))

    assert {p.evidence_category for p in result.patterns} == {EvidenceCategory.WHITELISTED_API_DECORATION}
    assert [s.evidence_category for s in result.skipped_aggregations] == [
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK
    ]


def test_support_is_occurrences_over_population() -> None:
    # 2 of 3 whitelisted symbols also carry frappe.read_only.
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        *_whitelisted("erpnext.api.c"),
    ]

    result = aggregate_patterns(_request(*records))

    read_only = next(p for p in result.patterns if p.subject == "frappe.read_only")
    assert read_only.occurrences == 2
    assert read_only.population == 3
    assert read_only.support == pytest.approx(2 / 3)


def test_the_whitelist_marker_itself_has_full_support() -> None:
    records = [*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")]

    result = aggregate_patterns(_request(*records))

    whitelist = next(p for p in result.patterns if p.subject == "frappe.whitelist")
    assert whitelist.occurrences == whitelist.population == 2
    assert whitelist.support == 1.0


def test_a_pattern_carries_exactly_the_evidence_ids_it_counted() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
    ]

    result = aggregate_patterns(_request(*records))

    read_only = next(p for p in result.patterns if p.subject == "frappe.read_only")
    expected = sorted(r.evidence_id for r in records if r.subject == "frappe.read_only")
    assert list(read_only.supporting_evidence_ids) == expected


def test_a_pattern_carries_the_population_description_from_its_resolver() -> None:
    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))
    assert "distinct symbols" in result.patterns[0].population_description


def test_occurrences_counts_distinct_symbols_not_records() -> None:
    # Same symbol, same subject, two different source lines -- one symbol.
    records = [
        *_whitelisted("erpnext.api.a"),
        *_whitelisted("erpnext.api.b"),
        _evidence(symbol="erpnext.api.a", subject="frappe.read_only", line=10),
        _evidence(symbol="erpnext.api.a", subject="frappe.read_only", line=20),
    ]

    result = aggregate_patterns(_request(*records, min_occurrences=1))

    read_only = next(p for p in result.patterns if p.subject == "frappe.read_only")
    assert read_only.occurrences == 1


# -- SkippedAggregation is a first-class result (§9) ---------------------------------------------------


def test_the_skip_carries_a_machine_readable_status_and_a_real_record_count() -> None:
    hooks = [
        _evidence(
            symbol=f"erpnext.C{i}.validate",
            subject="validate",
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        )
        for i in range(5)
    ]

    result = aggregate_patterns(_request(*hooks))

    skip = result.skipped_aggregations[0]
    assert skip.status is AggregationStatus.SKIPPED_NO_POPULATION
    assert skip.evidence_records_present == 5
    assert skip.reason.strip() != ""


def test_lifecycle_hooks_without_a_resolvable_population_still_skip() -> None:
    # Sprint 22 made the category aggregatable, not unconditionally
    # measurable. Hook records with no class-definition Evidence beside
    # them resolve to an empty population, and an empty denominator is
    # still a recorded skip rather than a fabricated number.
    hooks = [
        _evidence(
            symbol="erpnext.C.validate",
            subject="validate",
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        )
    ]

    result = aggregate_patterns(_request(*hooks))

    assert result.skipped_aggregations[0].reason == "the resolved population is empty"
    assert result.patterns == ()


def test_a_skipped_category_produces_no_patterns_at_all() -> None:
    hooks = [
        _evidence(
            symbol=f"erpnext.C{i}.validate",
            subject="validate",
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        )
        for i in range(3)
    ]

    result = aggregate_patterns(_request(*hooks))

    assert result.patterns == ()
    assert result.observed_below_threshold == ()
    assert len(result.skipped_aggregations) == 1


def test_zero_patterns_with_a_populated_skip_list_is_a_valid_successful_result() -> None:
    # §7.7: "nothing was measurable, and here is precisely why".
    hooks = [
        _evidence(
            symbol="erpnext.C.validate",
            subject="validate",
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        )
    ]

    result = aggregate_patterns(_request(*hooks))

    assert result.patterns == ()
    assert result.skipped_aggregations != ()
    assert result.statistics.categories_skipped == 1
    assert result.statistics.patterns_produced == 0


# -- Never fabricate a denominator, never divide by zero -----------------------------------------------


def test_a_category_whose_population_resolves_to_zero_is_skipped_not_divided() -> None:
    # Whitelisted-API records exist, but none carries a whitelist-family
    # marker -- so the population is genuinely empty. The engine must skip
    # rather than divide by zero or invent a denominator.
    records = [
        _evidence(symbol="erpnext.helpers.a", subject="redis_cache"),
        _evidence(symbol="erpnext.helpers.b", subject="staticmethod"),
    ]

    result = aggregate_patterns(_request(*records))

    assert result.patterns == ()
    skip = next(
        s
        for s in result.skipped_aggregations
        if s.evidence_category is EvidenceCategory.WHITELISTED_API_DECORATION
    )
    assert skip.status is AggregationStatus.SKIPPED_NO_POPULATION
    assert skip.evidence_records_present == 2
    assert "population is empty" in skip.reason


def test_a_category_with_no_matrix_entry_degrades_to_a_recorded_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # §8's default-deny at engine level. Unreachable with today's two
    # registered categories, so simulated: this is the behavior that
    # protects a FUTURE Evidence category added without a matrix row --
    # it must become a recorded skip, never a fabricated denominator.
    import aggregation.engine as engine_module

    monkeypatch.setattr(engine_module, "get_population_basis", lambda category: None)

    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))

    assert result.patterns == ()
    skip = result.skipped_aggregations[0]
    assert skip.status is AggregationStatus.SKIPPED_NO_POPULATION
    assert "no population basis is registered" in skip.reason
    assert skip.evidence_records_present == 2


def test_an_aggregated_category_with_no_resolver_degrades_to_a_recorded_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The matrix declares the category aggregatable but no resolver backs
    # it. Cross-checked by test_resolvers.py so unreachable today; kept
    # because silently proceeding would mean inventing a denominator.
    import aggregation.engine as engine_module

    monkeypatch.setattr(engine_module, "POPULATION_RESOLVERS", {})

    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))

    assert result.patterns == ()
    skip = result.skipped_aggregations[0]
    assert skip.status is AggregationStatus.SKIPPED_NO_POPULATION
    assert "no population resolver is registered" in skip.reason


def test_no_pattern_can_ever_carry_a_zero_population() -> None:
    records = [*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")]
    result = aggregate_patterns(_request(*records))
    assert all(p.population >= 1 for p in result.patterns)


def test_every_support_stays_within_the_unit_interval() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        *_whitelisted("erpnext.api.c"),
    ]
    result = aggregate_patterns(_request(*records))
    assert all(0.0 <= p.support <= 1.0 for p in result.patterns)


# -- Threshold behavior (§7.6) ---------------------------------------------------------------------------


def test_a_subject_at_exactly_min_occurrences_is_promoted_to_a_pattern() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        *_whitelisted("erpnext.api.c"),
    ]

    result = aggregate_patterns(_request(*records, min_occurrences=2))

    assert any(p.subject == "frappe.read_only" for p in result.patterns)


def test_a_subject_below_the_threshold_is_recorded_not_dropped() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "staticmethod"),
        *_whitelisted("erpnext.api.b"),
        *_whitelisted("erpnext.api.c"),
    ]

    result = aggregate_patterns(_request(*records, min_occurrences=2))

    assert not any(p.subject == "staticmethod" for p in result.patterns)
    below = next(o for o in result.observed_below_threshold if o.subject == "staticmethod")
    assert below.occurrences == 1


def test_raising_the_threshold_moves_a_subject_out_of_patterns() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        *_whitelisted("erpnext.api.c"),
    ]

    result = aggregate_patterns(_request(*records, min_occurrences=3))

    assert not any(p.subject == "frappe.read_only" for p in result.patterns)
    assert any(o.subject == "frappe.read_only" for o in result.observed_below_threshold)


def test_the_min_occurrences_threshold_is_registered_not_inlined() -> None:
    assert MIN_OCCURRENCES_THRESHOLD.threshold_name == "min_occurrences"
    assert MIN_OCCURRENCES_THRESHOLD.value == 2
    assert MIN_OCCURRENCES_THRESHOLD.calibration_status == "heuristic_default"
    assert MIN_OCCURRENCES_THRESHOLD.justification.strip() != ""


def test_the_registered_threshold_matches_the_request_default() -> None:
    request = AggregationRequest(evidence_set=_evidence_set(), correlation_id="c", requested_by="r")
    assert request.min_occurrences == MIN_OCCURRENCES_THRESHOLD.value


# -- Determinism and stable ordering (§11) ---------------------------------------------------------------


def test_two_runs_are_identical_including_every_pattern_id() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        *_whitelisted("erpnext.api.c"),
    ]
    request = _request(*records)

    first = aggregate_patterns(request)
    second = aggregate_patterns(request)

    strip = {"pattern_set_id": "x", "aggregated_at": "x"}
    assert first.model_copy(update=strip) == second.model_copy(update=strip)
    assert [p.pattern_id for p in first.patterns] == [p.pattern_id for p in second.patterns]


def test_patterns_are_sorted_by_category_then_most_frequent_then_subject() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "zzz_rare", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        *_whitelisted("erpnext.api.c", "zzz_rare"),
    ]

    result = aggregate_patterns(_request(*records, min_occurrences=2))

    keys = [(p.evidence_category.value, -p.occurrences, p.subject) for p in result.patterns]
    assert keys == sorted(keys)


def test_pattern_order_does_not_depend_on_input_record_order() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        *_whitelisted("erpnext.api.c"),
    ]

    forward = aggregate_patterns(_request(*records))
    reversed_ = aggregate_patterns(_request(*reversed(records)))

    assert [p.subject for p in forward.patterns] == [p.subject for p in reversed_.patterns]
    assert [p.pattern_id for p in forward.patterns] == [p.pattern_id for p in reversed_.patterns]


def test_below_threshold_entries_are_stably_sorted() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "zzz_one", "aaa_one"),
        *_whitelisted("erpnext.api.b"),
    ]

    result = aggregate_patterns(_request(*records, min_occurrences=2))

    keys = [(o.evidence_category.value, -o.occurrences, o.subject) for o in result.observed_below_threshold]
    assert keys == sorted(keys)


def test_supporting_evidence_ids_are_sorted_within_each_pattern() -> None:
    records = [*_whitelisted("erpnext.api.z"), *_whitelisted("erpnext.api.a")]

    result = aggregate_patterns(_request(*records))

    ids = list(result.patterns[0].supporting_evidence_ids)
    assert ids == sorted(ids)


def test_the_same_fact_at_the_same_commit_always_yields_the_same_pattern_id() -> None:
    records = [*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")]

    first = aggregate_patterns(_request(*records))
    second = aggregate_patterns(_request(*reversed(records)))

    assert first.patterns[0].pattern_id == second.patterns[0].pattern_id


# -- Artifact assembly ------------------------------------------------------------------------------------


def test_the_pattern_set_traces_back_to_its_source_evidence_set() -> None:
    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))
    assert result.source_evidence_set_id == "evset-1"


def test_the_pattern_set_echoes_the_evidence_sets_provenance() -> None:
    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))
    assert result.repository is CanonicalRepository.ERPNEXT
    assert result.version == "v15.102.0"
    assert result.commit == _COMMIT
    assert result.schema_version == "2.0"


def test_every_pattern_echoes_the_provenance_too() -> None:
    # A pattern is only true of a specific commit, so it carries it.
    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))
    for pattern in result.patterns:
        assert pattern.repository is CanonicalRepository.ERPNEXT
        assert pattern.version == "v15.102.0"
        assert pattern.commit == _COMMIT


def test_statistics_reflect_the_real_run() -> None:
    records = [
        *_whitelisted("erpnext.api.a", "frappe.read_only", "staticmethod"),
        *_whitelisted("erpnext.api.b", "frappe.read_only"),
        _evidence(
            symbol="erpnext.C.validate",
            subject="validate",
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        ),
    ]

    result = aggregate_patterns(_request(*records))

    assert result.statistics.evidence_records_consumed == len(records)
    assert result.statistics.categories_present == 2
    assert result.statistics.categories_aggregated == 1
    assert result.statistics.categories_skipped == 1
    assert result.statistics.patterns_produced == len(result.patterns)
    assert result.statistics.subjects_below_threshold == len(result.observed_below_threshold)


def test_an_empty_evidence_set_produces_a_valid_empty_pattern_set() -> None:
    result = aggregate_patterns(_request())

    assert result.patterns == ()
    assert result.skipped_aggregations == ()
    assert result.observed_below_threshold == ()
    assert result.statistics.categories_present == 0
    assert result.statistics.evidence_records_consumed == 0


def test_correlation_id_is_carried_from_the_request() -> None:
    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))
    assert result.correlation_id == "corr-1"


# -- Sprint 22: structural evidence, resolved populations, and provenance --------------------------------


def _class(name: str, *bases: str, module: str = "erpnext.mod") -> list[Evidence]:
    """A class definition record plus one base-declaration record per base
    -- the exact shape `collect_class_definition_evidence` emits.
    """

    symbol = f"{module}.{name}"
    records = [_evidence(symbol=symbol, subject=name, category=EvidenceCategory.CLASS_DEFINITION)]
    records.extend(
        _evidence(symbol=symbol, subject=base, category=EvidenceCategory.CLASS_BASE_DECLARATION)
        for base in bases
    )
    return records


def _hook(class_name: str, hook: str, module: str = "erpnext.mod") -> Evidence:
    return _evidence(
        symbol=f"{module}.{class_name}.{hook}",
        subject=hook,
        category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
    )


def test_structural_evidence_is_neither_measured_nor_skipped() -> None:
    # Requirement 3. Class definitions are topology, not signal. Letting
    # them reach the matrix's default-deny would file them as "we could
    # not measure this", which is the wrong claim -- nobody tried, because
    # there is nothing there to measure. A declared gap that is not a gap
    # devalues the ones that are.
    records = [*_class("A", "Document"), *_class("B", "Document")]
    result = aggregate_patterns(_request(*records))

    reported = {pattern.evidence_category for pattern in result.patterns}
    skipped = {entry.evidence_category for entry in result.skipped_aggregations}
    structural = {EvidenceCategory.CLASS_DEFINITION, EvidenceCategory.CLASS_BASE_DECLARATION}

    assert reported & structural == set()
    assert skipped & structural == set()
    assert result.statistics.categories_present == 0


def test_structural_records_are_still_counted_as_consumed() -> None:
    # They were read, and the population depends on them -- reporting
    # otherwise would understate what the artifact was built from.
    records = [*_class("A", "Document"), *_class("B", "Document")]
    result = aggregate_patterns(_request(*records))

    assert result.statistics.evidence_records_consumed == len(records)


def test_lifecycle_hooks_are_measured_against_the_resolved_class_graph() -> None:
    records = [
        *_class("A", "Document"),
        *_class("B", "Document"),
        *_class("C", "B"),
        *_class("Unrelated"),
        _hook("A", "validate"),
        _hook("B", "validate"),
    ]
    result = aggregate_patterns(_request(*records))

    hooks = [
        pattern
        for pattern in result.patterns
        if pattern.evidence_category is EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK
    ]
    assert len(hooks) == 1
    # A, B and C descend from Document; `Unrelated` does not.
    assert hooks[0].population == 3
    assert hooks[0].occurrences == 2
    assert hooks[0].support == 2 / 3


def test_a_supporting_corpus_enlarges_the_population_without_joining_it() -> None:
    # The cross-repository case, in miniature. `Mixin` lives in frappe and
    # completes ERPNext's chain; it must not itself be counted.
    supporting = EvidenceSet(
        evidence_set_id="evset-frappe",
        schema_version="1.0",
        repository=CanonicalRepository.FRAPPE,
        version="v15.103.1",
        commit=_COMMIT,
        extracted_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=tuple(_class("Mixin", "Document", module="frappe.utils")),
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=2
        ),
    )
    records = [*_class("A", "Document"), *_class("B", "Mixin"), _hook("A", "validate")]

    alone = aggregate_patterns(_request(*records, min_occurrences=1))
    with_support = aggregate_patterns(
        AggregationRequest(
            evidence_set=_evidence_set(*records),
            supporting_evidence_sets=(supporting,),
            min_occurrences=1,
            correlation_id="corr-1",
            requested_by="test-suite",
        )
    )

    def population(result: PatternSet) -> int:
        return next(
            pattern.population
            for pattern in result.patterns
            if pattern.evidence_category is EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK
        )

    assert population(alone) == 1  # only A resolves
    assert population(with_support) == 2  # B now resolves through frappe's Mixin
    # frappe's own Mixin is never counted into ERPNext's population.
    assert all(pattern.repository is CanonicalRepository.ERPNEXT for pattern in with_support.patterns)


def test_resolution_provenance_records_a_single_corpus_run() -> None:
    records = [*_class("A", "Document"), _hook("A", "validate")]
    result = aggregate_patterns(_request(*records, min_occurrences=1))

    provenance = result.resolution_provenance
    assert provenance is not None
    assert provenance.strategy is ResolutionStrategy.SINGLE_CORPUS
    assert provenance.supporting_corpora == ()
    assert provenance.measured_corpus.repository is CanonicalRepository.ERPNEXT
    assert provenance.measured_corpus.commit == _COMMIT


def test_resolution_provenance_records_every_supporting_corpus() -> None:
    supporting = EvidenceSet(
        evidence_set_id="evset-frappe",
        schema_version="1.0",
        repository=CanonicalRepository.FRAPPE,
        version="v15.103.1",
        commit=_COMMIT,
        extracted_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=tuple(_class("Mixin", "Document", module="frappe.utils")),
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=2
        ),
    )
    records = [*_class("A", "Document"), _hook("A", "validate")]
    result = aggregate_patterns(
        AggregationRequest(
            evidence_set=_evidence_set(*records),
            supporting_evidence_sets=(supporting,),
            min_occurrences=1,
            correlation_id="corr-1",
            requested_by="test-suite",
        )
    )

    provenance = result.resolution_provenance
    assert provenance is not None
    assert provenance.strategy is ResolutionStrategy.MULTI_CORPUS
    assert [ref.repository for ref in provenance.supporting_corpora] == [CanonicalRepository.FRAPPE]
    assert provenance.supporting_corpora[0].version == "v15.103.1"


def test_provenance_is_absent_when_no_population_needed_resolution() -> None:
    # `None` means "no population in this artifact was derived from the
    # class graph" -- a statement, not a missing value.
    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a"), *_whitelisted("erpnext.api.b")))

    assert result.resolution_provenance is None


def test_provenance_counts_the_unresolved_residue() -> None:
    records = [*_class("A", "Document"), *_class("E", "Exception"), _hook("A", "validate")]
    result = aggregate_patterns(_request(*records, min_occurrences=1))

    assert result.resolution_provenance is not None
    assert result.resolution_provenance.unresolved_bases_count == 1


def test_a_matrix_declared_skip_still_reports_its_blocker(monkeypatch: pytest.MonkeyPatch) -> None:
    # No category is matrix-skipped since Sprint 22 closed the last one,
    # so this path is exercised against a substituted registry rather than
    # deleted -- it is the mechanism that keeps a *future* declared gap
    # reportable.
    import aggregation.engine as engine_module

    blocked = PopulationBasis(
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        status=AggregationStatus.SKIPPED_NO_POPULATION,
        description="stand-in",
        blocker="a stated, disclosed blocker",
    )
    monkeypatch.setattr(engine_module, "get_population_basis", lambda category: blocked)

    result = aggregate_patterns(_request(*_whitelisted("erpnext.api.a")))

    assert result.skipped_aggregations[0].reason == "a stated, disclosed blocker"
    assert result.patterns == ()


# -- Numerator / population alignment, end to end (Sprint 22, Commit 7) ----------------------------------


def _lifecycle_pattern(result: PatternSet, subject: str = "validate") -> Pattern | None:
    for pattern in result.patterns:
        if (
            pattern.evidence_category is EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK
            and pattern.subject == subject
        ):
            return pattern
    return None


def test_a_hook_on_a_non_controller_does_not_reach_the_numerator() -> None:
    # `Helper` defines a method named `validate` but descends from
    # nothing. Before this fix it inflated the numerator against a
    # population it was never part of.
    records = [
        *_class("Controller", "Document"),
        *_class("Helper"),
        _hook("Controller", "validate"),
        _hook("Helper", "validate"),
    ]
    result = aggregate_patterns(_request(*records, min_occurrences=1))

    pattern = _lifecycle_pattern(result)
    assert pattern is not None
    assert pattern.occurrences == 1
    assert pattern.population == 1
    assert pattern.support == 1.0


def test_a_mixed_corpus_produces_the_aligned_numerator() -> None:
    records = [
        *_class("A", "Document"),
        *_class("B", "Document"),
        *_class("NotAController"),
        _hook("A", "validate"),
        _hook("B", "validate"),
        _hook("NotAController", "validate"),
    ]
    result = aggregate_patterns(_request(*records, min_occurrences=1))

    pattern = _lifecycle_pattern(result)
    assert pattern is not None
    assert (pattern.occurrences, pattern.population) == (2, 2)


def test_occurrences_can_never_exceed_population_through_this_path() -> None:
    # The shape that used to raise: many hook-bearing non-controllers
    # against a single real controller. Support must stay a share.
    records = [*_class("Only", "Document"), _hook("Only", "validate")]
    for index in range(25):
        records += [*_class(f"Fake{index}"), _hook(f"Fake{index}", "validate")]

    result = aggregate_patterns(_request(*records, min_occurrences=1))

    pattern = _lifecycle_pattern(result)
    assert pattern is not None
    assert pattern.occurrences <= pattern.population
    assert 0.0 <= pattern.support <= 1.0


def test_every_lifecycle_pattern_satisfies_the_invariant() -> None:
    records = [
        *_class("A", "Document"),
        *_class("B", "A"),
        *_class("Loose"),
        _hook("A", "validate"),
        _hook("B", "on_submit"),
        _hook("Loose", "on_trash"),
    ]
    result = aggregate_patterns(_request(*records, min_occurrences=1))

    for pattern in result.patterns:
        assert 0 <= pattern.occurrences <= pattern.population
        assert 0.0 <= pattern.support <= 1.0
    # `Loose` contributes nothing at all, not even a below-threshold entry
    # under its own subject.
    assert _lifecycle_pattern(result, "on_trash") is None


def test_a_supporting_corpus_never_contributes_an_occurrence() -> None:
    # It enlarges the population by resolving ancestry, and contributes no
    # hook of its own even when it has one.
    supporting = EvidenceSet(
        evidence_set_id="evset-frappe",
        schema_version="2.0",
        repository=CanonicalRepository.FRAPPE,
        version="v15.103.1",
        commit=_COMMIT,
        extracted_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=(
            *_class("Mixin", "Document", module="frappe.utils"),
            _hook("Mixin", "validate", module="frappe.utils"),
        ),
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=3
        ),
    )
    records = [*_class("A", "Document"), *_class("B", "Mixin"), _hook("A", "validate")]

    result = aggregate_patterns(
        AggregationRequest(
            evidence_set=_evidence_set(*records),
            supporting_evidence_sets=(supporting,),
            min_occurrences=1,
            correlation_id="corr-1",
            requested_by="test-suite",
        )
    )

    pattern = _lifecycle_pattern(result)
    assert pattern is not None
    assert pattern.population == 2  # A and B, resolved through frappe's Mixin
    assert pattern.occurrences == 1  # frappe's own Mixin.validate is not counted
    for supporting_id in pattern.supporting_evidence_ids:
        assert "frappe.utils" not in supporting_id
