"""The Knowledge Graph — Sprint 3, Phase 5.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §7 (Graph Build Engine, Graph
Store Adapter, Traversal Interface) and
docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md (Node Structure, Relationship
Vocabulary, edge lifecycle) — projecting Sprint 2's already-shipped
`ContentArtifact` envelope fields (`relationships`/`dependencies`) into a
traversable, in-memory graph.

Depends only on `knowledge.artifacts` (Sprint 2, frozen). Per the
Architecture Audit that approved this phase, this package imports nothing
from `integration/` (Connector Registry, Connector Contract, Secrets
Resolver, Configuration Profiles) and nothing from `runtime/` beyond what
`knowledge.artifacts` itself already depends on — the Knowledge Graph is
read/derive-only with respect to artifacts (ADR-0006) and untouched by any
live Connector call (ADR-0007, §11.4).

Out of this phase's scope, per its own task description: the Planning
Engine, any Runtime Module/Pipeline wiring for this package, and any
Connector integration — all left for a later phase.
"""

from __future__ import annotations

from knowledge.graph.builder import GraphBuilder
from knowledge.graph.errors import (
    ArtifactNotValidatedError,
    DependsOnCycleError,
    GraphError_,
    InconsistentNodeError,
    UnknownArtifactPrefixError,
)
from knowledge.graph.model import GraphEdge, GraphNode
from knowledge.graph.store import SYMMETRIC_RELATIONSHIPS, GraphStoreAdapter, InMemoryGraphStore

__all__ = [
    "SYMMETRIC_RELATIONSHIPS",
    "ArtifactNotValidatedError",
    "DependsOnCycleError",
    "GraphBuilder",
    "GraphEdge",
    "GraphError_",
    "GraphNode",
    "GraphStoreAdapter",
    "InMemoryGraphStore",
    "InconsistentNodeError",
    "UnknownArtifactPrefixError",
]
