"""The Workflow artifact type.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §2.6: a
multi-step, sequential/procedural process description — distinguished from
`Pattern` (a structural solution shape) by being ordered steps.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from knowledge.artifacts.envelope import ArtifactEnvelope, ArtifactType


class WorkflowStep(BaseModel):
    """One ordered step of a `Workflow`.

    `invokes` names the `Knowledge API`/`Pattern` id this step depends on,
    per KNOWLEDGE_ARTIFACTS.md §2.6's `depends_on`-in-step-order relationship.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    order: int
    description: str
    invokes: str | None = None


class WorkflowContent(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §2.6's content payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    steps: tuple[WorkflowStep, ...]


class Workflow(ArtifactEnvelope):
    """A multi-step procedure, per KNOWLEDGE_ARTIFACTS.md §2.6."""

    type: Literal[ArtifactType.WORKFLOW] = ArtifactType.WORKFLOW
    content: WorkflowContent
