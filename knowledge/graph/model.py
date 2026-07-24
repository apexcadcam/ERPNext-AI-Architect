"""The Knowledge Graph Node and Edge shapes.

Implements docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md §2 (Node
Structure) and §3/§4 (Relationship Vocabulary, edge lifecycle) exactly —
these are pure data shapes, carrying no behavior; `store.py` is where
nodes/edges are created, looked up, and traversed.

Two fields named in §2/§4 are deliberately present but always unpopulated by
this Sprint's Graph Builder, disclosed here rather than silently omitted:

- `confidence_of_edge` — §2 distinguishes it from the wrapped artifact's own
  `confidence`, but neither `RelationshipEdge` nor `DependencyEdge`
  (knowledge/artifacts/envelope.py, frozen) carries any per-edge confidence
  signal for a Builder to project from. Always `None` from this package,
  never fabricated.
- `retracted` — §4's edge-retraction lifecycle has no producer yet (nothing
  upstream emits a retraction signal); the field exists so the shape is
  spec-complete and forward-compatible, always `False` from this package.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from knowledge.artifacts import ArtifactType, RelationshipType


class GraphNode(BaseModel):
    """One `KG-NNNN` node, wrapping exactly one artifact instance and
    holding no content of its own (§2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    wraps: str
    wraps_type: ArtifactType


class GraphEdge(BaseModel):
    """One typed, directed edge between two nodes (§2/§3). Symmetric
    relationships (`conflicts_with`, `related_to`) are still represented by
    this same shape — canonical-direction storage is `store.py`'s
    responsibility, not this type's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_node_id: str
    relationship: RelationshipType
    target_node_id: str
    note: str = ""
    confidence_of_edge: float | None = None
    retracted: bool = False
