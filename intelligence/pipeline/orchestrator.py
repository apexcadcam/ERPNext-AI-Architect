"""Intelligence Pipeline Wiring — Sprint 11, Phase 2.

Wires the existing Knowledge layer into the existing `IntelligenceEngine`
abstraction using Phase 1's already-completed `intelligence.bridge`,
exactly along the frozen flow:

    KnowledgeSnapshot -> Bridge -> EvidenceItem / Candidate -> IntelligenceEngine

This module performs orchestration only: gather Knowledge output, hand it
to Bridge, hand Bridge's output to an injected `IntelligenceEngine`,
return its response unmodified. No business logic, no re-interpretation
of evidence, no transformation after translation, no new contract, no
reasoning of its own.

**Why this file never imports `knowledge.*`, even for a type
annotation:** this phase's own dependency rule is that `intelligence.
bridge` remains the *only* Intelligence component allowed to import
Knowledge — not "the only one that imports it for business logic," the
only one, full stop. `_collect_evidence`/`_collect_candidates` below
still need to walk a `KnowledgeSnapshot`'s own shape (`.collections`,
each with `.artifacts`/`.references`/`.nodes`/`.edges`) to know what to
hand to Bridge — so the snapshot parameter is typed `Any` rather than
`knowledge.domain.KnowledgeSnapshot`, deliberately. This is the same
"a structural seam needs no import of the concrete type it accepts"
reasoning already established twice in this project (`planning.
graph_reader.GraphReader`, `intelligence.adapters.anthropic_adapter.
AnthropicClientProtocol`), taken one step further: those two precedents
still import the *data* shapes they carry and only avoid the concrete
adapter/client class; this module's own constraint is stricter (no
`knowledge` import of any kind), so even the data shape itself is left
untyped. A `Protocol` whose every field would itself have to be typed
`Any` (since `EvidenceItem`/`Candidate`'s translators require concrete
`knowledge.*` types this file cannot name) would add a class with no
real static-safety benefit over the plain, honest `Any` used directly
below — introducing one would be exactly the unnecessary abstraction
this phase's own brief forbids, not a genuine improvement over it.

**Why `evaluate_tradeoff` and only `evaluate_tradeoff`:** `IntelligenceEngine`
exposes four methods. `interpret_requirement` needs a `Requirement`
(a caller's own plain-language statement) and `critique_architecture`/
`challenge_assumptions` both need a `ProposedArchitecture` (a caller's own
assembled proposal) — neither exists anywhere in a `KnowledgeSnapshot`,
and fabricating either from Knowledge data would be inventing a
requirement or a proposal Knowledge never stated, exactly the
"reinterpreting evidence" this phase's own brief forbids.
`evaluate_tradeoff(evidence, candidates)` is the one method whose entire,
real input is obtainable purely from translated Knowledge output — the
only one this pipeline can honestly call.

**Why artifacts become `Candidate`s and everything else becomes
`EvidenceItem`s:** mechanical, not a judgment call. Of Bridge's five
translators, only `translate_artifact_to_candidate` produces a
`Candidate` at all — `KnowledgeReference`, `GraphNode`, and `GraphEdge`
have no `Candidate` translation to choose between in the first place.
`ContentArtifact` is therefore the one Knowledge shape this pipeline
treats as "the option under evaluation"; every other shape already only
has one place to go (`EvidenceItem`), so this pipeline sends it there.

**Order and determinism:** every collection, and every item within it,
is walked in the snapshot's own declared tuple order — no sorting, no
filtering, no deduplication beyond whatever Bridge's own translators
already do. Given the same `KnowledgeSnapshot` and the same
`IntelligenceEngine` implementation, this module always constructs and
passes the identical `(evidence, candidates)` tuple to that engine — the
engine's own response determinism is that engine's own documented
responsibility (`IntelligenceEngine`'s own ABC docstring), not something
this orchestration layer can or does affect.
"""

from __future__ import annotations

from typing import Any

from intelligence.bridge import (
    translate_artifact_to_candidate,
    translate_edge_to_evidence,
    translate_node_to_evidence,
    translate_reference_to_evidence,
)
from intelligence.contract import Candidate, EvidenceItem, IntelligenceEngine, TradeoffAssessment


def collect_evidence(snapshot: Any) -> tuple[EvidenceItem, ...]:
    """Translates every `KnowledgeReference`, `GraphNode`, and `GraphEdge`
    across every collection in `snapshot`, in declared order, into
    `EvidenceItem`. `snapshot` is a `knowledge.domain.KnowledgeSnapshot`
    at runtime; see this module's own docstring for why it is typed `Any`
    rather than that concrete type.
    """

    evidence: list[EvidenceItem] = []
    for collection in snapshot.collections:
        for reference in collection.references:
            evidence.append(translate_reference_to_evidence(reference))
        for node in collection.nodes:
            evidence.append(translate_node_to_evidence(node))
        for edge in collection.edges:
            evidence.append(translate_edge_to_evidence(edge))
    return tuple(evidence)


def collect_candidates(snapshot: Any) -> tuple[Candidate, ...]:
    """Translates every `ContentArtifact` across every collection in
    `snapshot`, in declared order, into `Candidate`. See `collect_evidence`
    for why `snapshot` is typed `Any`.
    """

    return tuple(
        translate_artifact_to_candidate(artifact)
        for collection in snapshot.collections
        for artifact in collection.artifacts
    )


def evaluate_knowledge_snapshot(snapshot: Any, engine: IntelligenceEngine) -> TradeoffAssessment:
    """The pipeline's sole entry point: `snapshot` -> Bridge ->
    `(EvidenceItem, ...)` / `(Candidate, ...)` -> `engine.evaluate_tradeoff`
    -> its `TradeoffAssessment`, returned unmodified. `engine` may be
    `NullIntelligenceEngine`, a `ValidatingIntelligenceEngine` wrapping any
    inner engine, or any other real `IntelligenceEngine` implementation —
    this function does not know or care which.
    """

    evidence = collect_evidence(snapshot)
    candidates = collect_candidates(snapshot)
    return engine.evaluate_tradeoff(evidence, candidates)
