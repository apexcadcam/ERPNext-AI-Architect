"""Pattern Aggregation Engine's own contract: the one fixed set of types
every stage produces and consumes, and the final `PatternSet` artifact
callers receive.

Implements Pattern Aggregation Engine Architecture Specification v1.0 §7
in full. Every model is frozen, matching every other contract in this
project (`evidence.contract.EvidenceSet`,
`evaluation.contract.ArchitectureEvaluation`, ...).

**No field named `confidence` exists anywhere in this module, by
deliberate design (§6).** `evaluation.contract.Confidence` already exists
in this project as a closed enum meaning *how directly cited evidence
supports a conclusion* -- a judgement about inferential strength. What
this engine computes is a different quantity entirely: how frequently an
observation occurs across a defined population. That is `support`, with
its `occurrences` numerator and `population` denominator stored alongside
it so the raw counts are never hidden behind the ratio. The word
`confidence` is reserved for the later Verification stage, where it will
mean how much a *rule* is trusted given its source, corroboration, and
human review status.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evidence.contract import CanonicalRepository, EvidenceCategory, EvidenceSet


class AggregationStatus(str, enum.Enum):
    """§7.1's closed vocabulary, mirroring the Aggregation Capability
    Matrix (§2) exactly. A third value is added only when a third real
    situation exists -- never speculatively.
    """

    AGGREGATED = "aggregated"
    SKIPPED_NO_POPULATION = "skipped_no_population"


class PopulationBasis(BaseModel):
    """§7.2. One row of the Aggregation Capability Matrix: whether a given
    Evidence category has a derivable denominator, and if not, why not.

    Commit 3's `POPULATION_BASES` registry is built from these, making
    the matrix executable rather than prose that can drift from behavior.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_category: EvidenceCategory
    status: AggregationStatus
    description: str = Field(min_length=1)
    blocker: str | None = None


class Pattern(BaseModel):
    """§7.3's one measured observation.

    A `Pattern` states what *is* -- never what to do about it. It carries
    no severity, no priority, no rule, and no recommendation: promoting a
    measurement into guidance is Sprint 23's own, separate, later job.

    `population` is constrained `ge=1` rather than `ge=0` deliberately:
    §5's "no population, no Pattern" principle then holds at the type
    level, so a zero denominator is unrepresentable and cannot be
    produced even by a future bug in a resolver.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(min_length=1)
    evidence_category: EvidenceCategory
    subject: str = Field(min_length=1)
    occurrences: int = Field(ge=1)
    population: int = Field(ge=1)
    support: float = Field(ge=0.0, le=1.0)
    population_description: str = Field(min_length=1)
    supporting_evidence_ids: tuple[str, ...] = Field(min_length=1)
    repository: CanonicalRepository
    version: str = Field(min_length=1)
    commit: str = Field(min_length=1)


class SkippedAggregation(BaseModel):
    """§7.4, §9. A first-class result, not a diagnostic message.

    Carried in `PatternSet.skipped_aggregations`, persisted to disk, and
    asserted on by tests -- so a consumer can act on it programmatically,
    and so the declared gap cannot silently drift closed. A silently
    absent category would look identical to a category with nothing to
    report; only one of those is correct.

    `evidence_records_present` records how much data *was* available but
    could not be measured -- the difference between "no records" and "no
    denominator".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_category: EvidenceCategory
    status: AggregationStatus
    reason: str = Field(min_length=1)
    evidence_records_present: int = Field(ge=0)


class ObservedBelowThreshold(BaseModel):
    """§7.5. A subject seen fewer than `min_occurrences` times: recorded
    with its real count, never promoted to a `Pattern`, and never
    silently dropped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_category: EvidenceCategory
    subject: str = Field(min_length=1)
    occurrences: int = Field(ge=1)


class ThresholdSpec(BaseModel):
    """One named, documented numeric threshold -- the Rule Metadata
    Registry pattern `evaluation.contract.RuleThresholdSpec` and
    `recommendation.contract.PriorityWeightSpec` already established,
    applied here identically (§7.6). Commit 5 reads its threshold by name
    from a registry rather than inlining a magic number.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    threshold_name: str = Field(min_length=1)
    value: int
    calibration_status: str = Field(min_length=1)  # "empirical" | "heuristic_default"
    justification: str = Field(min_length=1)


class ResolutionStrategy(str, enum.Enum):
    """Inheritance Resolution §6.2. How a population's underlying class
    descent was resolved -- closed, with exactly two members, extended
    only when a third real strategy exists.
    """

    SINGLE_CORPUS = "single_corpus"
    MULTI_CORPUS = "multi_corpus"


