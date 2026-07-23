"""The Example artifact type.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §2.5: a concrete
illustration, explicitly non-authoritative.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from knowledge.artifacts.envelope import ArtifactEnvelope, ArtifactType


class ExampleContent(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §2.5's content payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    demonstrates: str
    code_or_steps: str


class Example(ArtifactEnvelope):
    """A concrete, non-authoritative illustration of a `Pattern`/`Knowledge API`."""

    type: Literal[ArtifactType.EXAMPLE] = ArtifactType.EXAMPLE
    content: ExampleContent
