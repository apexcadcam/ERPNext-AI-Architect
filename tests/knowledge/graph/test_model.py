"""Tests for the Knowledge Graph's Node/Edge data shapes
(docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md §2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from knowledge.artifacts import ArtifactType, RelationshipType
from knowledge.graph.model import GraphEdge, GraphNode


def test_graph_node_constructs() -> None:
    node = GraphNode(node_id="KG-0001", wraps="KA-0001", wraps_type=ArtifactType.KNOWLEDGE_API)
    assert node.node_id == "KG-0001"
    assert node.wraps == "KA-0001"
    assert node.wraps_type == ArtifactType.KNOWLEDGE_API


def test_graph_node_is_frozen() -> None:
    node = GraphNode(node_id="KG-0001", wraps="KA-0001", wraps_type=ArtifactType.KNOWLEDGE_API)
    with pytest.raises(ValidationError):
        node.node_id = "KG-0002"


def test_graph_edge_constructs_with_defaults() -> None:
    edge = GraphEdge(
        source_node_id="KG-0001", relationship=RelationshipType.DEPENDS_ON, target_node_id="KG-0002"
    )
    assert edge.note == ""
    assert edge.confidence_of_edge is None
    assert edge.retracted is False


def test_graph_edge_is_frozen() -> None:
    edge = GraphEdge(
        source_node_id="KG-0001", relationship=RelationshipType.DEPENDS_ON, target_node_id="KG-0002"
    )
    with pytest.raises(ValidationError):
        edge.retracted = True
