"""`NullIntelligenceEngine` — Sprint 8, Phase 2.

Implements the approved Sprint 8 Implementation Plan §4 Phase 2: the one,
minimal, deterministic reference implementation of `IntelligenceEngine`,
chosen first for the same reason `planning.strategy.RuleBasedPlannerStrategy`
was chosen first among planner strategies — lowest risk, no external
dependency, proves the contract end to end. It is deliberately not
intelligent: no language understanding, no search, no model of any kind.
It reads only the fields `IntelligenceEngine`'s four methods are given —
nothing else — and never touches the clock, a random source, or any I/O.
"""

from __future__ import annotations

from intelligence.contract import (
    ArchitectureCritique,
    AssumptionChallenge,
    Candidate,
    EvidenceItem,
    IntelligenceEngine,
    ProposedArchitecture,
    Requirement,
    RequirementUnderstanding,
    TradeoffAssessment,
)


def _evidence_weight_sum(candidate: Candidate, evidence_weight_by_id: dict[str, float]) -> float:
    return sum(
        evidence_weight_by_id[reference_id]
        for reference_id in candidate.supporting_evidence_ids
        if reference_id in evidence_weight_by_id
    )


class NullIntelligenceEngine(IntelligenceEngine):
    """The reference `IntelligenceEngine`: for every method, produces the
    most honest answer obtainable without inventing anything beyond what
    was supplied.

    - `interpret_requirement` restates `requirement.description` unchanged
      and reports no ambiguities and no key concepts — identifying either
      would require actual language understanding this implementation
      does not have.
    - `evaluate_tradeoff` ranks `candidates` by the summed `weight` of
      their own `supporting_evidence_ids` that also appear in `evidence`,
      highest first; ties are broken by `candidate_id` in ascending
      lexicographic order, so the result is fully deterministic regardless
      of the input tuples' own ordering.
    - `critique_architecture` and `challenge_assumptions` both return an
      empty result unconditionally — "no concern identified" and "no
      assumption was found worth challenging" are the correct, honest
      answers from an implementation with no capacity to critique or
      challenge anything; fabricating either would violate this contract's
      own "must not invent" expectation more, not less, than returning
      nothing.

    Stateless, side-effect-free, thread-safe, and idempotent by
    construction — there is no field on this class for state to live in.
    """

    def interpret_requirement(self, requirement: Requirement) -> RequirementUnderstanding:
        return RequirementUnderstanding(
            requirement_id=requirement.requirement_id,
            key_concepts=(),
            ambiguities=(),
            restated_requirement=requirement.description,
        )

    def evaluate_tradeoff(
        self, evidence: tuple[EvidenceItem, ...], candidates: tuple[Candidate, ...]
    ) -> TradeoffAssessment:
        evidence_weight_by_id = {item.reference_id: item.weight for item in evidence}

        ranked = sorted(
            candidates,
            key=lambda candidate: (
                -_evidence_weight_sum(candidate, evidence_weight_by_id),
                candidate.candidate_id,
            ),
        )

        used_evidence_ids = {
            reference_id for candidate in candidates for reference_id in candidate.supporting_evidence_ids
        }
        cited_evidence_ids = tuple(
            item.reference_id for item in evidence if item.reference_id in used_evidence_ids
        )

        if not ranked:
            rationale = "no candidates supplied to rank"
        else:
            scored = ", ".join(
                f"{candidate.candidate_id}={_evidence_weight_sum(candidate, evidence_weight_by_id):.4f}"
                for candidate in ranked
            )
            rationale = f"ranked by summed supporting-evidence weight, ties broken by candidate_id: {scored}"

        return TradeoffAssessment(
            ranked_candidate_ids=tuple(candidate.candidate_id for candidate in ranked),
            rationale=rationale,
            cited_evidence_ids=cited_evidence_ids,
        )

    def critique_architecture(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> ArchitectureCritique:
        return ArchitectureCritique()

    def challenge_assumptions(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> AssumptionChallenge:
        return AssumptionChallenge()
