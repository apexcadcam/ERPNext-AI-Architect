"""Tests for `ValidatingIntelligenceEngine` (Sprint 8 Implementation Plan,
Phase 2). Uses a scripted fake `IntelligenceEngine` throughout — not
`NullIntelligenceEngine` — to prove the wrapper is generic over any inner
engine, per the plan's "keep the wrapper completely generic" requirement.
One end-to-end test at the bottom exercises it against the real
`NullIntelligenceEngine` as well.
"""

from __future__ import annotations

import pytest

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
from intelligence.errors import CitationError
from intelligence.null_engine import NullIntelligenceEngine
from intelligence.validating import ValidatingIntelligenceEngine


class _ScriptedIntelligenceEngine(IntelligenceEngine):
    """A fake `IntelligenceEngine` whose every method returns a
    pre-configured, fixed response, regardless of its input — lets a test
    construct an otherwise-impossible-to-provoke response shape (e.g. one
    citing a fabricated id) to prove the wrapper catches it.
    """

    def __init__(
        self,
        *,
        understanding: RequirementUnderstanding | None = None,
        tradeoff: TradeoffAssessment | None = None,
        critique: ArchitectureCritique | None = None,
        challenge: AssumptionChallenge | None = None,
    ) -> None:
        self._understanding = understanding
        self._tradeoff = tradeoff
        self._critique = critique
        self._challenge = challenge

    def interpret_requirement(self, requirement: Requirement) -> RequirementUnderstanding:
        assert self._understanding is not None
        return self._understanding

    def evaluate_tradeoff(
        self, evidence: tuple[EvidenceItem, ...], candidates: tuple[Candidate, ...]
    ) -> TradeoffAssessment:
        assert self._tradeoff is not None
        return self._tradeoff

    def critique_architecture(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> ArchitectureCritique:
        assert self._critique is not None
        return self._critique

    def challenge_assumptions(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> AssumptionChallenge:
        assert self._challenge is not None
        return self._challenge


_EVIDENCE = (EvidenceItem(reference_id="E-1", summary="x"), EvidenceItem(reference_id="E-2", summary="y"))
_CANDIDATES = (Candidate(candidate_id="C-1", description="x"), Candidate(candidate_id="C-2", description="y"))
_PROPOSED = ProposedArchitecture(summary="x")


# -- interpret_requirement: pure pass-through, no citation check applies -------------------------


def test_interpret_requirement_passes_through_unchanged() -> None:
    understanding = RequirementUnderstanding(requirement_id="R-1", restated_requirement="x")
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(understanding=understanding))
    result = wrapper.interpret_requirement(Requirement(requirement_id="R-1", description="x"))
    assert result is understanding


# -- evaluate_tradeoff: valid output passes through unchanged ------------------------------------


def test_evaluate_tradeoff_passes_through_a_valid_result_unchanged() -> None:
    tradeoff = TradeoffAssessment(
        ranked_candidate_ids=("C-1", "C-2"), rationale="x", cited_evidence_ids=("E-1",)
    )
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(tradeoff=tradeoff))
    result = wrapper.evaluate_tradeoff(_EVIDENCE, _CANDIDATES)
    assert result is tradeoff


def test_evaluate_tradeoff_with_no_citations_at_all_is_valid() -> None:
    tradeoff = TradeoffAssessment(rationale="x")
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(tradeoff=tradeoff))
    result = wrapper.evaluate_tradeoff(_EVIDENCE, _CANDIDATES)
    assert result is tradeoff


# -- evaluate_tradeoff: fabricated ids raise ------------------------------------------------------


def test_evaluate_tradeoff_raises_on_a_fabricated_evidence_id() -> None:
    tradeoff = TradeoffAssessment(rationale="x", cited_evidence_ids=("E-999",))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(tradeoff=tradeoff))
    with pytest.raises(CitationError, match="evidence"):
        wrapper.evaluate_tradeoff(_EVIDENCE, _CANDIDATES)


def test_evaluate_tradeoff_raises_on_a_fabricated_candidate_id() -> None:
    tradeoff = TradeoffAssessment(rationale="x", ranked_candidate_ids=("C-999",))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(tradeoff=tradeoff))
    with pytest.raises(CitationError, match="candidate"):
        wrapper.evaluate_tradeoff(_EVIDENCE, _CANDIDATES)


