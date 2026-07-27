"""The Intelligence Abstraction Layer — Sprint 8, Phases 1-2.

Implements the approved Sprint 8 Implementation Plan's Phase 1 scope (the
foundational data models and the `IntelligenceEngine` contract itself,
`intelligence/contract.py`) and Phase 2 scope (`NullIntelligenceEngine`,
`ValidatingIntelligenceEngine`, `CitationError`). The Runtime module
wrapper (`intelligence.module`) and the one adapter (`intelligence.
adapters.anthropic_adapter`) exist as of later Sprint 8 phases but are
deliberately not re-exported here, keeping this file's own public surface
scoped to Phases 1-2 only.

**Updated disclosure (Sprint 11, Phase 1):** `intelligence.bridge` is now
the one sanctioned, Knowledge-aware exception to this package's own
isolation — it imports `knowledge.*` to translate Knowledge's output into
this module's own `EvidenceItem`/`Candidate`. Every symbol re-exported
from *this* file remains exactly as Knowledge-independent as it always
was; `contract.py`, `errors.py`, `null_engine.py`, `validating.py`,
`module.py`, and `adapters/` still import none of `knowledge/`,
`analysis/`, `planning/`, `execution/`, or `orchestration/`, and none of
those packages import this one — see `tests/sprint11/
test_architecture_boundaries.py` for the enforced, executable version of
this exact boundary.
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
