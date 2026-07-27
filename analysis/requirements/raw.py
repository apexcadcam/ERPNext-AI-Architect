"""Raw structured requirement shapes — Sprint 9, Phase 3.

Per this phase's own brief: "the analyzer receives structured
requirements, not free-form natural language... assume parsing into
structured fields has already happened. This phase is about analysis,
not NLP." These models are that already-structured input — a
human, or a future upstream tool, has already identified which spans of a
requirement mention an entity, a process, an actor, a rule, or a
constraint, and supplies each mention alongside the literal `excerpt` it
was identified from. `analyzer.py` never invents a mention that isn't
here; it only converts what's supplied into `analysis.contract` shapes.

Every `excerpt` field is required (`min_length=1`) — this is what makes
"never fabricate evidence" a structural guarantee rather than a
convention: there is no way to construct a mention this package accepts
without a real, non-empty excerpt for the resulting `SupportingEvidence`
to cite.

`extra="ignore"`, mirroring `analysis.erpnext.metadata`'s own established
distinction from `analysis.contract`'s `extra="forbid"`: this is an input
shape for structured data assembled by whoever calls this analyzer, not
this project's own fully-controlled vocabulary.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RawEntityMention(BaseModel):
    """One already-identified business-entity mention."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    attributes: tuple[str, ...] = ()


class RawProcessMention(BaseModel):
    """One already-identified business-process mention. `actors` names
    participants by name only — this module never resolves a name to an
    `Actor` id beyond the same deterministic naming rule `analyze_actors()`
    itself uses, and never requires a matching `RawActorMention` to exist.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    steps: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()


class RawActorMention(BaseModel):
    """One already-identified actor mention."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class RawRuleMention(BaseModel):
    """One already-identified business-rule mention."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    statement: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class RawConstraintMention(BaseModel):
    """One already-identified business-constraint mention."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    statement: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class RawRequirement(BaseModel):
    """The complete, already-structured input for one requirement:
    its own identity and description, plus every mention already
    identified within it. Any of the five mention tuples may be empty —
    a requirement with no business rules mentioned, for instance, is a
    normal, valid input, not a malformed one.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    requirement_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    entities: tuple[RawEntityMention, ...] = ()
    processes: tuple[RawProcessMention, ...] = ()
    actors: tuple[RawActorMention, ...] = ()
    rules: tuple[RawRuleMention, ...] = ()
    constraints: tuple[RawConstraintMention, ...] = ()
