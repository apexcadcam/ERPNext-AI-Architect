"""Architecture Evaluation's own contract: the one fixed set of types every
stage produces and consumes, and the final `ArchitectureEvaluation`
artifact callers receive.

Implements Architecture Evaluation Engine Specification v1.0 §2 and §3,
plus the Threshold Documentation & Rule Metadata Addendum, in full. Every
model is frozen, matching every other contract in this project
(`synthesis.contract.RepositoryFacts`, `discovery.contract.RepositoryInventory`,
...).
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field

from synthesis.contract import RepositoryFacts

#: §2's Input defaults.
DEFAULT_MAX_FINDINGS: int = 100
DEFAULT_TIMEOUT_SECONDS: float = 30.0


class Severity(str, enum.Enum):
    """§3's closed severity vocabulary. Computed by a fixed threshold
    function per rule (§5 of the specification) -- never assigned by feel.
    """

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, enum.Enum):
    """§3's closed confidence vocabulary. Reflects how directly the cited
    evidence supports the conclusion, not how "sure" the engine is in any
    subjective sense.

    LOW is defined and reserved for a future rule whose signal is weaker
    than any v1.0 rule actually needs -- no v1.0 rule produces it.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Evidence(BaseModel):
    """One piece of supporting evidence. Every entry must be independently
    re-derivable by reading `RepositoryFacts` at the cited path (§ Explainability).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_kind: str = Field(min_length=1)
    fact_summary: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)


class Finding(BaseModel):
    """The one thing every rule produces."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    rule_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: Severity
    confidence: Confidence
    metric_value: float
    explanation: str = Field(min_length=1)
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    affected_files: tuple[str, ...]
    affected_modules: tuple[str, ...]


class SkippedRule(BaseModel):
    """A rule whose own algorithm raised unexpectedly -- caught and
    recorded rather than aborting the whole evaluation (§7).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class EvaluationStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rules_evaluated: int = Field(ge=0)
    rules_skipped: int = Field(ge=0)
    findings_produced: int = Field(ge=0)
    findings_by_severity: dict[Severity, int]


class EvaluationRequest(BaseModel):
    """§2's Input. Wraps an already-produced `RepositoryFacts` -- this
    engine never reads the repository, never scans the filesystem, never
    parses source code.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_facts: RepositoryFacts
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    max_findings: int = Field(default=DEFAULT_MAX_FINDINGS, ge=1)
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)


class ArchitectureEvaluation(BaseModel):
    """§3's final artifact -- the one thing `evaluate_architecture()`
    returns. Determinism (§2): two runs against byte-for-byte identical
    `RepositoryFacts` produce an identical `ArchitectureEvaluation` in
    every field except `evaluation_id` and `evaluated_at`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_id: str = Field(min_length=1)
    source_facts_id: str = Field(min_length=1)
    repository_root: str = Field(min_length=1)
    evaluated_at: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    findings: tuple[Finding, ...]
    skipped_rules: tuple[SkippedRule, ...]
    truncated: bool
    statistics: EvaluationStatistics


class RuleThresholdSpec(BaseModel):
    """One named, documented threshold value -- the Rule Metadata Registry
    entry type from the Threshold Documentation & Rule Metadata Addendum.
    Every rule in `evaluation.rules` reads its own thresholds by
    `(rule_id, threshold_name)` from `evaluation.rules.RULE_THRESHOLDS`
    rather than embedding a magic number in its algorithm.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    threshold_name: str = Field(min_length=1)
    value: float
    calibration_status: str = Field(min_length=1)  # "empirical" | "heuristic_default"
    justification: str = Field(min_length=1)