class CorpusRef(BaseModel):
    """One corpus, identified precisely enough to be fetched again.

    Repository alone is not an identity: the same repository at two
    commits is two different bodies of evidence, and a population
    resolved against one is not the population resolved against the
    other.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: CanonicalRepository
    version: str = Field(min_length=1)
    commit: str = Field(min_length=1)


class ResolutionProvenance(BaseModel):
    """Inheritance Resolution §6. Records *how* a population was reached,
    not just what it came to.

    **Why this is a stored field rather than a runtime detail.** Once
    descent can be resolved using corpora beyond the one being measured,
    the same repository at the same commit yields more than one
    defensible population -- ERPNext resolves to 492 alone and 510 with
    `frappe` supplied (RQ-0002 F6). Both are correct answers to different
    questions. A `PatternSet` that records the number without recording
    which corpora produced it is one whose central figure cannot be
    reproduced or audited, which is the one thing this platform exists to
    prevent.

    `unresolved_bases_count` is the residue: base names matching no
    definition in any supplied corpus (`object`, `Exception`, a
    third-party class). A non-zero count is normal and expected -- it is
    recorded rather than swallowed so the shape of what was *not*
    resolved stays visible.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    measured_corpus: CorpusRef
    supporting_corpora: tuple[CorpusRef, ...] = ()
    strategy: ResolutionStrategy
    unresolved_bases_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _strategy_matches_the_corpora_actually_used(self) -> ResolutionProvenance:
        """The label may not contradict the record.

        `SINGLE_CORPUS` with supporting corpora, or `MULTI_CORPUS`
        without any, would make `strategy` a claim that the rest of the
        object disproves -- and `strategy` is exactly the field a reader
        checks when they do not want to read the rest.
        """

        if self.strategy is ResolutionStrategy.SINGLE_CORPUS and self.supporting_corpora:
            raise ValueError(
                "strategy is 'single_corpus' but supporting_corpora is not empty; "
                "use 'multi_corpus' when another corpus contributed to resolution"
            )
        if self.strategy is ResolutionStrategy.MULTI_CORPUS and not self.supporting_corpora:
            raise ValueError(
                "strategy is 'multi_corpus' but no supporting_corpora are recorded; "
                "use 'single_corpus' when resolution used the measured corpus alone"
            )
        return self

    @model_validator(mode="after")
    def _supporting_corpora_are_not_the_measured_one(self) -> ResolutionProvenance:
        for supporting in self.supporting_corpora:
            if supporting.repository is self.measured_corpus.repository:
                raise ValueError(
                    f"supporting_corpora must not contain the measured repository "
                    f"'{self.measured_corpus.repository.value}'"
                )
        return self


