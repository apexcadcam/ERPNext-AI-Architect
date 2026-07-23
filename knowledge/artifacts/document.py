"""The Knowledge Document artifact type.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §2.1: the staging
unit produced by Acquisition/Cleaning/Normalization/Deduplication
(KNOWLEDGE_PIPELINE.md §§2-5, out of Sprint 2's scope — see
SPRINT2_IMPLEMENTATION_PLAN.md §3) and consumed by Extraction (in scope).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from knowledge.artifacts.envelope import ArtifactEnvelope, ArtifactType


class KnowledgeDocumentContent(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §2.1's content payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_text: str
    cleaned_text: str = ""
    format: str
    language: str = "en"
    structural_metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocument(ArtifactEnvelope):
    """A Knowledge Document.

    Closer to raw material than a claim — per KNOWLEDGE_ARTIFACTS.md §2.1 it
    has no `depends_on` edges, only a `references` edge to its
    `Knowledge Source`.
    """

    type: Literal[ArtifactType.KNOWLEDGE_DOCUMENT] = ArtifactType.KNOWLEDGE_DOCUMENT
    content: KnowledgeDocumentContent
