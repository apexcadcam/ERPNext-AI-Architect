"""The Recommendation Engine exception hierarchy.

Mirrors `evaluation.errors.EvaluationError_`'s own trailing-underscore-base
convention exactly (Recommendation Engine Architecture Specification v1.0
§3's "Errors").

Like `EvaluationError_`, this base has no expected concrete subtype raised
in normal operation -- this engine touches no I/O and receives an
already-validated `ArchitectureEvaluation`. A single grouping step that
fails unexpectedly is caught and recorded as a `SkippedGrouping` inside
the returned artifact, never raised to the caller (see
`recommendation.scoring.group_findings`).
"""

from __future__ import annotations


class RecommendationError_(Exception):
    """Base class for every error raised by the Recommendation Engine.

    Named with a trailing underscore for the same reason
    `evaluation.errors.EvaluationError_` is: to avoid shadowing a
    built-in-shaped name at a glance.
    """
