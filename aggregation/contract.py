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

from pydantic import BaseModel, ConfigDict, Field

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


class AggregationRequest(BaseModel):
    """§7.6's Input. Wraps an already-read `EvidenceSet` -- this engine
    never re-runs extraction, never touches a source tree, and never
    imports `evidence.engine` (§13).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_set: EvidenceSet
    min_occurrences: int = Field(default=2, ge=1)
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)


class AggregationStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_records_consumed: int = Field(ge=0)
    categories_present: int = Field(ge=0)
    categories_aggregated: int = Field(ge=0)
    categories_skipped: int = Field(ge=0)
    patterns_produced: int = Field(ge=0)
    subjects_below_threshold: int = Field(ge=0)


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
