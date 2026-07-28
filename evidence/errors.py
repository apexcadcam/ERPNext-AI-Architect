"""The Evidence Extraction Engine exception hierarchy.

Mirrors `recommendation.errors.RecommendationError_`'s own
trailing-underscore-base convention exactly (Evidence Extraction Engine
Architecture Specification v1.1's error conventions).

This base has no concrete subtype in this Sprint -- a file that fails to
parse is caught and recorded as an `EvidenceExtractionError` inside the
returned `EvidenceSet`, never raised to the caller (see
`evidence.engine.extract_evidence`).
"""

from __future__ import annotations


class EvidenceError_(Exception):
    """Base class for every error raised by the Evidence Extraction Engine.

    Named with a trailing underscore for the same reason
    `recommendation.errors.RecommendationError_` is: to avoid shadowing a
    built-in-shaped name at a glance.
    """
