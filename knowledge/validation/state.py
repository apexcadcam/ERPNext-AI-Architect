"""In-memory state the Validator's gates need to compare an incoming
artifact against artifacts already seen in this process.

No persistence layer exists yet (SPRINT2_IMPLEMENTATION_PLAN.md §3) — this
is intentionally process-local and disposable, scoped to what Duplicate
Detection (KNOWLEDGE_VALIDATION_SPEC.md §2) and Version Conflict Detection
(§3) need: an exact-match index and a same-type/same-version index.
"""

from __future__ import annotations

import hashlib

from knowledge.artifacts import ArtifactType, ContentArtifact


def content_hash(artifact: ContentArtifact) -> str:
    """A deterministic exact-match key for `artifact`'s content payload.

    Content-only (not the full envelope) — two artifacts extracted from
    different sources but claiming the identical fact must hash identically,
    per KNOWLEDGE_PIPELINE.md §5's "exact-match" pass generalized to the
    artifact level.
    """

    return hashlib.sha256(artifact.content.model_dump_json().encode("utf-8")).hexdigest()


class KnowledgeStore:
    """Every artifact that has passed through Duplicate Detection, indexed
    for the two lookups the Validator's gates need.
    """

    def __init__(self) -> None:
        self._by_content_hash: dict[tuple[ArtifactType, str], ContentArtifact] = {}
        self._by_type_and_version: dict[tuple[ArtifactType, str], list[ContentArtifact]] = {}

    def find_exact_duplicate(self, artifact: ContentArtifact) -> ContentArtifact | None:
        return self._by_content_hash.get((artifact.type, content_hash(artifact)))

    def same_type_same_version(
        self, artifact_type: ArtifactType, applies_to: str
    ) -> tuple[ContentArtifact, ...]:
        return tuple(self._by_type_and_version.get((artifact_type, applies_to), ()))

    def remember(self, artifact: ContentArtifact) -> None:
        self._by_content_hash[(artifact.type, content_hash(artifact))] = artifact
        if artifact.version.applies_to is not None:
            key = (artifact.type, artifact.version.applies_to)
            entries = self._by_type_and_version.setdefault(key, [])
            entries[:] = [existing for existing in entries if existing.id != artifact.id]
            entries.append(artifact)
