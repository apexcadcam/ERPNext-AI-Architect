"""Evidence Extraction Engine's own contract: the one fixed set of types
every collector produces and the engine consumes, and the final
`EvidenceSet` artifact callers receive.

Implements Evidence Extraction Engine Architecture Specification v1.1 §6
in full. Every model is frozen, matching every other contract in this
project (`evaluation.contract.ArchitectureEvaluation`,
`recommendation.contract.RecommendationSet`, ...).
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field


class CanonicalRepository(str, enum.Enum):
    """§2's closed set of pinned, read-only canonical references. Extending
    to other frameworks (Django, Odoo, ...) is explicitly not a goal of
    this Sprint or this schema (§4).
    """

    FRAPPE = "frappe"
    ERPNEXT = "erpnext"


class EvidenceKind(str, enum.Enum):
    """§6.2's closed vocabulary, extended only when its own Miner exists.

    `documentation` / `migration` / `release_note` / `architecture_decision`
    are deliberately not stubbed here -- they are added only when a
    Documentation Miner / Migration Miner / Release Note Miner /
    Architecture Decision Miner actually exists.
    """

    IMPLEMENTATION = "implementation"


class EvidenceCategory(str, enum.Enum):
    """§3's v1 signal types, plus Sprint 22's two structural ones.

    **The two structural categories exist as a pair, and separating them
    is the point** (Inheritance Resolution Specification §2.1). A single
    category recording "class X declares base B" would emit nothing at
    all for a class that declares no base -- which is precisely the blind
    spot that made the `CONTROLLER_LIFECYCLE_HOOK` population underivable
    in the first place, since that collector likewise emits a record only
    where a hook is *found*. Recording the node set and the edge set
    separately makes "every class produces at least one record" a
    structural property rather than one someone has to remember.

    `class Customer(Document, NestedSet)` therefore yields three records:
    one `CLASS_DEFINITION` and two `CLASS_BASE_DECLARATION`. `class Foo:`
    yields exactly one.

    Neither category carries any inference. A `CLASS_BASE_DECLARATION`
    records the base name *as written in the source*; whether that name
    resolves to `frappe.model.document.Document`, and whether the
    declaring class therefore descends from it, is computed downstream
    from these records and never asserted here (ADR-0015).
    """

    CONTROLLER_LIFECYCLE_HOOK = "controller_lifecycle_hook"
    WHITELISTED_API_DECORATION = "whitelisted_api_decoration"
    CLASS_DEFINITION = "class_definition"
    CLASS_BASE_DECLARATION = "class_base_declaration"


class CollectorName(str, enum.Enum):
    """§6.4's closed vocabulary for `Evidence.collector`. A free string
    invited drift (`"hook"` vs `"hooks"` vs `"collect_hook"` meaning the
    same thing across different records) -- closed exactly like
    `EvidenceKind`/`EvidenceCategory`, extended only when a new collector
    actually exists.
    """

    CONTROLLER_LIFECYCLE_HOOK_COLLECTOR = "controller_lifecycle_hook_collector"
    WHITELISTED_API_DECORATION_COLLECTOR = "whitelisted_api_decoration_collector"

    #: One collector, two categories (Inheritance Resolution §2.4). A
    #: single AST pass produces a class's definition record and its base
    #: records together; splitting it in two would walk the same tree
    #: twice to produce facts that are only meaningful as a pair.
    CLASS_DEFINITION_COLLECTOR = "class_definition_collector"


class Source(BaseModel):
    """§6.5's mandatory provenance. Every `Evidence.source` must resolve to
    a real repository, version, commit, file, and line -- a finding that
    cannot be traced this precisely is not emitted (§5).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: CanonicalRepository
    version: str = Field(min_length=1)
    commit: str = Field(min_length=1, pattern=r"^[0-9a-f]{7,40}$")
    relative_path: str = Field(min_length=1)
    line: int = Field(ge=1)


class Evidence(BaseModel):
    """§6.6's one atomic observed occurrence.

    Deliberately atomic: one Evidence record per single observed fact --
    never a bundle of several facts in one record (§3). `evidence_id` is
    content-addressed (a `sha256` digest of `repository`, `relative_path`,
    `line`, `category`, `symbol`, and `subject`), not a UUID -- the same
    fact at the same commit always produces the same id, in any run,
    enabling direct cross-run and future cross-version comparison (§9).
    Carries no confidence field of any kind (§5) -- that is Pattern
    Aggregation's own, later, separate computation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1)
    kind: EvidenceKind
    category: EvidenceCategory
    symbol: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    source: Source
    collector: CollectorName
    collected_at: str = Field(min_length=1)


class EvidenceExtractionRequest(BaseModel):
    """§6.7's Input. `version` and `commit` are caller-supplied, never
    auto-detected by the engine at runtime -- this keeps the engine free
    of a `git` runtime dependency and keeps provenance an explicit,
    testable input (§2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: CanonicalRepository
    source_root: str = Field(min_length=1)
    version: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    max_files: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)


class EvidenceStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    files_examined: int = Field(ge=0)
    files_skipped: int = Field(ge=0)
    files_failed: int = Field(ge=0)
    evidence_extracted: int = Field(ge=0)


class EvidenceExtractionError(BaseModel):
    """One file that failed to parse -- extraction still completes; this is
    the graceful-degradation record, never a raised exception (§8).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class EvidenceSet(BaseModel):
    """§6.10's final artifact -- the one thing `extract_evidence()`
    returns. Determinism (§9): two runs against the same `source_root` and
    the same request produce an identical `EvidenceSet` in every field,
    including every `Evidence.evidence_id`, except `evidence_set_id`,
    `extracted_at`, and each `Evidence.collected_at`.

    `evidence_set_id` is a fresh UUID per run -- it identifies the *run*,
    not the content (contrast with `Evidence.evidence_id`, which is
    content-addressed).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_set_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    repository: CanonicalRepository
    version: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    extracted_at: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    evidence: tuple[Evidence, ...]
    errors: tuple[EvidenceExtractionError, ...]
    truncated: bool
    statistics: EvidenceStatistics
