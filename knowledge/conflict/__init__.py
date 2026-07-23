"""Conflict resolution: precedence hierarchy, named scenarios, and the
non-negotiable "undecided" fallback.

Implements docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md.
"""

from __future__ import annotations

from knowledge.conflict.resolution import (
    ConflictCase,
    ConflictClaim,
    ConflictOutcomeKind,
    ConflictResolution,
    PrecedenceTier,
    resolve_conflict,
)
from knowledge.conflict.stage import resolve_conflict_stage

__all__ = [
    "ConflictCase",
    "ConflictClaim",
    "ConflictOutcomeKind",
    "ConflictResolution",
    "PrecedenceTier",
    "resolve_conflict",
    "resolve_conflict_stage",
]