def test_evaluate_tradeoff_error_message_lists_every_unknown_id() -> None:
    tradeoff = TradeoffAssessment(rationale="x", cited_evidence_ids=("E-999", "E-998"))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(tradeoff=tradeoff))
    with pytest.raises(CitationError) as excinfo:
        wrapper.evaluate_tradeoff(_EVIDENCE, _CANDIDATES)
    assert "E-999" in str(excinfo.value)
    assert "E-998" in str(excinfo.value)


def test_evaluate_tradeoff_checks_evidence_before_candidates() -> None:
    # Both fields invalid -- the evidence check fires first; this only
    # proves *a* CitationError is raised, not an ordering guarantee beyond
    # "fails fast on the first problem found," per the plan's requirement.
    tradeoff = TradeoffAssessment(
        rationale="x", cited_evidence_ids=("E-999",), ranked_candidate_ids=("C-999",)
    )
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(tradeoff=tradeoff))
    with pytest.raises(CitationError):
        wrapper.evaluate_tradeoff(_EVIDENCE, _CANDIDATES)


# -- critique_architecture: valid passes through, fabricated id raises ---------------------------


def test_critique_architecture_passes_through_a_valid_result_unchanged() -> None:
    critique = ArchitectureCritique(concerns=("x",), cited_evidence_ids=("E-1",))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(critique=critique))
    result = wrapper.critique_architecture(_PROPOSED, _EVIDENCE)
    assert result is critique


def test_critique_architecture_raises_on_a_fabricated_evidence_id() -> None:
    critique = ArchitectureCritique(cited_evidence_ids=("E-999",))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(critique=critique))
    with pytest.raises(CitationError, match="evidence"):
        wrapper.critique_architecture(_PROPOSED, _EVIDENCE)


def test_critique_architecture_with_no_citations_is_valid() -> None:
    critique = ArchitectureCritique(concerns=("a concern with no citation",))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(critique=critique))
    result = wrapper.critique_architecture(_PROPOSED, _EVIDENCE)
    assert result is critique


# -- challenge_assumptions: valid passes through, fabricated id raises ---------------------------


def test_challenge_assumptions_passes_through_a_valid_result_unchanged() -> None:
    challenge = AssumptionChallenge(cited_evidence_ids=("E-2",))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(challenge=challenge))
    result = wrapper.challenge_assumptions(_PROPOSED, _EVIDENCE)
    assert result is challenge


def test_challenge_assumptions_raises_on_a_fabricated_evidence_id() -> None:
    challenge = AssumptionChallenge(cited_evidence_ids=("E-999",))
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(challenge=challenge))
    with pytest.raises(CitationError, match="evidence"):
        wrapper.challenge_assumptions(_PROPOSED, _EVIDENCE)


def test_challenge_assumptions_with_no_citations_is_valid() -> None:
    challenge = AssumptionChallenge()
    wrapper = ValidatingIntelligenceEngine(_ScriptedIntelligenceEngine(challenge=challenge))
    result = wrapper.challenge_assumptions(_PROPOSED, _EVIDENCE)
    assert result is challenge


# -- Generic over any inner engine, proven end-to-end against the real Null engine ---------------


def test_wrapper_works_against_the_real_null_intelligence_engine() -> None:
    wrapper = ValidatingIntelligenceEngine(NullIntelligenceEngine())
    evidence = (EvidenceItem(reference_id="E-1", summary="x", weight=0.8),)
    candidates = (Candidate(candidate_id="C-1", description="x", supporting_evidence_ids=("E-1",)),)

    result = wrapper.evaluate_tradeoff(evidence, candidates)

    assert result.ranked_candidate_ids == ("C-1",)
    assert result.cited_evidence_ids == ("E-1",)


def test_wrapper_never_raises_for_the_null_engines_own_empty_critique_and_challenge() -> None:
    wrapper = ValidatingIntelligenceEngine(NullIntelligenceEngine())
    evidence = (EvidenceItem(reference_id="E-1", summary="x"),)

    assert wrapper.critique_architecture(_PROPOSED, evidence) == ArchitectureCritique()
    assert wrapper.challenge_assumptions(_PROPOSED, evidence) == AssumptionChallenge()
