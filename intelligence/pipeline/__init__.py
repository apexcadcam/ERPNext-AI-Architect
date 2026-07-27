"""Intelligence Pipeline Wiring — Sprint 11, Phase 2.

Orchestration only: gathers already-translated Knowledge output (via
Phase 1's `intelligence.bridge`) and invokes the existing
`IntelligenceEngine` abstraction. See `orchestrator.py`'s own module
docstring for the full, documented reasoning — why this package never
imports `knowledge.*`, why `evaluate_tradeoff` is the only engine method
called here, and why `ContentArtifact` alone becomes `Candidate` while
every other Knowledge shape becomes `EvidenceItem`.

Translation (`intelligence.bridge`), pipeline orchestration (this
package), and Intelligence reasoning (`IntelligenceEngine` and its
implementations) remain three separate responsibilities — this package
performs only the middle one.
"""

from __future__ import annotations

from intelligence.pipeline.orchestrator import (
    collect_candidates,
    collect_evidence,
    evaluate_knowledge_snapshot,
)

__all__ = [
    "collect_candidates",
    "collect_evidence",
    "evaluate_knowledge_snapshot",
]
