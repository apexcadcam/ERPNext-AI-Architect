"""Knowledge domain contracts — Sprint 10, Phase 1.

Implements ADR-001's mandate as pure, immutable data: Knowledge consumes
Analysis, never reasons, and prepares reusable knowledge for Intelligence.
No implementation, no storage, no graph database, no Runtime integration,
no persistence — see this module's own compatibility review (in the
Sprint 10 Phase 1 deliverables, not repeated here) for the full mapping
between what already existed in this project's Knowledge Factory (Sprint
2/3) and what is genuinely new below.

**Reused, not reinvented** (see the compatibility review for why):
`KnowledgeNode` is `knowledge.graph.GraphNode`; `KnowledgeRelationship` is
`knowledge.graph.GraphEdge` (graph-level) / `knowledge.artifacts.
RelationshipEdge` (artifact-level); `KnowledgeArtifact` is `knowledge.
artifacts.ContentArtifact`. None of these three names are redefined here —
doing so would be exactly the "parallel model representing the same
concept" this phase's own brief forbids.

**Genuinely new** (nothing in this project modeled these before Sprint 10,
because nothing before ADR-001 needed Knowledge to consume Analysis
output at all): `KnowledgeReference`, `KnowledgeCollection`,
`KnowledgeSnapshot`, `KnowledgeQuery`, `KnowledgeResult`,
`KnowledgeStatistics`.

Depends on `analysis.contract` (one type, `AnalysisResult` — the one
place this module directly reflects ADR-001's "Knowledge consumes
Analysis") and this project's own existing, frozen `knowledge.artifacts`/
`knowledge.graph` (Sprint 2/3). Imports nothing from `intelligence`,
`planning`, `execution`, `runtime`, `orchestration`, or `integration`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from analysis.contract import AnalysisResult
from knowledge.artifacts import ArtifactType, ContentArtifact
from knowledge.graph import GraphEdge, GraphNode


class KnowledgeReference(BaseModel):
    """A pointer from a piece of organized Knowledge back to the specific
    Analysis fact it was derived from. Genuinely new — not a duplicate of
    `knowledge.artifacts.envelope.SourceReference`, which points at
    *external*, crawled content (`url`/`content_hash`/`span`) and has no
    field capable of naming an Analysis fact by id. `subject_kind` is a
    closed set mirroring `analysis.contract`'s own five fact-producing
    types exactly — no sixth kind exists there to enumerate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    subject_kind: Literal[
        "business_entity", "business_process", "business_rule", "business_constraint", "actor"
    ]


class KnowledgeCollection(BaseModel):
    """A named, organized grouping of existing knowledge — artifacts,
    graph nodes and edges, and the `KnowledgeReference`s tying them back to
    the Analysis facts they came from. Reuses `ContentArtifact`
    (`knowledge.artifacts`) and `GraphNode`/`GraphEdge` (`knowledge.graph`)
    directly rather than wrapping them in a new type.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    collection_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    artifacts: tuple[ContentArtifact, ...] = ()
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()
    references: tuple[KnowledgeReference, ...] = ()


class KnowledgeSnapshot(BaseModel):
    """An immutable, point-in-time capture of everything Knowledge has
    organized from one Analysis run. The one place this module directly
    imports `analysis.contract` — per ADR-001, consuming Analysis's
    output is this whole layer's reason to exist. `source` is embedded,
    not referenced by id: a snapshot's entire point is that it captures
    having organized *this exact* `AnalysisResult`, not a pointer to look
    one up elsewhere later.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    source: AnalysisResult
    collections: tuple[KnowledgeCollection, ...] = ()


class KnowledgeQuery(BaseModel):
    """A request for knowledge — pure data describing *what* is being
    asked for. No query engine, no execution logic, no ranking: answering
    a `KnowledgeQuery` is explicitly out of this phase's scope.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    artifact_types: tuple[ArtifactType, ...] = ()
    tags: tuple[str, ...] = ()


class KnowledgeResult(BaseModel):
    """What came back for one `KnowledgeQuery` — pure data, never computed
    here. `total_matched` must account for at least what's actually
    included; this is the one structural invariant this module enforces,
    mirroring `ArtifactEnvelope`'s own `_id_matches_type_prefix`
    precedent — a genuine cross-field consistency check, not a new
    business decision.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    artifacts: tuple[ContentArtifact, ...] = ()
    nodes: tuple[GraphNode, ...] = ()
    total_matched: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _total_matched_accounts_for_every_included_item(self) -> KnowledgeResult:
        included = len(self.artifacts) + len(self.nodes)
        if self.total_matched < included:
            raise ValueError(
                f"total_matched ({self.total_matched}) cannot be less than the "
                f"{included} item(s) actually included in this result"
            )
        return self


class KnowledgeStatistics(BaseModel):
    """Aggregate counts describing one `KnowledgeCollection` — pure data,
    never computed here (computing them is a later phase's concern).
    `counts_by_artifact_type` is a plain `dict`, the same disclosed,
    already-precedented trade-off `planning.contract.PlanStep.parameters`
    makes: a `dict` is categorically unhashable, so this model — like
    `PlanStep` — is immutable in the sense that its own fields cannot be
    reassigned, but is not itself hashable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    collection_id: str = Field(min_length=1)
    artifact_count: int = Field(default=0, ge=0)
    node_count: int = Field(default=0, ge=0)
    relationship_count: int = Field(default=0, ge=0)
    counts_by_artifact_type: dict[str, int] = Field(default_factory=dict)
