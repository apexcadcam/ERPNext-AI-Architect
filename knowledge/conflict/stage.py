"""Pipeline Engine stages built on knowledge/conflict/resolution.py.

Two stages, both matching `runtime.pipeline.engine.StageCallable`'s
`(input, PipelineContext) -> (output, StageOutcome)` contract:

  `resolve_conflict_stage` — resolves one `ConflictCase` directly; used by
  the Validator's Version Conflict Detection gate (§3), which already knows
  the two specific claims in tension.

  `resolve_conflicts_in_batch` — the `knowledge.graph_build` Pipeline
  Definition's own "Conflict Resolution" stage (PIPELINE_ENGINE.md §4):
  scans a list of artifacts fresh out of Pattern Extraction for any
  `Knowledge Conflict` entries mixed into it (per KNOWLEDGE_EXTRACTION_SPEC.md
  §6's Forum Discussions rule, "Threads with multiple, mutually-contradicting
  answers... → Knowledge Conflict") and resolves each against the other
  artifacts in the same batch. No extraction rule Sprint 2 actually
  implements (rules.py covers only Official Documentation/Source Code)
  produces a raw `Knowledge Conflict` yet — this stage is exercised by this
  Sprint's own tests via directly-constructed fixture input, proving the
  mechanism works ahead of the extraction rule that will eventually feed it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.artifacts import ArtifactStatus, ContentArtifact, KnowledgeConflict
from knowledge.conflict.providers import PrecedenceProvider, to_conflict_claim
from knowledge.conflict.resolution import ConflictCase, ConflictResolution, resolve_conflict
from runtime.pipeline.engine import StageOutcome

if TYPE_CHECKING:
    from runtime.pipeline.engine import PipelineContext


def resolve_conflict_stage(
    case: ConflictCase, context: PipelineContext
) -> tuple[ConflictResolution, StageOutcome]:
    """`Undecided` is a legitimate, successful business outcome to surface —
    per KNOWLEDGE_CONFLICT_RESOLUTION.md §1 it is never guessed at, but
    reporting it is not itself a stage failure. This stage therefore always
    returns `StageOutcome.SUCCESS`; callers inspect
    `ConflictResolution.requires_human_review` to know what happens next.
    """

    del context  # unused: resolution needs no correlation/tracing context
    return resolve_conflict(case), StageOutcome.SUCCESS


def resolve_conflicts_in_batch(
    items: list[ContentArtifact | KnowledgeConflict],
    context: PipelineContext,
    *,
    precedence_provider: PrecedenceProvider,
) -> tuple[list[ContentArtifact | KnowledgeConflict], StageOutcome]:
    """A deterministically-resolved `Knowledge Conflict` marks its losing
    claim `superseded` (never deleted) and is otherwise dropped from the
    batch (its outcome is now recorded on the claims themselves); an
    unresolvable one is left as a `Knowledge Conflict` in the returned list
    so a caller can route it onward for human review — this Sprint has no
    Knowledge Graph module to persist it in yet.
    """

    del context
    conflicts = [item for item in items if isinstance(item, KnowledgeConflict)]
    content_by_id: dict[str, ContentArtifact] = {
        item.id: item for item in items if not isinstance(item, KnowledgeConflict)
    }
    unresolved: list[KnowledgeConflict] = []

    for conflict in conflicts:
        claim_a = content_by_id.get(conflict.content.claim_a_id)
        claim_b = content_by_id.get(conflict.content.claim_b_id)
        if claim_a is None or claim_b is None:
            unresolved.append(conflict)  # a referenced claim isn't in this batch — nothing to resolve here
            continue

        case = ConflictCase(
            claim_a=to_conflict_claim(claim_a, precedence_provider),
            claim_b=to_conflict_claim(claim_b, precedence_provider),
        )
        resolution = resolve_conflict(case)

        if resolution.requires_human_review or resolution.losing_claim_id is None:
            unresolved.append(conflict)
            continue

        loser = content_by_id[resolution.losing_claim_id]
        content_by_id[loser.id] = loser.model_copy(update={"status": ArtifactStatus.SUPERSEDED})

    return [*content_by_id.values(), *unresolved], StageOutcome.SUCCESS
