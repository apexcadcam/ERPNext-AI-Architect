"""Knowledge Graph exception hierarchy.

Mirrors the narrow-per-package exception discipline `integration/errors.py`
and `secrets_management/errors.py` already establish this Sprint: each new
package owns its own exceptions rather than overloading another package's,
even where the failure category is conceptually similar.
"""

from __future__ import annotations


class GraphError_(Exception):
    """Base class for every error raised by the Knowledge Graph package.

    Named with a trailing underscore for the same reason
    `runtime.errors.RuntimeError_` is: to avoid shadowing a built-in-shaped
    name at a glance.
    """


class ArtifactNotValidatedError(GraphError_):
    """The Graph Builder's input must be a `ContentArtifact` with
    `status == ArtifactStatus.VALIDATED` (KNOWLEDGE_GRAPH_SPEC.md §7.3's
    Graph Build Engine: "Its input is exactly what Sprint 2's
    `knowledge.validation` pipeline already produces... `status: validated`").
    A caller passing anything else has violated that precondition.
    """


class UnknownArtifactPrefixError(GraphError_):
    """An edge names a `target_id` whose id prefix does not match any
    entry in `knowledge.artifacts.ARTIFACT_ID_PREFIXES` — the Graph Builder
    has no way to determine that node's `wraps_type` without guessing, and
    this package never guesses (no heuristics, no inference).
    """


class DependsOnCycleError(GraphError_):
    """KNOWLEDGE_GRAPH_SPEC.md §3: "a `depends_on` cycle is rejected at
    graph-write, not merely detected later at query time." Raised by
    `GraphStoreAdapter.create_edge` when adding a `depends_on` edge would
    close a cycle.
    """


class InconsistentNodeError(GraphError_):
    """A node is asked to be created for a `wraps` id that already has a
    node in this store, but with a different `wraps_type` than the one
    already recorded. Should not occur if callers only ever derive
    `wraps_type` from `ARTIFACT_ID_PREFIXES` (which is 1:1 with id prefix),
    but checked defensively rather than silently taking whichever was
    first.
    """
