"""The Knowledge -> Intelligence Translation Bridge — Sprint 11, Phase 1.

A deterministic, structural translation API from Sprint 10's Knowledge
output shapes into Sprint 8's existing `intelligence.contract` types.
Invokes no `IntelligenceEngine`; performs no reasoning, ranking, or AI
work. See `translator.py`'s own module docstring for the full,
documented translation rules (summary generation, id synthesis, weight
defaulting, and the `EvidenceItem`/`Candidate` responsibility split).

Only the five translation functions are exported — no intermediate
helper, no Knowledge or Intelligence type is re-exported from here, to
keep this package's public surface minimal.
"""

from __future__ import annotations

from intelligence.bridge.translator import (
    translate_artifact_to_candidate,
    translate_artifact_to_evidence,
    translate_edge_to_evidence,
    translate_node_to_evidence,
    translate_reference_to_evidence,
)

__all__ = [
    "translate_artifact_to_candidate",
    "translate_artifact_to_evidence",
    "translate_edge_to_evidence",
    "translate_node_to_evidence",
    "translate_reference_to_evidence",
]
