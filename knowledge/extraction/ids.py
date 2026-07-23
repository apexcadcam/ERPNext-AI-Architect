"""Stable, sequential ID issuance for artifacts this Sprint's Extractor
produces.

No persistence layer exists yet (SPRINT2_IMPLEMENTATION_PLAN.md §3), so this
is process-local, in-memory state — a real ID authority (a compiled index,
per docs/ai-retrieval/RULE_INDEX_SPEC.md §6's pattern for `Engineering Rule`
IDs) is a later Sprint's concern; this is enough to guarantee every artifact
this Sprint produces gets a unique, correctly-prefixed id.
"""

from __future__ import annotations

from knowledge.artifacts import ARTIFACT_ID_PREFIXES, ArtifactType


class IdAllocator:
    """Issues the next `PREFIX-NNNN` id for a given artifact type."""

    def __init__(self) -> None:
        self._counters: dict[ArtifactType, int] = {}

    def next_id(self, artifact_type: ArtifactType) -> str:
        self._counters[artifact_type] = self._counters.get(artifact_type, 0) + 1
        return f"{ARTIFACT_ID_PREFIXES[artifact_type]}-{self._counters[artifact_type]:04d}"
