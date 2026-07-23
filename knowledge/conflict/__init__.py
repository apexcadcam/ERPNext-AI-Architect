"""Conflict resolution: precedence hierarchy, named scenarios, and the
non-negotiable "undecided" fallback.

Implements docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md.
"""

from __future__ import annotations

from knowledge.conflict.providers import PrecedenceProvider, to_conflict_claim
from knowledge.conflict.resolution import (
    ConflictCase,
    ConflictClaim,
    ConflictOutcomeKind,
    ConflictResolution,
    PrecedenceTier,
    resolve_conflict,
)
from knowledge.conflict.stage import resolve_conflict_stage, resolve_conflicts_in_batch
from knowledge.conflict.tags import TAG_AFTER_DOCS_UPDATE, TAG_CONTRADICTS_STABLE_RULE, TAG_STAFF_AUTHORED

__all__ = [
    "TAG_AFTER_DOCS_UPDATE",
    "TAG_CONTRADICTS_STABLE_RULE",
    "TAG_STAFF_AUTHORED",
    "ConflictCase",
    "ConflictClaim",
    "ConflictOutcomeKind",
    "ConflictResolution",
    "PrecedenceProvider",
    "PrecedenceTier",
    "resolve_conflict",
    "resolve_conflict_stage",
    "resolve_conflicts_in_batch",
    "to_conflict_claim",
]
