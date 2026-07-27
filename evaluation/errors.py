"""The Architecture Evaluation exception hierarchy.

Mirrors `discovery.errors.DiscoveryError_`/`synthesis.errors.SynthesisError_`'s
own trailing-underscore-base convention exactly (Architecture Evaluation
Engine Specification v1.0 §2's "Errors").

Unlike `DiscoveryError_`/`SynthesisError_`, this base has no expected
concrete subtype raised in normal operation -- a genuine, positive
property, not a gap. This engine touches no filesystem, so there is no
root-level failure mode analogous to `RepositoryNotFoundError`/
`RepositoryInventoryStaleError`. The one thing that could go wrong -- a
single rule's own algorithm raising unexpectedly -- is caught and recorded
as a `SkippedRule` inside the returned artifact, never raised to the
caller (see `evaluation.engine.execute_rules`).
"""

from __future__ import annotations


class EvaluationError_(Exception):
    """Base class for every error raised by Architecture Evaluation.

    Named with a trailing underscore for the same reason
    `runtime.errors.RuntimeError_` is: to avoid shadowing a
    built-in-shaped name at a glance.
    """
