"""`ValidatingIntelligenceEngine` — Sprint 8, Phase 2.

Implements the approved Sprint 8 Implementation Plan §4 Phase 2: the one,
non-bypassable enforcement point for "an `IntelligenceEngine` must not
cite evidence or a candidate it was not actually given." Wraps any other
`IntelligenceEngine` — this project's own `NullIntelligenceEngine`, a
future vendor adapter, or any other future implementation — and changes
no business behavior of the wrapped engine's output: a conforming
response passes through completely unmodified. A response citing an id
absent from that call's own input raises `CitationError` immediately —
never logged and passed through, never silently repaired.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

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


def _reject_unknown_ids(cited_ids: Collection[str], valid_ids: Iterable[str], *, kind: str) -> None:
    valid = set(valid_ids)
    unknown = [cited_id for cited_id in cited_ids if cited_id not in valid]
    if unknown:
        raise CitationError(f"cited {kind} id(s) not present in the supplied input: {unknown}")


class ValidatingIntelligenceEngine(IntelligenceEngine):
    """Wraps `inner`, an arbitrary `IntelligenceEngine`. Every method
    delegates to `inner` unchanged, then checks the result's own citation
    fields against the exact input that call was given, before returning
    it. `interpret_requirement` is a pure pass-through — it takes no
    evidence or candidates, so there is nothing for this wrapper to check.

    Generic over `inner` by construction — this class knows nothing about
    any specific `IntelligenceEngine` implementation, vendor, or
    technology.
    """

    def __init__(self, inner: IntelligenceEngine) -> None:
        self._inner = inner

    def interpret_requirement(self, requirement: Requirement) -> RequirementUnderstanding:
        return self._inner.interpret_requirement(requirement)

    def evaluate_tradeoff(
        self, evidence: tuple[EvidenceItem, ...], candidates: tuple[Candidate, ...]
    ) -> TradeoffAssessment:
        result = self._inner.evaluate_tradeoff(evidence, candidates)
        _reject_unknown_ids(
            result.cited_evidence_ids, (item.reference_id for item in evidence), kind="evidence"
        )
        _reject_unknown_ids(
            result.ranked_candidate_ids,
            (candidate.candidate_id for candidate in candidates),
            kind="candidate",
        )
        return result

    def critique_architecture(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> ArchitectureCritique:
        result = self._inner.critique_architecture(proposed, evidence)
        _reject_unknown_ids(
            result.cited_evidence_ids, (item.reference_id for item in evidence), kind="evidence"
        )
        return result

    def challenge_assumptions(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> AssumptionChallenge:
        result = self._inner.challenge_assumptions(proposed, evidence)
        _reject_unknown_ids(
            result.cited_evidence_ids, (item.reference_id for item in evidence), kind="evidence"
        )
        return result
