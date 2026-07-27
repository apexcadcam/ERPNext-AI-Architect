"""The Analysis Layer's foundational contracts — Sprint 9, Phase 1.

Implements the `analysis/` package the Strategic Realignment named across
v1 §2 ("a new architectural layer between Requirements and Planning") and
v2/v4 (the ERP Analyzer's evidence-based `Recommendation` contract),
scoped narrowly to this phase's own objective: a deterministic Analysis
Foundation, immutable data contracts only. No extraction logic, no
ERPNext parsing, no similarity computation, no LLM usage — those are
later phases' scope.

**Analysis extracts facts; Intelligence reasons about them.** This
package owns `SupportingEvidence` — deliberately richer than
`intelligence.contract.EvidenceItem` (an opaque `reference_id`/`summary`/
`weight` triple): `SupportingEvidence` here carries a `source_reference`,
the literal `excerpt` a fact was derived from, and a `rationale` — because
Analysis's whole job is producing facts traceable back to their source
text, while Intelligence only ever receives already-selected evidence to
reason over. The two types are independently owned by design and are
never merged — a later phase (not this one) is responsible for
translating this package's own `Requirement` and evidence into
Intelligence's simplified shapes when it calls `IntelligenceEngine`, the
same "each layer owns its own version of a shared concept, translated at
the boundary" discipline Sprint 8 Phase 1 already established for
`EvidenceItem` itself.

Every model here is frozen, `extra="forbid"`, and carries no cross-field
validation — pure data, mirroring `orchestration/contract.py`'s own
established "the engine validates, the model doesn't" discipline. This
module imports nothing beyond `pydantic` and the standard library: no
`planning`, `execution`, `runtime`, `knowledge`, `intelligence`,
`orchestration`, or `integration` — this package is not yet a consumer of,
and is not yet consumed by, anything else in this project.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Requirement(BaseModel):
    """A developer's plain-language statement of intent — Analysis's own
    input type, independently owned from `intelligence.contract.
    Requirement` (see this module's own docstring). `description` is
    opaque free text; this module asserts nothing about its language,
    length, or structure.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AnalysisContext(BaseModel):
    """Correlation/environment metadata carried through one analysis run
    — mirrors `planning.contract.RuntimeContextInfo`'s own shape, plus a
    `correlation_id` for tracing, the same field this project's other
    per-call contexts already carry. Never a credential, never a live
    object reference — no field here can carry one, by construction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    environment: str = Field(min_length=1)


class SupportingEvidence(BaseModel):
    """One traceable link back to the literal source text a fact was
    derived from. Deliberately richer than `intelligence.contract.
    EvidenceItem` — see this module's own docstring for why the two are
    never merged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: An opaque pointer to where this excerpt came from (e.g. a
    #: `Requirement.requirement_id`, a document reference) — this module
    #: does not resolve or validate it.
    source_reference: str = Field(min_length=1)
    #: The literal text this fact was derived from.
    excerpt: str = Field(min_length=1)
    #: Why this excerpt supports the fact it's attached to.
    rationale: str = Field(min_length=1)


class Actor(BaseModel):
    """A person, role, or system participating in a business process
    (e.g. "Patient", "Receptionist", "Billing Clerk"), identified during
    analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    supporting_evidence: tuple[SupportingEvidence, ...] = ()


class BusinessEntity(BaseModel):
    """A domain concept/noun identified during analysis (e.g. "Patient",
    "Appointment", "Invoice") — the same kind of concept the Strategic
    Realignment's Layer 3 names as a "domain concept," represented here as
    Analysis's own extracted fact, independent of whether any matching
    ERPNext capability exists (that comparison is `SimilarityResult`'s
    job, in a later phase).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    #: Rough attribute names mentioned or implied — descriptive facts
    #: only, never a formal schema.
    attributes: tuple[str, ...] = ()
    supporting_evidence: tuple[SupportingEvidence, ...] = ()


class BusinessProcess(BaseModel):
    """A workflow or sequence of activity identified during analysis
    (e.g. "Patient Registration", "Appointment Scheduling"). `steps` is a
    descriptive, not executable, sequence — this is an extracted fact,
    never a `planning.contract.Plan`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    process_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    #: References to `Actor.actor_id` values — by id, never an embedded
    #: `Actor`, the same "reference by id" discipline every other
    #: cross-object link in this project already follows.
    actor_ids: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    supporting_evidence: tuple[SupportingEvidence, ...] = ()


class BusinessRule(BaseModel):
    """A stated business rule identified during analysis (e.g. "An
    invoice cannot be issued without a confirmed appointment").
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    supporting_evidence: tuple[SupportingEvidence, ...] = ()


class BusinessConstraint(BaseModel):
    """A stated limiting condition identified during analysis (e.g.
    "Only one active prescription per patient at a time") — a distinct
    concept from `BusinessRule` (a behavioral rule) even though its shape
    is identical, mirroring `Pattern`/`AntiPattern`'s own established
    "distinct concept, same content shape" precedent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    constraint_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    supporting_evidence: tuple[SupportingEvidence, ...] = ()


class RequirementAnalysis(BaseModel):
    """The full, structured breakdown of one `Requirement` — every
    entity/process/rule/constraint/actor extraction produced for it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str = Field(min_length=1)
    entities: tuple[BusinessEntity, ...] = ()
    processes: tuple[BusinessProcess, ...] = ()
    rules: tuple[BusinessRule, ...] = ()
    constraints: tuple[BusinessConstraint, ...] = ()
    actors: tuple[Actor, ...] = ()


class SimilarityResult(BaseModel):
    """The data shape a future similarity computation (explicitly out of
    this phase's scope) will produce — not computed here. `subject_id` is
    an opaque reference to whichever extracted fact this pertains to (a
    `BusinessEntity.entity_id`, `BusinessProcess.process_id`, etc.);
    `candidate_reference` is an equally opaque reference to whatever it
    was compared against. Neither is resolved or validated by this
    module — no business logic lives here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_id: str = Field(min_length=1)
    candidate_reference: str = Field(min_length=1)
    similarity_score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class GapAnalysis(BaseModel):
    """An extracted fact (`subject_id`, the same opaque-reference
    discipline as `SimilarityResult`) for which no matching existing
    capability was found — the data shape a later phase's gap-detection
    logic will produce, not computed here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supporting_evidence: tuple[SupportingEvidence, ...] = ()


class AnalysisResult(BaseModel):
    """The top-level, always-obtainable outcome of one analysis run —
    this analysis's own stable identity (`analysis_id`) alongside the
    `RequirementAnalysis` it produced and whatever `SimilarityResult`/
    `GapAnalysis` entries a later phase attaches. Does not embed the
    `AnalysisContext` that produced it — mirrors `ExecutionResult`'s/
    `GoalRunResult`'s own established "a result carries its own ids, never
    its input context" shape.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    requirement_analysis: RequirementAnalysis
    similarity_results: tuple[SimilarityResult, ...] = ()
    gaps: tuple[GapAnalysis, ...] = ()
