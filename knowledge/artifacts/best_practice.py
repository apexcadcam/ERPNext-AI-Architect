"""The Best Practice artifact type.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §2.4: a
recommended, non-mandatory approach, below `Engineering Rule`'s evidence bar.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from knowledge.artifacts.envelope import ArtifactEnvelope, ArtifactType


class BestPracticeContent(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §2.4's content payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    recommendation: str
    scope: str = ""


class BestPractice(ArtifactEnvelope):
    """A well-corroborated claim not yet backed by Production-Incident-grade
    evidence, per KNOWLEDGE_ARTIFACTS.md §2.4.
    """

    type: Literal[ArtifactType.BEST_PRACTICE] = ArtifactType.BEST_PRACTICE
    content: BestPracticeContent
