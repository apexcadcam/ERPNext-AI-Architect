"""Tests for `intelligence/contract.py` (Sprint 8 Implementation Plan,
Phase 1). Contracts only — no behavioral tests, no adapter tests, no
runtime tests; those are later phases' own scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from intelligence.contract import (
    ArchitectureCritique,
    AssumptionChallenge,
    Candidate,
    ChallengedAssumption,
    EvidenceItem,
    IntelligenceEngine,
    ProposedArchitecture,
    Requirement,
    RequirementUnderstanding,
    TradeoffAssessment,
)

INTELLIGENCE_DIR = Path(__file__).resolve().parents[2] / "intelligence"


# -- EvidenceItem -----------------------------------------------------------------------------


def test_evidence_item_constructs_with_valid_data() -> None:
    item = EvidenceItem(reference_id="E-1", summary="some evidence", weight=0.5)
    assert item.reference_id == "E-1"
    assert item.summary == "some evidence"
    assert item.weight == 0.5


def test_evidence_item_weight_defaults_to_one() -> None:
    item = EvidenceItem(reference_id="E-1", summary="some evidence")
    assert item.weight == 1.0


def test_evidence_item_weight_out_of_bounds_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(reference_id="E-1", summary="x", weight=1.5)
    with pytest.raises(ValidationError):
        EvidenceItem(reference_id="E-1", summary="x", weight=-0.1)


def test_evidence_item_is_frozen() -> None:
    item = EvidenceItem(reference_id="E-1", summary="x")
    with pytest.raises(ValidationError):
        item.summary = "y"


def test_evidence_item_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(reference_id="E-1", summary="x", extra="y")  # type: ignore[call-arg]


def test_evidence_item_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(reference_id="", summary="x")
    with pytest.raises(ValidationError):
        EvidenceItem(reference_id="E-1", summary="")


# -- Requirement / RequirementUnderstanding ----------------------------------------------------


def test_requirement_constructs_with_valid_data() -> None:
    requirement = Requirement(requirement_id="R-1", description="track patients", context_notes="clinic")
    assert requirement.requirement_id == "R-1"
    assert requirement.description == "track patients"
    assert requirement.context_notes == "clinic"


def test_requirement_context_notes_defaults_to_empty() -> None:
    requirement = Requirement(requirement_id="R-1", description="track patients")
    assert requirement.context_notes == ""


def test_requirement_is_frozen() -> None:
    requirement = Requirement(requirement_id="R-1", description="x")
    with pytest.raises(ValidationError):
        requirement.description = "y"


def test_requirement_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Requirement(requirement_id="R-1", description="x", extra="y")  # type: ignore[call-arg]


def test_requirement_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        Requirement(requirement_id="", description="x")
    with pytest.raises(ValidationError):
        Requirement(requirement_id="R-1", description="")


def test_requirement_understanding_constructs_with_valid_data() -> None:
    understanding = RequirementUnderstanding(
        requirement_id="R-1",
        key_concepts=("patient identity", "billing"),
        ambiguities=("unclear whether appointments are in scope",),
        restated_requirement="track patient identity and billing",
    )
    assert understanding.key_concepts == ("patient identity", "billing")
    assert understanding.ambiguities == ("unclear whether appointments are in scope",)


def test_requirement_understanding_defaults_are_empty_tuples() -> None:
    understanding = RequirementUnderstanding(requirement_id="R-1", restated_requirement="x")
    assert understanding.key_concepts == ()
    assert understanding.ambiguities == ()


def test_requirement_understanding_is_frozen() -> None:
    understanding = RequirementUnderstanding(requirement_id="R-1", restated_requirement="x")
    with pytest.raises(ValidationError):
        understanding.restated_requirement = "y"


def test_requirement_understanding_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RequirementUnderstanding(requirement_id="R-1", restated_requirement="x", extra="y")  # type: ignore[call-arg]


def test_requirement_understanding_rejects_empty_restated_requirement() -> None:
    with pytest.raises(ValidationError):
        RequirementUnderstanding(requirement_id="R-1", restated_requirement="")


# -- Candidate / TradeoffAssessment -------------------------------------------------------------


def test_candidate_constructs_with_valid_data() -> None:
    candidate = Candidate(candidate_id="C-1", description="reuse Customer", supporting_evidence_ids=("E-1",))
    assert candidate.candidate_id == "C-1"
    assert candidate.supporting_evidence_ids == ("E-1",)


def test_candidate_supporting_evidence_ids_defaults_to_empty() -> None:
    candidate = Candidate(candidate_id="C-1", description="x")
    assert candidate.supporting_evidence_ids == ()


def test_candidate_is_frozen() -> None:
    candidate = Candidate(candidate_id="C-1", description="x")
    with pytest.raises(ValidationError):
        candidate.description = "y"


def test_candidate_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Candidate(candidate_id="C-1", description="x", extra="y")  # type: ignore[call-arg]


def test_candidate_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        Candidate(candidate_id="", description="x")
    with pytest.raises(ValidationError):
        Candidate(candidate_id="C-1", description="")


def test_tradeoff_assessment_constructs_with_valid_data() -> None:
    assessment = TradeoffAssessment(
        ranked_candidate_ids=("C-1", "C-2"),
        rationale="C-1 has stronger evidence",
        cited_evidence_ids=("E-1",),
    )
    assert assessment.ranked_candidate_ids == ("C-1", "C-2")
    assert assessment.cited_evidence_ids == ("E-1",)


def test_tradeoff_assessment_defaults_are_empty_tuples() -> None:
    assessment = TradeoffAssessment(rationale="x")
    assert assessment.ranked_candidate_ids == ()
    assert assessment.cited_evidence_ids == ()


def test_tradeoff_assessment_is_frozen() -> None:
    assessment = TradeoffAssessment(rationale="x")
    with pytest.raises(ValidationError):
        assessment.rationale = "y"


def test_tradeoff_assessment_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TradeoffAssessment(rationale="x", extra="y")  # type: ignore[call-arg]


def test_tradeoff_assessment_rejects_empty_rationale() -> None:
    with pytest.raises(ValidationError):
        TradeoffAssessment(rationale="")


# -- ProposedArchitecture / ArchitectureCritique -------------------------------------------------


def test_proposed_architecture_constructs_with_valid_data() -> None:
    proposed = ProposedArchitecture(summary="extend Customer", supporting_evidence_ids=("E-1",))
    assert proposed.summary == "extend Customer"
    assert proposed.supporting_evidence_ids == ("E-1",)


def test_proposed_architecture_is_frozen() -> None:
    proposed = ProposedArchitecture(summary="x")
    with pytest.raises(ValidationError):
        proposed.summary = "y"


def test_proposed_architecture_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProposedArchitecture(summary="x", extra="y")  # type: ignore[call-arg]


def test_proposed_architecture_rejects_empty_summary() -> None:
    with pytest.raises(ValidationError):
        ProposedArchitecture(summary="")


def test_architecture_critique_constructs_with_valid_data() -> None:
    critique = ArchitectureCritique(concerns=("duplicates Customer",), cited_evidence_ids=("E-1",))
    assert critique.concerns == ("duplicates Customer",)


def test_architecture_critique_defaults_are_empty_tuples() -> None:
    critique = ArchitectureCritique()
    assert critique.concerns == ()
    assert critique.cited_evidence_ids == ()


def test_architecture_critique_is_frozen() -> None:
    critique = ArchitectureCritique()
    with pytest.raises(ValidationError):
        critique.concerns = ("x",)


def test_architecture_critique_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ArchitectureCritique(extra="y")  # type: ignore[call-arg]


# -- ChallengedAssumption / AssumptionChallenge --------------------------------------------------


def test_challenged_assumption_constructs_with_valid_data() -> None:
    challenged = ChallengedAssumption(
        assumption="Patient should be a new DocType",
        challenge="why not extend Customer?",
        resolution="assumption_rejected",
        resolution_rationale="Customer already models identity and billing",
    )
    assert challenged.resolution == "assumption_rejected"


def test_challenged_assumption_rejects_an_invalid_resolution_literal() -> None:
    with pytest.raises(ValidationError):
        ChallengedAssumption(
            assumption="x",
            challenge="y",
            resolution="maybe",  # type: ignore[arg-type]
            resolution_rationale="z",
        )


def test_challenged_assumption_is_frozen() -> None:
    challenged = ChallengedAssumption(
        assumption="x", challenge="y", resolution="unresolved", resolution_rationale="z"
    )
    with pytest.raises(ValidationError):
        challenged.resolution = "assumption_holds"


def test_challenged_assumption_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ChallengedAssumption(
            assumption="x",
            challenge="y",
            resolution="unresolved",
            resolution_rationale="z",
            extra="w",  # type: ignore[call-arg]
        )


def test_challenged_assumption_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        ChallengedAssumption(assumption="", challenge="y", resolution="unresolved", resolution_rationale="z")


def test_assumption_challenge_constructs_with_valid_data() -> None:
    challenge = AssumptionChallenge(
        challenged_assumptions=(
            ChallengedAssumption(
                assumption="x", challenge="y", resolution="unresolved", resolution_rationale="z"
            ),
        ),
        cited_evidence_ids=("E-1",),
    )
    assert len(challenge.challenged_assumptions) == 1


def test_assumption_challenge_defaults_are_empty_tuples() -> None:
    challenge = AssumptionChallenge()
    assert challenge.challenged_assumptions == ()
    assert challenge.cited_evidence_ids == ()


def test_assumption_challenge_is_frozen() -> None:
    challenge = AssumptionChallenge()
    with pytest.raises(ValidationError):
        challenge.cited_evidence_ids = ("E-1",)


def test_assumption_challenge_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AssumptionChallenge(extra="y")  # type: ignore[call-arg]


# -- IntelligenceEngine (ABC) ---------------------------------------------------------------------


def test_intelligence_engine_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        IntelligenceEngine()  # type: ignore[abstract]


class _MinimalIntelligenceEngine(IntelligenceEngine):
    """The smallest possible conforming implementation — exercised only to
    prove the contract is implementable, not to test any behavior."""

    def interpret_requirement(self, requirement: Requirement) -> RequirementUnderstanding:
        return RequirementUnderstanding(
            requirement_id=requirement.requirement_id, restated_requirement=requirement.description
        )

    def evaluate_tradeoff(
        self, evidence: tuple[EvidenceItem, ...], candidates: tuple[Candidate, ...]
    ) -> TradeoffAssessment:
        return TradeoffAssessment(rationale="stub")

    def critique_architecture(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> ArchitectureCritique:
        return ArchitectureCritique()

    def challenge_assumptions(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> AssumptionChallenge:
        return AssumptionChallenge()


def test_a_minimal_concrete_implementation_can_be_instantiated() -> None:
    engine = _MinimalIntelligenceEngine()
    assert isinstance(engine, IntelligenceEngine)


def test_a_minimal_concrete_implementation_exposes_exactly_the_four_approved_methods() -> None:
    abstract_methods = IntelligenceEngine.__abstractmethods__
    assert abstract_methods == frozenset(
        {"interpret_requirement", "evaluate_tradeoff", "critique_architecture", "challenge_assumptions"}
    )


# -- Import boundary (light check; the full AST-plus-subprocess methodology is Phase 5's own scope) --


def test_contract_module_imports_only_stdlib_and_pydantic() -> None:
    tree = ast.parse((INTELLIGENCE_DIR / "contract.py").read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    assert modules <= {"__future__", "abc", "typing", "pydantic"}
