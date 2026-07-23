"""The Pattern / Anti-Pattern artifact types.

Implements docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md §2.3: a named,
reusable solution shape (`Pattern`) or its named bad mirror (`Anti-Pattern`),
reused unchanged from ENGINEERING_META_MODEL.md entries 8-9.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from knowledge.artifacts.envelope import ArtifactEnvelope, ArtifactType


class PatternContent(BaseModel):
    """Shared content shape for `Pattern` and `Anti-Pattern`.

    `third_party_observed` is set when the pattern was extracted from a
    long-tail/marketplace source rather than an official one, per
    KNOWLEDGE_EXTRACTION_SPEC.md §7 — it caps confidence below an equivalent
    official-sourced pattern regardless of corroboration count
    (KNOWLEDGE_VALIDATION_SPEC.md §5).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    problem: str
    solution_shape: str
    third_party_observed: bool = False


class Pattern(ArtifactEnvelope):
    """A recurring solution shape, per KNOWLEDGE_EXTRACTION_SPEC.md §9 —
    observed successfully across ≥2 independent artifacts, never manufactured
    from a single anecdote.
    """

    type: Literal[ArtifactType.PATTERN] = ArtifactType.PATTERN
    content: PatternContent


class AntiPattern(ArtifactEnvelope):
    """A recurring *bad* shape, per KNOWLEDGE_EXTRACTION_SPEC.md §9 —
    evidenced by recurring problem reports rather than recurring success.
    """

    type: Literal[ArtifactType.ANTI_PATTERN] = ArtifactType.ANTI_PATTERN
    content: PatternContent
