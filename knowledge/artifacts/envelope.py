"""The common artifact envelope every Knowledge Factory artifact shares.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §1: the nine
fields — id, type, metadata, version, provenance, confidence,
source_references, tags, dependencies, relationships — carried by every
artifact regardless of its type-specific content payload.

Business-rule checks (e.g. "source_references must be non-empty to pass
Schema Validation") are deliberately not enforced at construction time here.
KNOWLEDGE_VALIDATION_SPEC.md §1 requires a failing artifact to be *retained*
with a `rejected` status, not deleted or made un-constructible — so those
checks belong to the Validator's gates (knowledge/validation/), not to this
schema layer.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArtifactType(str, enum.Enum):
    """See KNOWLEDGE_ARTIFACTS.md §2 for the full type catalog.

    `Knowledge Source` and `Knowledge Graph Node` are catalog entries too,
    but are out of Sprint 2's scope (Knowledge Source is reused, unchanged,
    from knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md; Knowledge Graph Node
    belongs to the Graph Node/Edge Materialization stage this Sprint defers,
    per SPRINT2_IMPLEMENTATION_PLAN.md §3) and are not modeled here.
    """

    KNOWLEDGE_DOCUMENT = "knowledge_document"
    KNOWLEDGE_API = "knowledge_api"
    PATTERN = "pattern"
    ANTI_PATTERN = "anti_pattern"
    BEST_PRACTICE = "best_practice"
    EXAMPLE = "example"
    WORKFLOW = "workflow"
    KNOWLEDGE_CONFLICT = "knowledge_conflict"


#: Stable ID prefix per artifact type, per KNOWLEDGE_ARTIFACTS.md §1's
#: `id` field ("PREFIX-NNNN") and ENGINEERING_META_MODEL.md's Naming Standards.
ARTIFACT_ID_PREFIXES: dict[ArtifactType, str] = {
    ArtifactType.KNOWLEDGE_DOCUMENT: "KD",
    ArtifactType.KNOWLEDGE_API: "KA",
    ArtifactType.PATTERN: "PAT",
    ArtifactType.ANTI_PATTERN: "AP",
    ArtifactType.BEST_PRACTICE: "BP",
    ArtifactType.EXAMPLE: "EX",
    ArtifactType.WORKFLOW: "WF",
    ArtifactType.KNOWLEDGE_CONFLICT: "KC",
}


class ArtifactStatus(str, enum.Enum):
    """An artifact's status through the Knowledge Factory pipeline.

    Not itself assembled into one state machine anywhere in the frozen
    architecture — the individual values are named piecemeal across
    KNOWLEDGE_VALIDATION_SPEC.md, KNOWLEDGE_ARTIFACTS.md §2.7, and
    KNOWLEDGE_CONFLICT_RESOLUTION.md. Assembled here, narrowly, for what
    Sprint 2 needs; flagged in SPRINT2_IMPLEMENTATION_PLAN.md §8 as a risk
    for architecture review, not treated as already-frozen.
    """

    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"
    PENDING_CONFLICT_RESOLUTION = "pending-conflict-resolution"
    PENDING_HUMAN_APPROVAL = "pending-human-approval"
    SUPERSEDED = "superseded"


class ArtifactMetadata(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §1's `metadata` field: when and how this
    envelope was produced, distinct from when the underlying knowledge was
    true.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    extracted_at: str
    extraction_method: str
    extractor_version: str
    artifact_schema_version: str = "1.0.0"


class ArtifactVersionInfo(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §1's `version` field.

    `artifact_version` (this record's own structural version) and
    `applies_to` (the ERPNext/Frappe version the claim itself is scoped to)
    are two different notions of "version" and must never be conflated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_version: str = "1.0.0"
    applies_to: str | None = None
    #: Confidence band for `applies_to`, per KNOWLEDGE_PIPELINE.md §4.
    version_confidence: Literal["explicit", "stated", "inferred"] = "explicit"


class ProvenanceLink(BaseModel):
    """One link in KNOWLEDGE_ARTIFACTS.md §1's provenance chain:
    Knowledge Source → Knowledge Document(s) → this artifact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    artifact_type: str


class SourceReference(BaseModel):
    """A direct, dereferenceable pointer to the source content an artifact's
    claim came from — KNOWLEDGE_ARTIFACTS.md §1's anti-hallucination anchor.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    retrieved_at: str
    content_hash: str
    #: The exact span of source text the claim came from, per
    #: KNOWLEDGE_EXTRACTION_SPEC.md §0 — never a paraphrase with no anchor.
    span: str | None = None


class RelationshipType(str, enum.Enum):
    """The full relationship vocabulary, per KNOWLEDGE_GRAPH_SPEC.md §3."""

    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"
    REPLACES = "replaces"
    CONFLICTS_WITH = "conflicts_with"
    RELATED_TO = "related_to"
    DEPRECATED_BY = "deprecated_by"
    SUPERSEDES = "supersedes"
    REFERENCES = "references"


class RelationshipEdge(BaseModel):
    """One typed edge an artifact participates in, per KNOWLEDGE_GRAPH_SPEC.md §2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_id: str
    relationship: RelationshipType
    note: str = ""


class DependencyEdge(BaseModel):
    """The `depends_on`-typed subset of `relationships`, broken out per
    KNOWLEDGE_ARTIFACTS.md §1 because dependency expansion is the most
    frequently-queried relationship type.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_id: str
    reason: str = ""


class ArtifactEnvelope(BaseModel):
    """KNOWLEDGE_ARTIFACTS.md §1's common envelope.

    Frozen: a status transition or relationship addition produces a new
    envelope via `model_copy(update=...)` rather than mutating in place —
    the same "append, never overwrite" discipline KNOWLEDGE_GRAPH_SPEC.md §4
    already requires for graph edges, applied here to the artifact itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    type: ArtifactType
    metadata: ArtifactMetadata
    version: ArtifactVersionInfo
    provenance: tuple[ProvenanceLink, ...] = ()
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_references: tuple[SourceReference, ...] = ()
    tags: tuple[str, ...] = ()
    dependencies: tuple[DependencyEdge, ...] = ()
    relationships: tuple[RelationshipEdge, ...] = ()
    status: ArtifactStatus = ArtifactStatus.DRAFT

    @model_validator(mode="after")
    def _id_matches_type_prefix(self) -> ArtifactEnvelope:
        """`id` must carry its type's stable prefix (KNOWLEDGE_ARTIFACTS.md §1)."""

        expected_prefix = ARTIFACT_ID_PREFIXES[self.type]
        if not self.id.startswith(f"{expected_prefix}-"):
            raise ValueError(
                f"id '{self.id}' does not match the expected prefix "
                f"'{expected_prefix}-' for artifact type '{self.type.value}'"
            )
        return self
