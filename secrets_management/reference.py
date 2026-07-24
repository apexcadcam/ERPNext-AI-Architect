"""`credential_reference` parsing.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8.2: a `credential_reference` is
a scheme-prefixed string identifying both *where* to resolve a secret and
*which* backend understands that scheme — `env://VAR_NAME`,
`dotenv://VAR_NAME`, and (not implemented in Phase 1) `profile://...`,
`vault://...`.

A `CredentialReference` is never the secret itself, and this module never
touches a backend or a filesystem — it only parses the string shape, per
the same "resolution is a separate, later step" discipline
docs/runtime/CONFIGURATION_SYSTEM.md §6 already applies to configuration
values that merely *point at* a secret.
"""

from __future__ import annotations

from dataclasses import dataclass

from secrets_management.errors import InvalidCredentialReferenceError


@dataclass(frozen=True)
class CredentialReference:
    """A parsed `scheme://key` pointer. Never carries a resolved value."""

    scheme: str
    key: str


def parse_credential_reference(raw: str) -> CredentialReference:
    """Parses `raw` as `scheme://key`. Raises `InvalidCredentialReferenceError`
    if `raw` has no `://` separator, or either side of it is empty.
    """

    if "://" not in raw:
        raise InvalidCredentialReferenceError(
            f"credential reference '{raw}' is not shaped 'scheme://key' (missing '://')"
        )

    scheme, _, key = raw.partition("://")
    if not scheme:
        raise InvalidCredentialReferenceError(f"credential reference '{raw}' has an empty scheme")
    if not key:
        raise InvalidCredentialReferenceError(f"credential reference '{raw}' has an empty key")

    return CredentialReference(scheme=scheme, key=key)
