"""Secrets Resolver — Sprint 3, Phase 1.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8's `credential_reference`
resolution mechanism: `env://` and `dotenv://` schemes only, per §18's
Migration Strategy ("Secrets Resolver — env://dotenv:// only. Nothing else
in this package can be exercised end-to-end without it, and it has no
dependency on anything else here."). `profile://` and `vault://` are
architecturally named but not implemented until a later phase.

Package name note: the architecture package's own §3.1 reserves this code
under a top-level `secrets/` directory. That name collides with Python's
standard-library `secrets` module (used internally by, among others,
`uuid` and `tempfile`) — installing a top-level package named `secrets`
would shadow it for every import in this environment, not just this
project's own code. This package is named `secrets_management` instead, a
disclosed, minimal deviation from the architecture document's literal
folder name, not a functional or architectural change to what it does.
"""

from __future__ import annotations

from secrets_management.backend import SecretsBackend
from secrets_management.backends import DotenvSecretsBackend, EnvSecretsBackend
from secrets_management.errors import InvalidCredentialReferenceError, SecretResolutionError
from secrets_management.reference import CredentialReference, parse_credential_reference
from secrets_management.resolver import SecretsResolver

__all__ = [
    "CredentialReference",
    "DotenvSecretsBackend",
    "EnvSecretsBackend",
    "InvalidCredentialReferenceError",
    "SecretResolutionError",
    "SecretsBackend",
    "SecretsResolver",
    "parse_credential_reference",
]
