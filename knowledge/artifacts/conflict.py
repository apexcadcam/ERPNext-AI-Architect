"""The Knowledge Conflict artifact type.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §2.7: a detected,
pre-rule disagreement between two claims. Produced by Validation's Version
Conflict Detection stage (KNOWLEDGE_VALIDATION_SPEC.md §3) and resolved per
KNOWLEDGE_CONFLICT_RESOLUTION.md (see knowledge/conflict/resolution.py).
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from knowledge.artifacts.envelope import ArtifactEnvelope, ArtifactType


class KnowledgeConflictStatus(str, enum.Enum):
    """KNOWLEDGE_ARTIFACTS.md §2.7's content-level `status` field."""

    OPEN = "open"
    RESOLVED_DETERMINISTIC = "resolved-deterministic"
    RESOLVED_HUMAN = "resolved-human"
    UNDECIDED = "undecided"


class KnowledgeConflictContent(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §2.7's content payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_a_id: str
    claim_b_id: str
    scope: str
    precedence_outcome: str | None = None
    conflict_status: KnowledgeConflictStatus = KnowledgeConflictStatus.OPEN


class KnowledgeConflict(ArtifactEnvelope):
    """A detected disagreement between two claims, per KNOWLEDGE_ARTIFACTS.md §2.7."""

    type: Literal[ArtifactType.KNOWLEDGE_CONFLICT] = ArtifactType.KNOWLEDGE_CONFLICT
    content: KnowledgeConflictContent
