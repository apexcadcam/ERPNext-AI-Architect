"""Secrets Resolver — Sprint 3, Phases 1–2.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8's `credential_reference`
resolution mechanism. Phase 1: `env://` and `dotenv://`. Phase 2:
`profile://`, and the Profile convention (§8.3/§9.1) — a Profile is a named
Environment-layer value, never a new configuration layer. `vault://` is
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
from secrets_management.backends import DotenvSecretsBackend, EnvSecretsBackend, ProfileSecretsBackend
from secrets_management.errors import InvalidCredentialReferenceError, SecretResolutionError
from secrets_management.profile import InvalidProfileNameError, Profile
from secrets_management.reference import CredentialReference, parse_credential_reference
from secrets_management.resolver import SecretsResolver

__all__ = [
    "CredentialReference",
    "DotenvSecretsBackend",
    "EnvSecretsBackend",
    "InvalidCredentialReferenceError",
    "InvalidProfileNameError",
    "Profile",
    "ProfileSecretsBackend",
    "SecretResolutionError",
    "SecretsBackend",
    "SecretsResolver",
    "parse_credential_reference",
]
