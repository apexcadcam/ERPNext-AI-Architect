"""The `PrecedenceProvider` seam and the artifact-to-`ConflictClaim` helper
every conflict-resolving stage needs.

`PrecedenceProvider` lives here, not in knowledge/validation/, because it is
fundamentally about KNOWLEDGE_CONFLICT_RESOLUTION.md §1's precedence tiers —
knowledge/validation/gates.py depends on it (Version Conflict Detection),
and knowledge/conflict/stage.py's batch resolver depends on it too; keeping
it here avoids a circular import between the two (validation already
imports from conflict for `resolve_conflict` itself).

No default "always official-source-code" implementation is provided,
matching knowledge/validation/providers.py's same discipline — a caller
(including this Sprint's own tests) supplies an explicit implementation.
"""

from __future__ import annotations

from typing import Protocol

from knowledge.artifacts import ContentArtifact
from knowledge.conflict.resolution import ConflictClaim, PrecedenceTier
from knowledge.conflict.tags import TAG_AFTER_DOCS_UPDATE, TAG_CONTRADICTS_STABLE_RULE, TAG_STAFF_AUTHORED


class PrecedenceProvider(Protocol):
    """Which KNOWLEDGE_CONFLICT_RESOLUTION.md §1 precedence tier this
    artifact's originating source occupies.
    """

    def precedence_tier(self, artifact: ContentArtifact) -> PrecedenceTier: ...


def to_conflict_claim(artifact: ContentArtifact, precedence_provider: PrecedenceProvider) -> ConflictClaim:
    """Builds the `ConflictClaim` `resolve_conflict()` needs from an
    artifact plus its precedence tier — the tag-facet fields
    (`staff_authored`, etc.) are read from `artifact.tags`, per
    knowledge/conflict/tags.py.
    """

    return ConflictClaim(
        artifact_id=artifact.id,
        precedence_tier=precedence_provider.precedence_tier(artifact),
        version_applies_to=artifact.version.applies_to,
        version_confidence=artifact.version.version_confidence,
        staff_authored=TAG_STAFF_AUTHORED in artifact.tags,
        authored_after_docs_last_update=TAG_AFTER_DOCS_UPDATE in artifact.tags,
        contradicts_stable_rule=TAG_CONTRADICTS_STABLE_RULE in artifact.tags,
    )
