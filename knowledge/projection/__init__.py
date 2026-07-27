"""The deterministic Knowledge Graph Projection — Sprint 10, Phase 3.

Converts `knowledge.domain` objects into the existing `knowledge.graph.
GraphNode`/`GraphEdge` contracts — representation only. See `projector.py`'s
own module docstring for the full compatibility findings against
`knowledge.graph.builder.GraphBuilder` that shaped this module's design.
"""

from __future__ import annotations

from knowledge.projection.projector import (
    project_artifact,
    project_artifact_edges,
    project_collection,
    project_snapshot,
)

__all__ = [
    "project_artifact",
    "project_artifact_edges",
    "project_collection",
    "project_snapshot",
]
