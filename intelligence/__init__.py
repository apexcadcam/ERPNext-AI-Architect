"""The Intelligence Abstraction Layer — Sprint 8, Phase 1.

Implements the approved Sprint 8 Implementation Plan's Phase 1 scope only:
the foundational data models and the `IntelligenceEngine` contract itself
(`intelligence/contract.py`). `NullIntelligenceEngine`,
`ValidatingIntelligenceEngine`, `CitationError`, the Runtime module
wrapper, and every adapter are later-phase scope — none of them exist yet,
and this module deliberately does not re-export anything beyond Phase 1's
own contracts. Nothing in this package imports `knowledge/`, `analysis/`,
`planning/`, `execution/`, or `orchestration/`, and nothing in those
packages imports this one.
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

__all__ = [
    "ArchitectureCritique",
    "AssumptionChallenge",
    "Candidate",
    "ChallengedAssumption",
    "EvidenceItem",
    "IntelligenceEngine",
    "ProposedArchitecture",
    "Requirement",
    "RequirementUnderstanding",
    "TradeoffAssessment",
]
