"""The Requirement Synthesis exception hierarchy.

Mirrors `discovery.errors.DiscoveryError_`'s own trailing-underscore-base
convention exactly (Requirement Synthesis Engine Specification v1.1 §2's
"Errors").

Raised only for a failure at the repository *root* itself. A failure on a
single file (malformed source, unreadable file) is never raised — it is
recorded as an `UnresolvedFact` inside the returned `RepositoryFacts`
instead (§7, "partial synthesis").
"""

from __future__ import annotations


class SynthesisError_(Exception):
    """Base class for every error raised by Requirement Synthesis.

    Named with a trailing underscore for the same reason
    `discovery.errors.DiscoveryError_` is: to avoid shadowing a
    built-in-shaped name at a glance.
    """


class RepositoryInventoryStaleError(SynthesisError_):
    """`repository_inventory.repository_root` no longer exists or is not
    readable at synthesis time -- a TOCTOU case, since Synthesis may run
    long after the Discovery run that produced its input.
    """
