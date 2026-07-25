"""Tests for `NullIntelligenceEngine` (Sprint 8 Implementation Plan,
Phase 2). Determinism, the ranking algorithm, tie-breaking, and the
"empty result is the correct result" guarantee for critique/assumption
challenge — no adapter tests, no wrapper tests (those are
`test_validating.py`'s own scope).
"""

from __future__ import annotations

from intelligence.contract import (
    ArchitectureCritique,
    AssumptionChallenge,
    Candidate,
    EvidenceItem,
    ProposedArchitecture,
    Requirement,
)
from intelligence.null_engine import NullIntelligenceEngine


def _engine() -> NullIntelligenceEngine:
    return NullIntelligenceEngine()


# -- interpret_requirement ----------------------------------------------------------------------


def test_interpret_requirement_restates_the_description_unchanged() -> None:
    requirement = Requirement(requirement_id="R-1", description="track patient identity and billing")
    understanding = _engine().interpret_requirement(requirement)
    assert understanding.restated_requirement == "track patient identity and billing"
    assert understanding.requirement_id == "R-1"


def test_interpret_requirement_reports_no_ambiguities_or_key_concepts() -> None:
    understanding = _engine().interpret_requirement(Requirement(requirement_id="R-1", description="x"))
    assert understanding.ambiguities == ()
    assert understanding.key_concepts == ()


def test_interpret_requirement_is_deterministic_across_repeated_calls() -> None:
    requirement = Requirement(requirement_id="R-1", description="x", context_notes="y")
    engine = _engine()
    first = engine.interpret_requirement(requirement)
    second = engine.interpret_requirement(requirement)
    assert first == second


# -- evaluate_tradeoff: ranking algorithm --------------------------------------------------------


def test_evaluate_tradeoff_ranks_by_summed_evidence_weight_highest_first() -> None:
    evidence = (
        EvidenceItem(reference_id="E-1", summary="x", weight=0.9),
        EvidenceItem(reference_id="E-2", summary="y", weight=0.2),
    )
    candidates = (
        Candidate(candidate_id="C-low", description="x", supporting_evidence_ids=("E-2",)),
        Candidate(candidate_id="C-high", description="y", supporting_evidence_ids=("E-1",)),
    )
    assessment = _engine().evaluate_tradeoff(evidence, candidates)
    assert assessment.ranked_candidate_ids == ("C-high", "C-low")


def test_evaluate_tradeoff_sums_weight_across_multiple_evidence_items() -> None:
    evidence = (
        EvidenceItem(reference_id="E-1", summary="x", weight=0.3),
        EvidenceItem(reference_id="E-2", summary="y", weight=0.3),
        EvidenceItem(reference_id="E-3", summary="z", weight=0.9),
    )
    candidates = (
        Candidate(candidate_id="C-combined", description="x", supporting_evidence_ids=("E-1", "E-2")),
        Candidate(candidate_id="C-single", description="y", supporting_evidence_ids=("E-3",)),
    )
    assessment = _engine().evaluate_tradeoff(evidence, candidates)
    # 0.3 + 0.3 == 0.6, strictly less than the single 0.9 item.
    assert assessment.ranked_candidate_ids == ("C-single", "C-combined")


def test_evaluate_tradeoff_ignores_evidence_ids_not_supplied() -> None:
    evidence = (EvidenceItem(reference_id="E-1", summary="x", weight=0.1),)
    candidates = (
        Candidate(candidate_id="C-unsupplied", description="x", supporting_evidence_ids=("E-999",)),
        Candidate(candidate_id="C-supplied", description="y", supporting_evidence_ids=("E-1",)),
    )
    assessment = _engine().evaluate_tradeoff(evidence, candidates)
    assert assessment.ranked_candidate_ids == ("C-supplied", "C-unsupplied")
    assert assessment.cited_evidence_ids == ("E-1",)


def test_evaluate_tradeoff_cites_only_evidence_actually_referenced_by_a_candidate() -> None:
    evidence = (
        EvidenceItem(reference_id="E-1", summary="x", weight=0.5),
        EvidenceItem(reference_id="E-2", summary="unused", weight=0.5),
    )
    candidates = (Candidate(candidate_id="C-1", description="x", supporting_evidence_ids=("E-1",)),)
    assessment = _engine().evaluate_tradeoff(evidence, candidates)
    assert assessment.cited_evidence_ids == ("E-1",)


