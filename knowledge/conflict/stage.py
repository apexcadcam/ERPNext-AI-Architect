"""The `knowledge.resolve_conflict` Pipeline Engine stage.

Wraps knowledge/conflict/resolution.py's pure `resolve_conflict()` in the
`(input, PipelineContext) -> (output, StageOutcome)` shape
docs/runtime/PIPELINE_ENGINE.md §2 requires of every stage — the same
`StageCallable` contract runtime/pipeline/engine.py already defines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