class AggregationRequest(BaseModel):
    """§7.6's Input. Wraps an already-read `EvidenceSet` -- this engine
    never re-runs extraction, never touches a source tree, and never
    imports `evidence.engine` (§13).

    **`evidence_set` is the subject; `supporting_evidence_sets` are
    context and nothing else** (ADR-0015, Inheritance Resolution §5.2).
    A supporting corpus contributes class definitions used to resolve
    inheritance across repository boundaries -- and contributes *nothing
    else*. It never contributes an occurrence, never joins a population,
    and never owns a `Pattern`. `PatternSet.repository` remains the
    subject's.

    The distinction is carried in the type rather than in a convention
    because the obvious alternative -- one collection of `EvidenceSet`s,
    merged -- would produce Patterns spanning two repositories, which §4
    forbids: `frappe`'s 8.4% and `erpnext`'s 8.4% are not comparable
    quantities, because the populations are differently constituted.

    Defaults to empty, so single-corpus aggregation is unchanged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_set: EvidenceSet
    supporting_evidence_sets: tuple[EvidenceSet, ...] = ()
    min_occurrences: int = Field(default=2, ge=1)
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def _supporting_corpora_are_distinct_repositories(self) -> AggregationRequest:
        """§5.3. Every supporting corpus must be a *different* repository
        from the subject, and from each other.

        Supplying a repository as its own resolution context is a caller
        error rather than a harmless no-op: it reads as though it does
        something, and silently does nothing. Supplying the same
        repository twice -- typically two versions of it -- makes descent
        ambiguous, since a class name could resolve against either.
        """

        subject = self.evidence_set.repository
        seen: set[CanonicalRepository] = set()
        for supporting in self.supporting_evidence_sets:
            if supporting.repository is subject:
                raise ValueError(
                    f"supporting_evidence_sets must not contain the measured repository "
                    f"'{subject.value}'; it is the subject, not its own resolution context"
                )
            if supporting.repository in seen:
                raise ValueError(
                    f"supporting_evidence_sets contains '{supporting.repository.value}' more "
                    f"than once; descent would be ambiguous"
                )
            seen.add(supporting.repository)
        return self


class AggregationStatistics(BaseModel):
    """Counts describing one aggregation run.

    **Category accounting, stated once and finally (Sprint 22).**

    `categories_present` counts the Evidence categories this run *treated
    as candidates for measurement* -- every category found in the
    `EvidenceSet` except the structural ones. `categories_aggregated` and
    `categories_skipped` partition exactly that set, so
    `aggregated + skipped == present` always holds, and a validator below
    enforces it rather than leaving it to be noticed.

    **Structural categories are outside this accounting entirely.**
    `CLASS_DEFINITION` and `CLASS_BASE_DECLARATION` are topology: they
    describe the class graph so a population can be resolved, and are not
    observations anyone measures a share of. They are therefore neither
    present, nor aggregated, nor skipped. Counting them as *present* while
    excluding them from the other two would break the invariant; counting
    them as *skipped* would assert "we could not measure this", when in
    fact nobody tried, because there is nothing there to measure -- and a
    declared gap that is not a gap devalues the ones that are.

    `evidence_records_consumed` is deliberately *not* restricted this way:
    it counts every record read, structural ones included, because they
    were read and the populations depend on them. Under-reporting there
    would understate what the artifact was built from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_records_consumed: int = Field(ge=0)
    categories_present: int = Field(ge=0)
    categories_aggregated: int = Field(ge=0)
    categories_skipped: int = Field(ge=0)
    patterns_produced: int = Field(ge=0)
    subjects_below_threshold: int = Field(ge=0)

    @model_validator(mode="after")
    def _aggregated_and_skipped_partition_present(self) -> AggregationStatistics:
        """Every candidate category was either measured or skipped.

        Enforced rather than documented because these three numbers are
        what a reader checks to decide whether an artifact is complete. If
        they stopped adding up, the natural reading -- "some category went
        missing" -- would be exactly right, and nothing else in the
        artifact would say so.
        """

        if self.categories_aggregated + self.categories_skipped != self.categories_present:
            raise ValueError(
                f"categories_aggregated ({self.categories_aggregated}) + categories_skipped "
                f"({self.categories_skipped}) must equal categories_present "
                f"({self.categories_present}); every candidate category is one or the other"
            )
        return self


class PatternSet(BaseModel):
    """§7.7's final artifact -- the one thing `aggregate_patterns()`
    returns. Determinism (§11): two runs against the same `EvidenceSet`
    produce an identical `PatternSet` in every field, including every
    `Pattern.pattern_id`, except `pattern_set_id` and `aggregated_at`.

    `skipped_aggregations` is **not** expected to be empty in v1.0 --
    `CONTROLLER_LIFECYCLE_HOOK` is always present there, because its
    population is not derivable from persisted Evidence alone (§2.1).
    An empty `patterns` tuple alongside a populated
    `skipped_aggregations` is a valid, meaningful, successful result: it
    says nothing was measurable, and precisely why.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_set_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    source_evidence_set_id: str = Field(min_length=1)
    repository: CanonicalRepository
    version: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    aggregated_at: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    patterns: tuple[Pattern, ...]
    skipped_aggregations: tuple[SkippedAggregation, ...]
    observed_below_threshold: tuple[ObservedBelowThreshold, ...]
    statistics: AggregationStatistics

    #: Inheritance Resolution §6. How the populations in this artifact
    #: were resolved, when any of them required resolving class descent.
    #:
    #: **Optional, and `None` is meaningful rather than missing.** It
    #: reads "no population in this artifact required inheritance
    #: resolution" -- which is true of every `PatternSet` produced up to
    #: and including `v1.3.0`, since the one category that needs it was
    #: skipped for want of a denominator. It is not a placeholder for a
    #: value that should have been there.
    #:
    #: This field is deliberately *not* yet written by
    #: `aggregation.persistence`: `_META_FIELDS` is an explicit
    #: allow-list, so a `PatternSet` round-trips through disk today
    #: exactly as before, and every existing artifact still reads back
    #: unchanged. Persistence is extended in the commit that first
    #: produces a non-`None` value, so that the writer and the producer
    #: land together rather than one of them arriving early and empty.
    resolution_provenance: ResolutionProvenance | None = None
