"""The Intelligence Abstraction Layer — Sprint 8, Phase 1.

Implements the approved Sprint 8 Implementation Plan's Phase 1 scope:
pure, frozen data shapes plus the `IntelligenceEngine` contract itself —
nothing else. No implementation (`NullIntelligenceEngine`), no enforcement
wrapper (`ValidatingIntelligenceEngine`, `CitationError`), no Runtime
module, no adapter, no configuration or dependency injection. Those are
later phases (Sprint 8 Implementation Plan §4, Phases 2-5).

Every method on `IntelligenceEngine` takes already-selected, structured
data as input and returns structured data as output — this is what makes
"the reasoning side never invents knowledge, it only interprets what it is
given" a property of the method signatures themselves, not a convention an
implementation could forget.

Deviation disclosure (Sprint 8 Implementation Plan §2): `EvidenceItem`
below is a generic, opaque evidence primitive this module owns outright —
it deliberately does not carry a knowledge-layer classification or any
other field typed against `knowledge/`. That richer, domain-specific
evidence shape belongs to a future `analysis/` package (Sprint 12), which
will be responsible for translating its own evidence down to `EvidenceItem`
when it calls this contract. `intelligence/` stays domain-agnostic
infrastructure, the same way `planning/` stays unaware `orchestration/`
exists — this module has no import of, and no naming borrowed from,
`knowledge/`, ERPNext, or any specific reasoning technology.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    """One piece of already-validated, already-selected evidence, opaque
    to this module beyond its own three fields. `reference_id` is meaningful
    only to whoever supplied it (e.g. an artifact id in a caller's own
    store) — `IntelligenceEngine` never looks it up, only echoes it back in
    a response's own `cited_evidence_ids`-shaped fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    #: Caller-supplied relative importance. Not interpreted by this module.
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class Requirement(BaseModel):
    """A caller's plain-language statement of intent, handed to
    `interpret_requirement` for restatement/disambiguation. `description`
    is opaque free text — this module asserts nothing about its language,
    length, or structure.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    context_notes: str = ""


class RequirementUnderstanding(BaseModel):
    """`interpret_requirement`'s sole output — a restatement plus whatever
    concepts and ambiguities were identified, never a decision or
    recommendation of any kind.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str = Field(min_length=1)
    key_concepts: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()
    restated_requirement: str = Field(min_length=1)


class Candidate(BaseModel):
    """One option `evaluate_tradeoff` is asked to weigh, identified only by
    `candidate_id` — this module carries no opinion about what a candidate
    represents; that meaning belongs entirely to the caller.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supporting_evidence_ids: tuple[str, ...] = ()


class TradeoffAssessment(BaseModel):
    """`evaluate_tradeoff`'s sole output. `ranked_candidate_ids` and
    `cited_evidence_ids` are expected (by a later phase's enforcement
    wrapper, not by this module) to be subsets of the `candidates`/
    `evidence` a given call was actually supplied — this module defines the
    shape only; it does not check the constraint itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ranked_candidate_ids: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)
    cited_evidence_ids: tuple[str, ...] = ()


class ProposedArchitecture(BaseModel):
    """A caller-assembled architecture proposal, handed to
    `critique_architecture`/`challenge_assumptions` for review. Opaque
    beyond its own two fields — this module has no model of what an
    "architecture" is.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = Field(min_length=1)
    supporting_evidence_ids: tuple[str, ...] = ()


class ArchitectureCritique(BaseModel):
    """`critique_architecture`'s sole output. An empty `concerns` tuple is
    a valid, honest response — "no concerns identified" — never a signal
    that critique was skipped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    concerns: tuple[str, ...] = ()
    cited_evidence_ids: tuple[str, ...] = ()


class ChallengedAssumption(BaseModel):
    """One assumption underlying a `ProposedArchitecture`, and the outcome
    of questioning it. `resolution` is a closed, three-way outcome, never a
    free-text verdict, so a caller can branch on it mechanically.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    assumption: str = Field(min_length=1)
    challenge: str = Field(min_length=1)
    resolution: Literal["assumption_holds", "assumption_rejected", "unresolved"]
    resolution_rationale: str = Field(min_length=1)


class AssumptionChallenge(BaseModel):
    """`challenge_assumptions`'s sole output. An empty
    `challenged_assumptions` tuple is a valid, honest response — "no
    assumption was found worth challenging" — never a signal that the
    check was skipped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    challenged_assumptions: tuple[ChallengedAssumption, ...] = ()
    cited_evidence_ids: tuple[str, ...] = ()


class IntelligenceEngine(ABC):
    """The swappable architectural-intelligence core. Exposes exactly four
    methods — no configuration logic, no Runtime wiring, no additional
    public surface — mirroring `planning.strategy.PlannerStrategy`'s own
    "one fixed contract, many backends" shape one layer up.

    Every method's input is already-structured, already-selected data
    (`EvidenceItem`, `Candidate`, `ProposedArchitecture`); every output is
    an equally structured, typed result. There is no method here that
    accepts or returns a bare string — a caller cannot ask this contract
    to "just answer a prompt," only to perform one of the four specific,
    bounded tasks below over data it was actually given.

    Every implementation of this contract is expected to be:

    - **Stateless** — no field, no cache, no memory of a prior call
      influences the next one.
    - **Side-effect free** — no I/O, no writes, no publishing of events.
    - **Deterministic whenever possible** — an implementation backed by an
      inherently non-deterministic technology should still aim for
      repeatable output given repeatable input; this contract does not
      require bit-for-bit determinism, but an implementation that is
      gratuitously non-deterministic where it could easily not be has
      failed this expectation.
    - **Thread-safe** — safe to call concurrently from multiple callers
      against the same instance.
    - **Idempotent** — calling the same method with the same input twice
      produces an equivalent result and causes no additional effect.

    This module makes no assumption about, and carries no reference to,
    any specific reasoning technology, vendor, or paradigm — an
    implementation may be backed by a large language model, a constraint
    solver, a symbolic rule engine, a graph-search algorithm, a purely
    deterministic rule set, or a technology that does not exist yet.
    """

    @abstractmethod
    def interpret_requirement(self, requirement: Requirement) -> RequirementUnderstanding:
        """Restates `requirement` and surfaces any ambiguity in it. Must
        not invent a concept the requirement itself does not mention.
        """

    @abstractmethod
    def evaluate_tradeoff(
        self, evidence: tuple[EvidenceItem, ...], candidates: tuple[Candidate, ...]
    ) -> TradeoffAssessment:
        """Ranks `candidates` using only `evidence`. Must not cite an
        evidence or candidate id that was not supplied in this call.
        """

    @abstractmethod
    def critique_architecture(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> ArchitectureCritique:
        """Identifies concerns with `proposed`, grounded only in
        `evidence`. Must not cite an evidence id that was not supplied in
        this call.
        """

    @abstractmethod
    def challenge_assumptions(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> AssumptionChallenge:
        """Questions the premises `proposed` rests on, grounded only in
        `evidence`. Must not cite an evidence id that was not supplied in
        this call.
        """
