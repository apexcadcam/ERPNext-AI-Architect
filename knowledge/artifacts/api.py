"""The Knowledge API artifact type.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §2.2: formal,
checkable interface knowledge (a DocType field, a whitelisted method, a hook
signature, a REST endpoint).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from knowledge.artifacts.envelope import ArtifactEnvelope, ArtifactType


class KnowledgeAPIContent(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §2.2's content payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_kind: Literal["doctype-field", "whitelisted-method", "hook-signature", "rest-endpoint"]
    name: str
    signature: str = ""
    parameters: tuple[str, ...] = ()
    return_shape: str = ""
    doctype_scope: str | None = None


class KnowledgeAPI(ArtifactEnvelope):
    """A Knowledge API — the highest-precedence content artifact type when
    extracted directly from official source code (KNOWLEDGE_EXTRACTION_SPEC.md §2).
    """

    type: Literal[ArtifactType.KNOWLEDGE_API] = ArtifactType.KNOWLEDGE_API
    content: KnowledgeAPIContent
