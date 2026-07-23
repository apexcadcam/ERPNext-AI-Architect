"""Artifact envelope and type schemas.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md in full for the
types Sprint 2 needs: the common envelope (§1) and every content-bearing
type Extraction produces plus `Knowledge Document` and `Knowledge Conflict`
(§2). `Knowledge Source` (reused, unchanged) and `Knowledge Graph Node`
(out of Sprint 2's scope) are not modeled here.
"""

from __future__ import annotations

from knowledge.artifacts.api import KnowledgeAPI, KnowledgeAPIContent
from knowledge.artifacts.best_practice import BestPractice, BestPracticeContent
from knowledge.artifacts.conflict import KnowledgeConflict, KnowledgeConflictContent, KnowledgeConflictStatus
from knowledge.artifacts.document import KnowledgeDocument, KnowledgeDocumentContent
from knowledge.artifacts.envelope import (
    ARTIFACT_ID_PREFIXES,
    ArtifactEnvelope,
    ArtifactMetadata,
    ArtifactStatus,
    ArtifactType,
    ArtifactVersionInfo,
    DependencyEdge,
    ProvenanceLink,
    RelationshipEdge,
    RelationshipType,
    SourceReference,
)
from knowledge.artifacts.example import Example, ExampleContent
from knowledge.artifacts.pattern import AntiPattern, Pattern, PatternContent
from knowledge.artifacts.workflow import Workflow, WorkflowContent, WorkflowStep

#: The artifacts Extraction (knowledge.extract) and Pattern Extraction
#: (knowledge.extract_patterns) produce, and that Validation's gates operate
#: on — every content-bearing type except `Knowledge Document` (Extraction's
#: input, not its output) and `Knowledge Conflict` (Validation's own output).
ContentArtifact = KnowledgeAPI | Pattern | AntiPattern | BestPractice | Example | Workflow

__all__ = [
    "ARTIFACT_ID_PREFIXES",
    "AntiPattern",
    "ArtifactEnvelope",
    "ArtifactMetadata",
    "ArtifactStatus",
    "ArtifactType",
    "ArtifactVersionInfo",
    "BestPractice",
    "BestPracticeContent",
    "ContentArtifact",
    "DependencyEdge",
    "Example",
    "ExampleContent",
    "KnowledgeAPI",
    "KnowledgeAPIContent",
    "KnowledgeConflict",
    "KnowledgeConflictContent",
    "KnowledgeConflictStatus",
    "KnowledgeDocument",
    "KnowledgeDocumentContent",
    "Pattern",
    "PatternContent",
    "ProvenanceLink",
    "RelationshipEdge",
    "RelationshipType",
    "SourceReference",
    "Workflow",
    "WorkflowContent",
    "WorkflowStep",
]
