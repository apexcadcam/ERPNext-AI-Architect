"""Errors raised while parsing or resolving a `credential_reference`.

Mirrors runtime/errors.py's discipline: one narrow exception per failure
category, never a bare `Exception`, and never carrying a resolved secret
value in its message — only the reference (a pointer, never sensitive
itself, per SPRINT3_ARCHITECTURE_PACKAGE.md §8.2) and diagnostic context.
"""

from __future__ import annotations


class InvalidCredentialReferenceError(ValueError):
    """A `credential_reference` string is not shaped `scheme://key`."""


class SecretResolutionError(LookupError):
    """A well-formed `credential_reference` could not be resolved to a value —
    either no backend is registered for its scheme, or the backend found
    nothing at the given key. Never includes a secret value, by construction:
    resolution failed, so there was never a value to include.
    """
