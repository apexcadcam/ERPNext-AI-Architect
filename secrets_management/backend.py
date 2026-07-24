"""The `SecretsBackend` contract every resolution backend implements.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8.2's "one fixed contract, many
backends, chosen by configuration" shape — the same pattern
docs/runtime/STORAGE_ABSTRACTION.md already uses for Storage Adapters,
applied here to secrets. A backend resolves one scheme only; which backend
serves which scheme is the `SecretsResolver`'s concern (resolver.py), never
a backend's own.
"""

from __future__ import annotations

from typing import Protocol


class SecretsBackend(Protocol):
    """`scheme` is the `credential_reference` prefix this backend answers
    for (e.g. `"env"` for `env://...`), without the trailing `://`.
    """

    scheme: str

    def resolve(self, key: str) -> str | None:
        """Returns the secret value for `key`, or `None` if this backend has
        no value for it. Never raises for "not found" — only `None`; a
        backend raises only for a genuine, unexpected failure (e.g. a
        malformed source it cannot even attempt to read).
        """
        ...
