"""The Intelligence Abstraction Layer — Sprint 8, Phases 1-2.

Implements the approved Sprint 8 Implementation Plan's Phase 1 scope (the
foundational data models and the `IntelligenceEngine` contract itself,
`intelligence/contract.py`) and Phase 2 scope (`NullIntelligenceEngine`,
`ValidatingIntelligenceEngine`, `CitationError`). The Runtime module
wrapper and every adapter are later-phase scope — neither exists yet, and
this module deliberately does not re-export them. Nothing in this package
imports `knowledge/`, `analysis/`, `planning/`, `execution/`, or
`orchestration/`, and nothing in those packages imports this one.
"""

from __future__ import annotations

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
from intelligence.errors import CitationError, IntelligenceError_
from intelligence.null_engine import NullIntelligenceEngine
from intelligence.validating import ValidatingIntelligenceEngine

__all__ = [
    "ArchitectureCritique",
    "AssumptionChallenge",
    "Candidate",
    "ChallengedAssumption",
    "CitationError",
    "EvidenceItem",
    "IntelligenceEngine",
    "IntelligenceError_",
    "NullIntelligenceEngine",
    "ProposedArchitecture",
    "Requirement",
    "RequirementUnderstanding",
    "TradeoffAssessment",
    "ValidatingIntelligenceEngine",
]
