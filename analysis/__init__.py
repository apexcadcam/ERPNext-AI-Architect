"""The Analysis Layer — Sprint 9, Phase 1.

Implements this phase's own scope only: the foundational data contracts
(`analysis/contract.py`) representing the output of deterministic
requirement analysis. No extraction logic, no ERPNext parsing, no
similarity computation, no LLM usage, no Runtime integration, no
pipeline — all later-phase scope, none of it built yet. Nothing in this
package imports `planning`, `execution`, `runtime`, `knowledge`,
`intelligence`, `orchestration`, or `integration`, and nothing in those
packages imports this one.
"""

from __future__ import annotations

from analysis.contract import (
    Actor,
    AnalysisContext,
    AnalysisResult,
    BusinessConstraint,
    BusinessEntity,
    BusinessProcess,
    BusinessRule,
    GapAnalysis,
    Requirement,
    RequirementAnalysis,
    SimilarityResult,
    SupportingEvidence,
)

__all__ = [
    "Actor",
    "AnalysisContext",
    "AnalysisResult",
    "BusinessConstraint",
    "BusinessEntity",
    "BusinessProcess",
    "BusinessRule",
    "GapAnalysis",
    "Requirement",
    "RequirementAnalysis",
    "SimilarityResult",
    "SupportingEvidence",
]
