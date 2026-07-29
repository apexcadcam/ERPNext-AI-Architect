"""Tests for `aggregation.contract` (Pattern Aggregation Engine Architecture Specification v1.0 §7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evidence.contract import (
    CanonicalRepository,
    EvidenceCategory,
    EvidenceSet,
    EvidenceStatistics,
)

from aggregation.contract import (
    AggregationRequest,
    AggregationStatistics,
    AggregationStatus,
    CorpusRef,
    ObservedBelowThreshold,
    Pattern,
    PatternSet,
    PopulationBasis,
    ResolutionProvenance,
    ResolutionStrategy,
    SkippedAggregation,
    ThresholdSpec,
)

# -- Fixture builders --------------------------------------------------------------------------------

_COMMIT = "1d14ba16398db3a220873509565c60f2932bed81"


def _pattern(**overrides: object) -> Pattern:
    defaults: dict[str, object] = {
        "pattern_id": "a" * 64,
        "evidence_category": EvidenceCategory.WHITELISTED_API_DECORATION,
        "subject": "frappe.validate_and_sanitize_search_inputs",
        "occurrences": 59,
        "population": 705,
        "support": 59 / 705,
        "population_description": "distinct symbols carrying a whitelist-family decorator",
        "supporting_evidence_ids": ("b" * 64,),
        "repository": CanonicalRepository.ERPNEXT,
        "version": "v15.102.0",
        "commit": _COMMIT,
    }
    defaults.update(overrides)
    return Pattern(**defaults)  # type: ignore[arg-type]


def _evidence_set() -> EvidenceSet:
    return EvidenceSet(
        evidence_set_id="evset-1",
        schema_version="1.0",
        repository=CanonicalRepository.ERPNEXT,
        version="v15.102.0",
        commit=_COMMIT,
        extracted_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=(),
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=0, files_skipped=0, files_failed=0, evidence_extracted=0
        ),
    )


def _statistics() -> AggregationStatistics:
    return AggregationStatistics(
        evidence_records_consumed=1245,
        categories_present=2,
        categories_aggregated=1,
        categories_skipped=1,
        patterns_produced=2,
        subjects_below_threshold=4,
    )


def _pattern_set(**overrides: object) -> PatternSet:
    defaults: dict[str, object] = {
        "pattern_set_id": "pset-1",
        "schema_version": "1.0",
        "source_evidence_set_id": "evset-1",
        "repository": CanonicalRepository.ERPNEXT,
        "version": "v15.102.0",
        "commit": _COMMIT,
        "aggregated_at": "2026-07-27T13:00:00+00:00",
        "correlation_id": "corr-1",
        "patterns": (_pattern(),),
        "skipped_aggregations": (),
        "observed_below_threshold": (),
        "statistics": _statistics(),
    }
    defaults.update(overrides)
    return PatternSet(**defaults)  # type: ignore[arg-type]


# -- AggregationStatus -------------------------------------------------------------------------------


def test_aggregation_status_defines_exactly_the_two_documented_values() -> None:
    # SS7.1: a third value is added only when a third real situation exists.
    assert {member.value for member in AggregationStatus} == {"aggregated", "skipped_no_population"}


def test_aggregation_status_has_no_verified_or_approved_state() -> None:
    # Verification is Sprint 24's own, separate stage -- no state here anticipates it.
    values = {member.value for member in AggregationStatus}
    for forbidden in ("verified", "approved", "candidate", "rejected", "pending_review"):
        assert forbidden not in values


# -- PopulationBasis ---------------------------------------------------------------------------------


def test_population_basis_round_trips_through_json() -> None:
    basis = PopulationBasis(
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        status=AggregationStatus.AGGREGATED,
        description="distinct symbols carrying a whitelist-family decorator",
    )
    assert PopulationBasis.model_validate_json(basis.model_dump_json()) == basis


def test_population_basis_blocker_defaults_to_none() -> None:
    basis = PopulationBasis(
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        status=AggregationStatus.AGGREGATED,
        description="x",
    )
    assert basis.blocker is None


def test_population_basis_accepts_a_blocker_for_a_skipped_category() -> None:
    basis = PopulationBasis(
        evidence_category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        status=AggregationStatus.SKIPPED_NO_POPULATION,
        description="distinct Document subclasses",
        blocker="requires a class-definition Evidence category (Sprint 22)",
    )
    assert basis.blocker is not None


def test_population_basis_is_frozen() -> None:
    basis = PopulationBasis(
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        status=AggregationStatus.AGGREGATED,
        description="x",
    )
    with pytest.raises(ValidationError):
        basis.description = "other"


def test_population_basis_requires_a_description() -> None:
    with pytest.raises(ValidationError):
        PopulationBasis(
            evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
            status=AggregationStatus.AGGREGATED,
            description="",
        )


def test_population_basis_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PopulationBasis(
            evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
            status=AggregationStatus.AGGREGATED,
            description="x",
            unexpected="field",  # type: ignore[call-arg]
        )


# -- Pattern -- the three constraints this commit exists to guarantee --------------------------------


def test_pattern_has_no_confidence_field() -> None:
    # SS6: `confidence` already means something else in this project
    # (evaluation.contract.Confidence -- inferential strength). What this
    # engine computes is frequency, which is `support`. The name stays
    # reserved for Sprint 24's Verification stage.
    assert "confidence" not in Pattern.model_fields


def test_pattern_rejects_a_zero_population() -> None:
    # SS5's "no population, no Pattern" holds at the type level: a zero
    # denominator is unrepresentable, so no future resolver bug can
    # produce one.
    with pytest.raises(ValidationError):
        _pattern(population=0)


def test_pattern_rejects_a_negative_population() -> None:
    with pytest.raises(ValidationError):
        _pattern(population=-1)


def test_pattern_rejects_support_above_one() -> None:
    with pytest.raises(ValidationError):
        _pattern(support=1.5)


def test_pattern_rejects_support_below_zero() -> None:
    with pytest.raises(ValidationError):
        _pattern(support=-0.1)


def test_pattern_accepts_the_inclusive_support_bounds() -> None:
    assert _pattern(support=0.0, occurrences=1).support == 0.0
    assert _pattern(support=1.0, occurrences=705).support == 1.0


# -- Pattern -- general contract behavior --------------------------------------------------------------


def test_pattern_round_trips_through_json() -> None:
    pattern = _pattern()
    assert Pattern.model_validate_json(pattern.model_dump_json()) == pattern


def test_pattern_is_frozen() -> None:
    pattern = _pattern()
    with pytest.raises(ValidationError):
        pattern.subject = "other"


def test_pattern_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _pattern(unexpected="field")


def test_pattern_rejects_zero_occurrences() -> None:
    with pytest.raises(ValidationError):
        _pattern(occurrences=0)


def test_pattern_requires_at_least_one_supporting_evidence_id() -> None:
    # Full traceability (SS5): a measurement with no evidence behind it is
    # not a measurement.
    with pytest.raises(ValidationError):
        _pattern(supporting_evidence_ids=())


def test_pattern_requires_a_population_description() -> None:
    # A number orphaned from what it counted is meaningless.
    with pytest.raises(ValidationError):
        _pattern(population_description="")


def test_pattern_has_no_rule_or_recommendation_shaped_field() -> None:
    # SS4: a Pattern states what is, never what to do. Candidate Rules are
    # Sprint 23's own, separate stage.
    field_names = set(Pattern.model_fields)
    for forbidden in ("rule", "rule_id", "recommendation", "severity", "priority", "action", "remediation"):
        assert forbidden not in field_names


# -- SkippedAggregation ------------------------------------------------------------------------------


def _skipped(**overrides: object) -> SkippedAggregation:
    defaults: dict[str, object] = {
        "evidence_category": EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "status": AggregationStatus.SKIPPED_NO_POPULATION,
        "reason": "population is not derivable from persisted Evidence alone",
        "evidence_records_present": 476,
    }
    defaults.update(overrides)
    return SkippedAggregation(**defaults)  # type: ignore[arg-type]


def test_skipped_aggregation_round_trips_through_json() -> None:
    skipped = _skipped()
    assert SkippedAggregation.model_validate_json(skipped.model_dump_json()) == skipped


def test_skipped_aggregation_carries_a_machine_readable_status() -> None:
    # SS9: a consumer must be able to act on this programmatically, not
    # parse a prose string.
    assert _skipped().status is AggregationStatus.SKIPPED_NO_POPULATION


def test_skipped_aggregation_records_how_many_records_were_present() -> None:
    # The difference between "no records" and "records but no denominator".
    assert _skipped().evidence_records_present == 476


def test_skipped_aggregation_allows_zero_records_present() -> None:
    assert _skipped(evidence_records_present=0).evidence_records_present == 0


def test_skipped_aggregation_rejects_negative_records_present() -> None:
    with pytest.raises(ValidationError):
        _skipped(evidence_records_present=-1)


def test_skipped_aggregation_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        _skipped(reason="")


def test_skipped_aggregation_is_frozen() -> None:
    skipped = _skipped()
    with pytest.raises(ValidationError):
        skipped.reason = "other"


def test_skipped_aggregation_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _skipped(unexpected="field")


# -- ObservedBelowThreshold --------------------------------------------------------------------------


def test_observed_below_threshold_round_trips_through_json() -> None:
    observed = ObservedBelowThreshold(
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        subject="staticmethod",
        occurrences=1,
    )
    assert ObservedBelowThreshold.model_validate_json(observed.model_dump_json()) == observed


def test_observed_below_threshold_rejects_zero_occurrences() -> None:
    # It was observed, so it occurred at least once by definition.
    with pytest.raises(ValidationError):
        ObservedBelowThreshold(
            evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
            subject="staticmethod",
            occurrences=0,
        )


def test_observed_below_threshold_is_frozen() -> None:
    observed = ObservedBelowThreshold(
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        subject="staticmethod",
        occurrences=1,
    )
    with pytest.raises(ValidationError):
        observed.occurrences = 2


# -- ThresholdSpec -----------------------------------------------------------------------------------


def test_threshold_spec_round_trips_through_json() -> None:
    spec = ThresholdSpec(
        threshold_name="min_occurrences",
        value=2,
        calibration_status="heuristic_default",
        justification="a subject seen exactly once is an anecdote, not a pattern",
    )
    assert ThresholdSpec.model_validate_json(spec.model_dump_json()) == spec


def test_threshold_spec_requires_a_justification() -> None:
    with pytest.raises(ValidationError):
        ThresholdSpec(
            threshold_name="min_occurrences",
            value=2,
            calibration_status="heuristic_default",
            justification="",
        )


def test_threshold_spec_requires_a_calibration_status() -> None:
    with pytest.raises(ValidationError):
        ThresholdSpec(threshold_name="min_occurrences", value=2, calibration_status="", justification="x")


# -- AggregationRequest ------------------------------------------------------------------------------


def _request(**overrides: object) -> AggregationRequest:
    defaults: dict[str, object] = {
        "evidence_set": _evidence_set(),
        "correlation_id": "corr-1",
        "requested_by": "test-suite",
    }
    defaults.update(overrides)
    return AggregationRequest(**defaults)  # type: ignore[arg-type]


def test_aggregation_request_wraps_an_evidence_set() -> None:
    assert _request().evidence_set.evidence_set_id == "evset-1"


def test_aggregation_request_min_occurrences_defaults_to_two() -> None:
    # SS7.6's documented default; Commit 5 registers it as a ThresholdSpec.
    assert _request().min_occurrences == 2


def test_aggregation_request_rejects_min_occurrences_below_one() -> None:
    with pytest.raises(ValidationError):
        _request(min_occurrences=0)


def test_aggregation_request_is_frozen() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        request.min_occurrences = 5


def test_aggregation_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _request(unexpected="field")


# -- supporting_evidence_sets (Sprint 22, Inheritance Resolution §5) ------------------------------------


def _frappe_evidence_set() -> EvidenceSet:
    return _evidence_set().model_copy(
        update={
            "evidence_set_id": "evset-frappe",
            "repository": CanonicalRepository.FRAPPE,
            "version": "v15.103.1",
        }
    )


def test_supporting_evidence_sets_defaults_to_empty() -> None:
    # Single-corpus aggregation is unchanged: the field exists but is
    # absent unless a caller supplies one.
    assert _request().supporting_evidence_sets == ()


def test_supporting_evidence_sets_accepts_a_different_repository() -> None:
    request = _request(supporting_evidence_sets=(_frappe_evidence_set(),))
    assert len(request.supporting_evidence_sets) == 1
    assert request.supporting_evidence_sets[0].repository is CanonicalRepository.FRAPPE
    # The subject is untouched by the presence of context.
    assert request.evidence_set.repository is CanonicalRepository.ERPNEXT


def test_supporting_evidence_sets_rejects_the_measured_repository() -> None:
    # §5.3. Supplying a repository as its own resolution context reads as
    # though it does something and silently does nothing.
    with pytest.raises(ValidationError, match="subject"):
        _request(supporting_evidence_sets=(_evidence_set(),))


def test_supporting_evidence_sets_rejects_the_same_repository_twice() -> None:
    # Typically two versions of it -- under which a class name could
    # resolve against either, making descent ambiguous.
    other_version = _frappe_evidence_set().model_copy(update={"version": "v15.99.0"})
    with pytest.raises(ValidationError, match="ambiguous"):
        _request(supporting_evidence_sets=(_frappe_evidence_set(), other_version))


def test_supporting_evidence_sets_is_ordered_and_frozen() -> None:
    request = _request(supporting_evidence_sets=(_frappe_evidence_set(),))
    with pytest.raises(ValidationError):
        request.supporting_evidence_sets = ()


def test_aggregation_request_round_trips_with_supporting_sets() -> None:
    request = _request(supporting_evidence_sets=(_frappe_evidence_set(),))
    assert AggregationRequest.model_validate_json(request.model_dump_json()) == request


# -- CorpusRef ------------------------------------------------------------------------------------------


def _corpus_ref(**overrides: object) -> CorpusRef:
    defaults: dict[str, object] = {
        "repository": CanonicalRepository.ERPNEXT,
        "version": "v15.102.0",
        "commit": _COMMIT,
    }
    defaults.update(overrides)
    return CorpusRef(**defaults)  # type: ignore[arg-type]


def _frappe_ref() -> CorpusRef:
    return _corpus_ref(
        repository=CanonicalRepository.FRAPPE,
        version="v15.103.1",
        commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
    )


def test_corpus_ref_round_trips_through_json() -> None:
    ref = _corpus_ref()
    assert CorpusRef.model_validate_json(ref.model_dump_json()) == ref


def test_corpus_ref_requires_a_version_and_a_commit() -> None:
    # Repository alone is not an identity: the same repository at two
    # commits is two different bodies of evidence.
    with pytest.raises(ValidationError):
        _corpus_ref(version="")
    with pytest.raises(ValidationError):
        _corpus_ref(commit="")


def test_corpus_ref_is_frozen_and_rejects_unknown_fields() -> None:
    ref = _corpus_ref()
    with pytest.raises(ValidationError):
        ref.version = "v0"
    with pytest.raises(ValidationError):
        _corpus_ref(unexpected="field")


# -- ResolutionStrategy / ResolutionProvenance ----------------------------------------------------------


def test_resolution_strategy_defines_exactly_the_two_documented_values() -> None:
    assert {member.value for member in ResolutionStrategy} == {"single_corpus", "multi_corpus"}


def _provenance(**overrides: object) -> ResolutionProvenance:
    defaults: dict[str, object] = {
        "measured_corpus": _corpus_ref(),
        "supporting_corpora": (_frappe_ref(),),
        "strategy": ResolutionStrategy.MULTI_CORPUS,
        "unresolved_bases_count": 0,
    }
    defaults.update(overrides)
    return ResolutionProvenance(**defaults)  # type: ignore[arg-type]


def test_resolution_provenance_round_trips_through_json() -> None:
    provenance = _provenance()
    assert ResolutionProvenance.model_validate_json(provenance.model_dump_json()) == provenance


def test_single_corpus_strategy_requires_no_supporting_corpora() -> None:
    provenance = _provenance(supporting_corpora=(), strategy=ResolutionStrategy.SINGLE_CORPUS)
    assert provenance.supporting_corpora == ()


def test_single_corpus_strategy_rejects_supporting_corpora() -> None:
    # The label may not contradict the record -- `strategy` is exactly the
    # field a reader checks when they do not want to read the rest.
    with pytest.raises(ValidationError, match="multi_corpus"):
        _provenance(strategy=ResolutionStrategy.SINGLE_CORPUS)


def test_multi_corpus_strategy_rejects_an_empty_supporting_list() -> None:
    with pytest.raises(ValidationError, match="single_corpus"):
        _provenance(supporting_corpora=(), strategy=ResolutionStrategy.MULTI_CORPUS)


def test_resolution_provenance_rejects_the_measured_repository_as_support() -> None:
    with pytest.raises(ValidationError, match="measured repository"):
        _provenance(supporting_corpora=(_corpus_ref(),))


def test_resolution_provenance_records_the_unresolved_residue() -> None:
    # A base naming nothing in any supplied corpus (`object`, `Exception`,
    # a third-party class) is normal and expected; the count is recorded
    # rather than swallowed.
    assert _provenance(unresolved_bases_count=17).unresolved_bases_count == 17


def test_resolution_provenance_rejects_a_negative_residue() -> None:
    with pytest.raises(ValidationError):
        _provenance(unresolved_bases_count=-1)


def test_resolution_provenance_is_frozen_and_rejects_unknown_fields() -> None:
    provenance = _provenance()
    with pytest.raises(ValidationError):
        provenance.strategy = ResolutionStrategy.SINGLE_CORPUS
    with pytest.raises(ValidationError):
        _provenance(unexpected="field")


def test_resolution_provenance_carries_no_population_number() -> None:
    # It records *how* a population was reached, not what it came to --
    # the count itself already lives on Pattern.population, and storing
    # it twice would create two sources of truth for one number.
    fields = set(ResolutionProvenance.model_fields)
    for forbidden in ("population", "population_size", "descendants", "occurrences"):
        assert forbidden not in fields


# -- PatternSet.resolution_provenance -------------------------------------------------------------------


def test_pattern_set_resolution_provenance_defaults_to_none() -> None:
    # `None` reads "no population in this artifact required inheritance
    # resolution" -- true of every PatternSet produced up to v1.3.0.
    assert _pattern_set().resolution_provenance is None


def test_pattern_set_accepts_resolution_provenance() -> None:
    pattern_set = _pattern_set(resolution_provenance=_provenance())
    assert pattern_set.resolution_provenance is not None
    assert pattern_set.resolution_provenance.strategy is ResolutionStrategy.MULTI_CORPUS


def test_pattern_set_round_trips_with_resolution_provenance() -> None:
    pattern_set = _pattern_set(resolution_provenance=_provenance())
    assert PatternSet.model_validate_json(pattern_set.model_dump_json()) == pattern_set


def test_a_v1_pattern_set_payload_still_validates() -> None:
    # Backward expectation (Inheritance Resolution §7.2): a new reader
    # given a 1.0-shaped artifact -- one with no resolution_provenance
    # key at all -- still loads, because the field is optional.
    payload = _pattern_set().model_dump(mode="json")
    del payload["resolution_provenance"]
    assert PatternSet.model_validate(payload).resolution_provenance is None


# -- AggregationStatistics ---------------------------------------------------------------------------


def test_aggregation_statistics_round_trips_through_json() -> None:
    statistics = _statistics()
    assert AggregationStatistics.model_validate_json(statistics.model_dump_json()) == statistics


def test_aggregation_statistics_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        AggregationStatistics(
            evidence_records_consumed=-1,
            categories_present=0,
            categories_aggregated=0,
            categories_skipped=0,
            patterns_produced=0,
            subjects_below_threshold=0,
        )


# -- PatternSet ---------------------------------------------------------------------------------------


def test_pattern_set_round_trips_through_json() -> None:
    pattern_set = _pattern_set()
    assert PatternSet.model_validate_json(pattern_set.model_dump_json()) == pattern_set


def test_pattern_set_is_frozen() -> None:
    pattern_set = _pattern_set()
    with pytest.raises(ValidationError):
        pattern_set.correlation_id = "other"


def test_pattern_set_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _pattern_set(unexpected="field")


def test_pattern_set_traces_back_to_its_source_evidence_set() -> None:
    assert _pattern_set().source_evidence_set_id == "evset-1"


def test_pattern_set_accepts_zero_patterns_alongside_a_populated_skip_list() -> None:
    # SS7.7: this is a valid, meaningful, successful result -- "nothing was
    # measurable, and here is precisely why" -- not a failure.
    pattern_set = _pattern_set(
        patterns=(),
        skipped_aggregations=(_skipped(),),
        statistics=AggregationStatistics(
            evidence_records_consumed=476,
            categories_present=1,
            categories_aggregated=0,
            categories_skipped=1,
            patterns_produced=0,
            subjects_below_threshold=0,
        ),
    )
    assert pattern_set.patterns == ()
    assert len(pattern_set.skipped_aggregations) == 1


def test_pattern_set_has_no_candidate_rule_or_verification_field() -> None:
    # SS4: Candidate Rules are Sprint 23, Verification is Sprint 24 --
    # neither is anticipated in this schema.
    field_names = set(PatternSet.model_fields)
    for forbidden in ("candidates", "candidate_rules", "rules", "verified", "verification", "approvals"):
        assert forbidden not in field_names


def test_no_contract_model_has_an_llm_shaped_field() -> None:
    # SS4/SS5: zero Reasoning Engine involvement anywhere in this package.
    models = (
        Pattern,
        PatternSet,
        SkippedAggregation,
        ObservedBelowThreshold,
        PopulationBasis,
        AggregationRequest,
        AggregationStatistics,
        ThresholdSpec,
    )
    forbidden = {"prompt", "completion", "model", "temperature", "reasoning", "llm", "tokens"}
    for model in models:
        assert set(model.model_fields) & forbidden == set(), model.__name__
