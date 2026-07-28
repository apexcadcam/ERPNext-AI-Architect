"""The Pattern Aggregation Engine exception hierarchy.

Mirrors `evidence.errors.EvidenceError_`'s own trailing-underscore-base
convention exactly (Pattern Aggregation Engine Architecture Specification
v1.0's error conventions).

This base has no concrete subtype in this Sprint. Per §10, no ordinary
data path raises: a category with no registered resolver, or one whose
resolver returns a zero population, is recorded as a `SkippedAggregation`
inside the returned `PatternSet` rather than raised. `AggregationError_`
exists so that malformed *persisted input* (§6's `read_pattern_set`)
surfaces as this package's own type rather than a raw `json` or
`pydantic` error.
"""

from __future__ import annotations


class AggregationError_(Exception):
    """Base class for every error raised by the Pattern Aggregation Engine.

    Named with a trailing underscore for the same reason
    `evidence.errors.EvidenceError_` is: to avoid shadowing a
    built-in-shaped name at a glance.
    """
