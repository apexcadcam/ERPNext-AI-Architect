"""Injectable seams for gates that need external-world data this Sprint has
no live source for.

KNOWLEDGE_VALIDATION_SPEC.md §4 (Source Verification) re-fetches the actual
cited source; §5 (Trust Verification) reads KNOWLEDGE_SOURCE_CATALOG.md's
live Trust Score. Without a real Crawler or a live Knowledge Source Catalog
integration (neither built by any Sprint yet), the gates that need these
facts depend on these protocols instead — a future Crawler/Catalog Sprint
supplies a real implementation, and no gate logic changes when it does.
See SPRINT2_IMPLEMENTATION_PLAN.md §8 for the risk this documents.

No default "always succeeds" implementation is provided here deliberately —
that would be indistinguishable from a disguised stub silently letting
every artifact through. Callers (including this Sprint's own tests) supply
an explicit implementation appropriate to what they're testing.
"""

from __future__ import annotations

from typing import Protocol

from knowledge.artifacts import ContentArtifact
from knowledge.conflict import PrecedenceTier


class SourceVerifier(Protocol):
    """KNOWLEDGE_VALIDATION_SPEC.md §4: does this artifact's source content
    still dereference to what it claims?
    """

    def verify(self, artifact: ContentArtifact) -> bool: ...


class TrustScoreProvider(Protocol):
    """KNOWLEDGE_VALIDATION_SPEC.md §5: the 0-100 Trust Score of the
    Knowledge Source this artifact was ultimately extracted from.
    """

    def trust_score(self, artifact: ContentArtifact) -> int: ...


class PrecedenceProvider(Protocol):
    """Which KNOWLEDGE_CONFLICT_RESOLUTION.md §1 precedence tier this
    artifact's originating source occupies — needed by Version Conflict
    Detection to build a `ConflictCase` for `resolve_conflict()`.
    """

    def precedence_tier(self, artifact: ContentArtifact) -> PrecedenceTier: ...
