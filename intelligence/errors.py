"""Shared Intelligence Abstraction Layer exception hierarchy — Sprint 8,
Phase 2.

Mirrors `planning/errors.py`'s and `execution/errors.py`'s established
discipline: each new package owns its own narrow exceptions, subclassing a
single trailing-underscore base rather than overloading another package's
hierarchy.
"""

from __future__ import annotations


class IntelligenceError_(Exception):
    """Base class for every error raised by the Intelligence Abstraction
    Layer.

    Named with a trailing underscore for the same reason
    `runtime.errors.RuntimeError_` is: to avoid shadowing a built-in-shaped
    name at a glance.
    """


class CitationError(IntelligenceError_):
    """Raised by `ValidatingIntelligenceEngine` the moment a wrapped
    `IntelligenceEngine`'s response cites an evidence or candidate id that
    was not present in the input it was actually given for that call —
    the closed-world enforcement of "the reasoning side must not invent
    knowledge." Raised immediately, never logged-and-continued, and never
    repaired by substituting a corrected response — a citation failure is
    a defect in the wrapped engine's output, not a recoverable condition.
    """