def test_evaluate_tradeoff_rationale_is_non_empty() -> None:
    assessment = _engine().evaluate_tradeoff((), (Candidate(candidate_id="C-1", description="x"),))
    assert assessment.rationale != ""


def test_evaluate_tradeoff_with_no_candidates_produces_an_empty_ranking_and_non_empty_rationale() -> None:
    assessment = _engine().evaluate_tradeoff((EvidenceItem(reference_id="E-1", summary="x"),), ())
    assert assessment.ranked_candidate_ids == ()
    assert assessment.cited_evidence_ids == ()
    assert assessment.rationale != ""


# -- evaluate_tradeoff: tie-breaking --------------------------------------------------------------


def test_evaluate_tradeoff_breaks_ties_by_candidate_id_ascending() -> None:
    evidence = (EvidenceItem(reference_id="E-1", summary="x", weight=0.5),)
    candidates = (
        Candidate(candidate_id="C-z", description="x", supporting_evidence_ids=("E-1",)),
        Candidate(candidate_id="C-a", description="y", supporting_evidence_ids=("E-1",)),
        Candidate(candidate_id="C-m", description="z", supporting_evidence_ids=("E-1",)),
    )
    assessment = _engine().evaluate_tradeoff(evidence, candidates)
    assert assessment.ranked_candidate_ids == ("C-a", "C-m", "C-z")


def test_evaluate_tradeoff_tie_breaking_is_independent_of_input_order() -> None:
    evidence = ()
    candidates_one_order = (
        Candidate(candidate_id="C-b", description="x"),
        Candidate(candidate_id="C-a", description="y"),
    )
    candidates_other_order = (
        Candidate(candidate_id="C-a", description="y"),
        Candidate(candidate_id="C-b", description="x"),
    )
    engine = _engine()
    first = engine.evaluate_tradeoff(evidence, candidates_one_order)
    second = engine.evaluate_tradeoff(evidence, candidates_other_order)
    assert first.ranked_candidate_ids == second.ranked_candidate_ids == ("C-a", "C-b")


# -- evaluate_tradeoff: determinism ---------------------------------------------------------------


def test_evaluate_tradeoff_repeated_calls_with_identical_input_produce_identical_output() -> None:
    evidence = (
        EvidenceItem(reference_id="E-1", summary="x", weight=0.4),
        EvidenceItem(reference_id="E-2", summary="y", weight=0.7),
    )
    candidates = (
        Candidate(candidate_id="C-1", description="x", supporting_evidence_ids=("E-1",)),
        Candidate(candidate_id="C-2", description="y", supporting_evidence_ids=("E-2",)),
    )
    engine = _engine()
    first = engine.evaluate_tradeoff(evidence, candidates)
    second = engine.evaluate_tradeoff(evidence, candidates)
    assert first == second


def test_evaluate_tradeoff_is_deterministic_across_separate_engine_instances() -> None:
    evidence = (EvidenceItem(reference_id="E-1", summary="x", weight=0.6),)
    candidates = (Candidate(candidate_id="C-1", description="x", supporting_evidence_ids=("E-1",)),)
    first = NullIntelligenceEngine().evaluate_tradeoff(evidence, candidates)
    second = NullIntelligenceEngine().evaluate_tradeoff(evidence, candidates)
    assert first == second


# -- critique_architecture / challenge_assumptions: empty is correct -----------------------------


def test_critique_architecture_always_returns_an_empty_critique() -> None:
    critique = _engine().critique_architecture(
        ProposedArchitecture(summary="x"), (EvidenceItem(reference_id="E-1", summary="y"),)
    )
    assert critique == ArchitectureCritique()


def test_challenge_assumptions_always_returns_an_empty_challenge() -> None:
    challenge = _engine().challenge_assumptions(
        ProposedArchitecture(summary="x"), (EvidenceItem(reference_id="E-1", summary="y"),)
    )
    assert challenge == AssumptionChallenge()


def test_critique_and_challenge_are_deterministic_across_repeated_calls() -> None:
    proposed = ProposedArchitecture(summary="x")
    evidence = (EvidenceItem(reference_id="E-1", summary="y"),)
    engine = _engine()
    assert engine.critique_architecture(proposed, evidence) == engine.critique_architecture(
        proposed, evidence
    )
    assert engine.challenge_assumptions(proposed, evidence) == engine.challenge_assumptions(
        proposed, evidence
    )
