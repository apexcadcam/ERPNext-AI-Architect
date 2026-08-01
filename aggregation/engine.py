"""Pattern Aggregation Engine's own orchestration.

Implements Pattern Aggregation Engine Architecture Specification v1.0
§10 exactly: partition, dispatch, resolve, group, threshold, sort and
assemble. Composition only -- the Capability Matrix lives in
`aggregation.population`, population arithmetic in
`aggregation.resolvers`, and neither is reimplemented here.

**No stage raises on ordinary data (§10).** A category with no registered
resolver, or one whose resolver returns a zero population, becomes a
recorded `SkippedAggregation` in the returned artifact -- never an
exception, never a fabricated denominator, and never a division by zero.
The one division in this module is guarded by an explicit zero check
before it, and by `Pattern.population`'s own `ge=1` constraint after it.

**One precondition does raise, and it is not a stage** (ADR-0017). Before
any stage runs, `aggregate_patterns` refuses a request whose supporting
corpora do not meet the measured repository's registered closure. That is
not a statement about the data: it is a statement that the *inputs* are
insufficient to compute a correct denominator at all, and recording it as
a `SkippedAggregation` would file a caller error as a platform
limitation. The distinction §10 draws is between data the engine cannot
measure -- recorded -- and a request the engine must not answer --
refused.

Zero Reasoning Engine calls: counting is arithmetic.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from evidence.contract import Evidence, EvidenceCategory, EvidenceSet

from aggregation.admission import require_supporting_closure
from aggregation.contract import (
    AggregationRequest,
    AggregationStatistics,
    AggregationStatus,
    CorpusRef,
    ObservedBelowThreshold,
    Pattern,
    PatternSet,
    ResolutionProvenance,
    ResolutionStrategy,
    SkippedAggregation,
    ThresholdSpec,
)
from aggregation.inheritance import ClassDescentResult, resolve_descent
from aggregation.population import STRUCTURAL_CATEGORIES, get_population_basis
from aggregation.resolvers import (
    CONTROLLER_POPULATION_ROOT,
    OCCURRENCE_FILTERS,
    POPULATION_RESOLVERS,
    PopulationContext,
)

#: §7.7's fixed schema version for this Sprint's contract shape. Bumped
#: only when `Pattern`'s or `PatternSet`'s own fields change.
#:
#: `2.0` from Sprint 22: `PatternSet` gained `resolution_provenance`, so
#: the persisted metadata sidecar gains a key. An old reader given a `2.0`
#: artifact rejects it loudly -- `PatternSet` is `extra="forbid"` -- which
#: is the correct outcome, since silently ignoring the field would mean
#: reading a population without the record of how it was reached.
_SCHEMA_VERSION = "2.0"

#: §7.6's minimum-occurrence threshold, registered rather than inlined --
#: the same Rule Metadata Registry discipline
#: `evaluation.rules.RULE_THRESHOLDS` and
#: `recommendation.scoring.PRIORITY_WEIGHTS` already established.
MIN_OCCURRENCES_THRESHOLD = ThresholdSpec(
    threshold_name="min_occurrences",
    value=2,
    calibration_status="heuristic_default",
    justification=(
        "A subject observed exactly once is an anecdote, not a pattern -- `staticmethod` occurs "
        "1/705 in real ERPNext v15.102.0. Disclosed as a judgement call rather than a measured "
        "one: no production PatternSet data exists yet to calibrate it against. Revisited once "
        "real aggregation output accumulates."
    ),
)


def _partition_by_category(evidence: tuple[Evidence, ...]) -> dict[EvidenceCategory, list[Evidence]]:
    """§10 step 1. Groups records by their own category, preserving each
    category's internal record order (the engine's own sort is applied
    later, centrally, to the assembled patterns).

    **Structural categories are excluded here rather than skipped later.**
    `CLASS_DEFINITION` and `CLASS_BASE_DECLARATION` are topology: they
    describe the class graph so a population can be resolved, and are not
    observations anyone measures a share of. Letting them reach the
    matrix's default-deny would file them as `SKIPPED_NO_POPULATION` --
    "we could not measure this" -- which is the wrong claim. Nobody
    tried, because there is nothing there to measure, and a declared gap
    that is not a gap devalues the ones that are.
    """

    partitioned: dict[EvidenceCategory, list[Evidence]] = defaultdict(list)
    for record in evidence:
        if record.category in STRUCTURAL_CATEGORIES:
            continue
        partitioned[record.category].append(record)
    return dict(partitioned)


def _compute_pattern_id(
    repository: str, version: str, commit: str, category: EvidenceCategory, subject: str
) -> str:
    """§7.3's content-addressed identity. The same measured fact at the
    same commit always yields the same id, in any run -- never a UUID,
    which would make two identical runs look different.
    """

    payload = "|".join([repository, version, commit, category.value, subject])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _skip(category: EvidenceCategory, reason: str, records_present: int) -> SkippedAggregation:
    return SkippedAggregation(
        evidence_category=category,
        status=AggregationStatus.SKIPPED_NO_POPULATION,
        reason=reason,
        evidence_records_present=records_present,
    )


def _aggregate_category(
    category: EvidenceCategory,
    records: list[Evidence],
    evidence_set: EvidenceSet,
    min_occurrences: int,
    context: PopulationContext,
) -> tuple[list[Pattern], list[ObservedBelowThreshold], SkippedAggregation | None]:
    """§10 steps 2-5 for one category.

    Returns `(patterns, below_threshold, skipped)` -- exactly one of
    `skipped` or the two lists carries the outcome, never both.
    """

    basis = get_population_basis(category)
    if basis is None:
        # §8's default-deny: a category with no matrix entry is not
        # aggregatable. Reached only by a future Evidence category added
        # without a corresponding matrix row -- degrades to a recorded
        # skip rather than a fabricated denominator.
        return [], [], _skip(category, "no population basis is registered for this category", len(records))

    if basis.status is not AggregationStatus.AGGREGATED:
        return [], [], _skip(category, basis.blocker or basis.description, len(records))

    resolver = POPULATION_RESOLVERS.get(category)
    if resolver is None:
        # The matrix declares this category aggregatable but no resolver
        # backs it. A test cross-checks the two registries so this is
        # unreachable today; kept because silently proceeding would mean
        # inventing a denominator.
        return [], [], _skip(category, "no population resolver is registered for this category", len(records))

    population, population_description = resolver(records, context)
    if population == 0:
        # Never divide by zero, and never publish a ratio against an
        # empty population.
        return [], [], _skip(category, "the resolved population is empty", len(records))

    # **The numerator must be drawn from the population, not merely
    # compared against it.** A category whose records do not themselves
    # define its population -- CONTROLLER_LIFECYCLE_HOOK is the first --
    # can otherwise count symbols the denominator never contained, which
    # makes `support` a ratio between two different sets: silently
    # inflated, and outright invalid once occurrences exceed population.
    #
    # Enforced by construction here rather than checked afterwards.
    # Clamping a support above 1.0 back to 1.0 would hide the same defect
    # while keeping the number wrong.
    occurrence_filter = OCCURRENCE_FILTERS.get(category)
    countable = records if occurrence_filter is None else occurrence_filter(records, context)

    symbols_by_subject: dict[str, set[str]] = defaultdict(set)
    evidence_ids_by_subject: dict[str, set[str]] = defaultdict(set)
    for record in countable:
        symbols_by_subject[record.subject].add(record.symbol)
        evidence_ids_by_subject[record.subject].add(record.evidence_id)

    patterns: list[Pattern] = []
    below_threshold: list[ObservedBelowThreshold] = []
    for subject, symbols in symbols_by_subject.items():
        occurrences = len(symbols)
        if occurrences < min_occurrences:
            below_threshold.append(
                ObservedBelowThreshold(evidence_category=category, subject=subject, occurrences=occurrences)
            )
            continue
        patterns.append(
            Pattern(
                pattern_id=_compute_pattern_id(
                    evidence_set.repository.value,
                    evidence_set.version,
                    evidence_set.commit,
                    category,
                    subject,
                ),
                evidence_category=category,
                subject=subject,
                occurrences=occurrences,
                population=population,
                support=occurrences / population,
                population_description=population_description,
                supporting_evidence_ids=tuple(sorted(evidence_ids_by_subject[subject])),
                repository=evidence_set.repository,
                version=evidence_set.version,
                commit=evidence_set.commit,
            )
        )

    return patterns, below_threshold, None


#: Categories whose population is derived from the resolved class graph
#: rather than from their own records. Only these make
#: `ResolutionProvenance` meaningful.
_DESCENT_DERIVED_CATEGORIES = frozenset({EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK})


def _corpus_ref(evidence_set: EvidenceSet) -> CorpusRef:
    return CorpusRef(
        repository=evidence_set.repository,
        version=evidence_set.version,
        commit=evidence_set.commit,
    )


def _resolution_provenance(
    request: AggregationRequest,
    descent: ClassDescentResult,
    aggregated_categories: set[EvidenceCategory],
) -> ResolutionProvenance | None:
    """Inheritance Resolution §6. Records how a population was reached --
    but only when a population actually was reached that way.

    Returns `None` when no aggregated category derived its denominator
    from the class graph, which is the documented meaning of the absent
    field rather than a placeholder: 510 and 492 are both defensible
    ERPNext populations differing only by what was supplied, so an
    artifact that quotes one without recording its inputs cannot be
    reproduced. An artifact that quotes neither has nothing to record.
    """

    if not aggregated_categories & _DESCENT_DERIVED_CATEGORIES:
        return None

    supporting = request.supporting_evidence_sets
    return ResolutionProvenance(
        measured_corpus=_corpus_ref(request.evidence_set),
        supporting_corpora=tuple(_corpus_ref(corpus) for corpus in supporting),
        strategy=(ResolutionStrategy.MULTI_CORPUS if supporting else ResolutionStrategy.SINGLE_CORPUS),
        unresolved_bases_count=len(descent.unresolved_bases),
    )


def _pattern_sort_key(pattern: Pattern) -> tuple[str, int, str]:
    """§11's mandatory ordering: category, then most frequent first, ties
    broken alphabetically -- never dict insertion order.
    """

    return (pattern.evidence_category.value, -pattern.occurrences, pattern.subject)


def _below_threshold_sort_key(observed: ObservedBelowThreshold) -> tuple[str, int, str]:
    return (observed.evidence_category.value, -observed.occurrences, observed.subject)


def aggregate_patterns(request: AggregationRequest) -> PatternSet:
    """§16's public entry point. Composes §10's six steps over the
    persisted `EvidenceSet` the request carries.

    Never reads a source tree, never re-runs extraction, and never
    imports `evidence.engine` -- this engine consumes persisted Evidence
    only (§13).
    """

    evidence_set = request.evidence_set

    # **First statement, before anything is resolved or counted**
    # (ADR-0017 §6). An unmet supporting-corpus closure means the
    # population this run would compute is knowably incomplete, and an
    # incomplete population does not fail loudly -- it publishes a
    # smaller, plausible denominator and then silently filters valid
    # occurrences out of the numerator drawn against it. Refusing here
    # rather than validating the result afterwards is what makes 492
    # unpublishable for `erpnext`: no descent is resolved, no `Pattern`
    # is built, and no `PatternSet` exists to inspect.
    #
    # A generic lookup, exactly like `get_population_basis(category)`
    # below. The closure is data in `aggregation.admission`; this engine
    # never names a repository.
    require_supporting_closure(
        evidence_set.repository,
        frozenset(corpus.repository for corpus in request.supporting_evidence_sets),
    )

    partitioned = _partition_by_category(evidence_set.evidence)

    # Resolved once, before the category loop, and shared by every
    # resolver that needs it. Doing it per-category would rebuild the same
    # graph repeatedly and -- worse -- let the population quoted in a
    # `Pattern` and the residue quoted in `ResolutionProvenance` come from
    # two separate computations that could disagree.
    descent = resolve_descent(evidence_set, request.supporting_evidence_sets, root=CONTROLLER_POPULATION_ROOT)
    context = PopulationContext(
        measured=evidence_set,
        supporting=request.supporting_evidence_sets,
        descent=descent,
    )

    patterns: list[Pattern] = []
    below_threshold: list[ObservedBelowThreshold] = []
    skipped: list[SkippedAggregation] = []
    aggregated_categories: set[EvidenceCategory] = set()

    for category in sorted(partitioned, key=lambda item: item.value):
        category_patterns, category_below, category_skip = _aggregate_category(
            category, partitioned[category], evidence_set, request.min_occurrences, context
        )
        if category_skip is not None:
            skipped.append(category_skip)
            continue
        aggregated_categories.add(category)
        patterns.extend(category_patterns)
        below_threshold.extend(category_below)

    sorted_patterns = tuple(sorted(patterns, key=_pattern_sort_key))
    sorted_below = tuple(sorted(below_threshold, key=_below_threshold_sort_key))
    sorted_skipped = tuple(sorted(skipped, key=lambda item: item.evidence_category.value))

    statistics = AggregationStatistics(
        evidence_records_consumed=len(evidence_set.evidence),
        categories_present=len(partitioned),
        categories_aggregated=len(partitioned) - len(sorted_skipped),
        categories_skipped=len(sorted_skipped),
        patterns_produced=len(sorted_patterns),
        subjects_below_threshold=len(sorted_below),
    )

    return PatternSet(
        pattern_set_id=str(uuid.uuid4()),
        resolution_provenance=_resolution_provenance(request, descent, aggregated_categories),
        schema_version=_SCHEMA_VERSION,
        source_evidence_set_id=evidence_set.evidence_set_id,
        repository=evidence_set.repository,
        version=evidence_set.version,
        commit=evidence_set.commit,
        aggregated_at=datetime.now(UTC).isoformat(),
        correlation_id=request.correlation_id,
        patterns=sorted_patterns,
        skipped_aggregations=sorted_skipped,
        observed_below_threshold=sorted_below,
        statistics=statistics,
    )
