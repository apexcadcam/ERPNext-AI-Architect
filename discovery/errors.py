"""The Repository Discovery exception hierarchy.

Mirrors `integration.errors.IntegrationError_`/`execution.errors.ExecutionError_`'s
own trailing-underscore-base convention exactly (Repository Discovery
Engine Specification v1.1 §2's "Errors").

Both subclasses are raised only for a failure at the scan *root* itself.
A failure partway through a walk (a subdirectory permission error, a
broken symlink) is never raised — it is recorded as a `DiscoveryFileError`
inside the returned `RepositoryInventory` instead (§6, "partial scan").
"""

from __future__ import annotations


class DiscoveryError_(Exception):
    """Base class for every error raised by Repository Discovery.

    Named with a trailing underscore for the same reason
    `runtime.errors.RuntimeError_` is: to avoid shadowing a
    built-in-shaped name at a glance.
    """


class RepositoryNotFoundError(DiscoveryError_):
    """`repository_root` does not exist, or exists but is not a directory."""


class RepositoryAccessError(DiscoveryError_):
    """`repository_root` exists but is not readable."""
