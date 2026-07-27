"""The Knowledge -> Intelligence Translation Bridge — Sprint 11, Phase 1.

Deterministic, side-effect-free translation from Sprint 10's Knowledge
output shapes into Sprint 8's existing, frozen `intelligence.contract`
types. This module performs no reasoning, no ranking, no scoring, no AI
work, and invokes no `IntelligenceEngine` — it only prepares that
contract's own inputs from data that already exists. No new contract is
introduced here and none of `intelligence.contract`'s existing types are
modified; this module imports them exactly as already defined.

**Why this lives inside `intelligence/`, not `knowledge/`:** `knowledge/`
must remain completely unaware `intelligence/` exists — the same
direction every dependency in this project has taken since ADR-001
(a consumer depends on the producer it consumes, never the reverse).
`intelligence.bridge` is `intelligence/`'s own, single sanctioned
consumer of `knowledge.*`; every other file in `intelligence/` remains as
Knowledge-independent as Sprint 8 left it.

**Responsibility split — `EvidenceItem` vs. `Candidate` (never blurred):**
`KnowledgeReference`, `GraphNode`, and `GraphEdge` are always translated
to `EvidenceItem` — each is a pointer or a fact, never something a caller
would weigh as one of several options. `ContentArtifact` is the only
Knowledge shape with two translations, because it is the only one a
caller might legitimately use either way: `translate_artifact_to_evidence`
when the artifact is being cited as support, `translate_artifact_to_candidate`
when the artifact itself is the option under evaluation. Which of the two
applies is the caller's decision — this module does not decide it, and no
single artifact is translated as both by anything in this module.

**Summary generation — documented, deterministic, reproducible:**

- `ContentArtifact` -> `content.name` for `KnowledgeAPI` (its content has
  no `title` field); `content.title` for every other member of the
  `ContentArtifact` union (`Pattern`, `AntiPattern`, `BestPractice`,
  `Example`, `Workflow` — all five already carry one). No other field is
  read; nothing is inferred beyond this fixed, per-type lookup.
- `KnowledgeReference` -> the literal template
  `"Knowledge reference to {subject_kind} '{subject_id}' from analysis '{analysis_id}'."`
- `GraphNode` -> the literal template
  `"Graph node wrapping {wraps_type.value} artifact '{wraps}'."`
- `GraphEdge` -> the literal template
  `"Graph edge: '{source_node_id}' {relationship.value} '{target_node_id}'."`

Each template is a pure function of its input's own field values — the
same input always renders the same string; nothing here is randomized,
locale-dependent, or wall-clock-dependent.

**`reference_id`/`candidate_id` synthesis — documented, deterministic:**
`ContentArtifact.id` and `GraphNode.node_id` are already stable, unique
identifiers and are used verbatim. `KnowledgeReference` and `GraphEdge`
have no identifier of their own, so one is synthesized as a colon-joined
composite of their own existing fields, in a fixed field order:
`KnowledgeReference` -> `f"{analysis_id}:{subject_kind}:{subject_id}"`;
`GraphEdge` -> `f"{source_node_id}:{relationship}:{target_node_id}"`. No
counter, no random component, no timestamp.

**Weight — confidence when available, `EvidenceItem`'s own existing
default otherwise, never invented:** `ContentArtifact.confidence` (always
present, `ArtifactEnvelope`'s own required-with-default field) is passed
straight through. `GraphEdge.confidence_of_edge` is passed straight
through when not `None`; when it is `None` (the common case — see
`knowledge.graph.model`'s own disclosure that no Builder yet populates
it), `weight` is simply omitted from construction, so `EvidenceItem`'s own
field default (`1.0`) applies unchanged. `KnowledgeReference` and
`GraphNode` carry no confidence signal at all, so the same thing happens
for both — `weight` is omitted, `EvidenceItem`'s own default applies. No
alternate default is invented anywhere in this module.

**`Candidate.supporting_evidence_ids` derivation — structural, not a
ranking:** exactly the `target_id` of every one of the artifact's own
`dependencies` followed by every one of its own `relationships`, in their
already-declared order, deduplicated while preserving first occurrence.
This reads ids the artifact already carries; it does not decide which
ids matter more, rank them, or add or infer any id the artifact does not
already declare. Deduplication uses `dict.fromkeys` (insertion-order
preserving) rather than `set`, deliberately — a plain `set`'s iteration
order is not guaranteed stable across interpreter runs for string keys,
which would make this function's own output non-reproducible; a `dict`'s
insertion order is a language guarantee, so it is the only ordered,
duplicate-removing structure that keeps this function's determinism
requirement real rather than incidental.
"""

from __future__ import annotations

from knowledge.artifacts import ContentArtifact, KnowledgeAPI
from knowledge.domain import KnowledgeReference
from knowledge.graph import GraphEdge, GraphNode

from intelligence.contract import Candidate, EvidenceItem


def _artifact_summary(artifact: ContentArtifact) -> str:
    if isinstance(artifact, KnowledgeAPI):
        return artifact.content.name
    return artifact.content.title


def _artifact_supporting_evidence_ids(artifact: ContentArtifact) -> tuple[str, ...]:
    target_ids = [dependency.target_id for dependency in artifact.dependencies]
    target_ids += [relationship.target_id for relationship in artifact.relationships]
    return tuple(dict.fromkeys(target_ids))


def translate_artifact_to_evidence(artifact: ContentArtifact) -> EvidenceItem:
    """Represents `artifact` as evidence supporting some other assessment."""

    return EvidenceItem(
        reference_id=artifact.id,
        summary=_artifact_summary(artifact),
        weight=artifact.confidence,
    )


def translate_artifact_to_candidate(artifact: ContentArtifact) -> Candidate:
    """Represents `artifact` as an option to be weighed against others."""

    return Candidate(
        candidate_id=artifact.id,
        description=_artifact_summary(artifact),
        supporting_evidence_ids=_artifact_supporting_evidence_ids(artifact),
    )


def translate_reference_to_evidence(reference: KnowledgeReference) -> EvidenceItem:
    """Represents a `KnowledgeReference` pointer as evidence."""

    return EvidenceItem(
        reference_id=f"{reference.analysis_id}:{reference.subject_kind}:{reference.subject_id}",
        summary=(
            f"Knowledge reference to {reference.subject_kind} "
            f"'{reference.subject_id}' from analysis '{reference.analysis_id}'."
        ),
    )


def translate_node_to_evidence(node: GraphNode) -> EvidenceItem:
    """Represents a `GraphNode` as evidence."""

    return EvidenceItem(
        reference_id=node.node_id,
        summary=f"Graph node wrapping {node.wraps_type.value} artifact '{node.wraps}'.",
    )


def translate_edge_to_evidence(edge: GraphEdge) -> EvidenceItem:
    """Represents a `GraphEdge` as evidence."""

    reference_id = f"{edge.source_node_id}:{edge.relationship.value}:{edge.target_node_id}"
    summary = f"Graph edge: '{edge.source_node_id}' {edge.relationship.value} '{edge.target_node_id}'."
    if edge.confidence_of_edge is None:
        return EvidenceItem(reference_id=reference_id, summary=summary)
    return EvidenceItem(reference_id=reference_id, summary=summary, weight=edge.confidence_of_edge)
