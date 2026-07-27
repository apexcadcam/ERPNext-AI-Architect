"""Knowledge domain contracts — Sprint 10, Phase 1.

Implements ADR-001 as pure, immutable data only. `KnowledgeNode`,
`KnowledgeRelationship`, and `KnowledgeArtifact` are deliberately not
defined or re-exported here — they already exist as `knowledge.graph.
GraphNode`, `knowledge.graph.GraphEdge`/`knowledge.artifacts.
RelationshipEdge`, and `knowledge.artifacts.ContentArtifact` respectively;
see `contract.py`'s own module docstring for the full reasoning. This
package re-exports only the six genuinely new types Sprint 10 adds.
"""

from __future__ import annotations

from knowledge.domain.contract import (
    KnowledgeCollection,
    KnowledgeQuery,
    KnowledgeReference,
    KnowledgeResult,
    KnowledgeSnapshot,
    KnowledgeStatistics,
)

__all__ = [
    "KnowledgeCollection",
    "KnowledgeQuery",
    "KnowledgeReference",
    "KnowledgeResult",
    "KnowledgeSnapshot",
    "KnowledgeStatistics",
]
