"""The Secrets Resolver: resolves a `credential_reference` to a value,
just-in-time, by dispatching to whichever registered backend serves its
scheme.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8.2 and §8.5. This class never
caches a resolved value across calls — every `resolve()` call re-invokes the
owning backend, so a secret is never held in `SecretsResolver`'s own state
longer than one call's return value, per §8.5's "never resolved-and-cached...
resolved just-in-time." No backend is registered by default: an empty
`SecretsResolver` resolves nothing, per the same "no default 'always
succeeds' implementation" discipline knowledge/validation/providers.py
already established for this project's other injectable seams — a caller
must explicitly register the backends it actually wants.
"""

from __future__ import annotations

from secrets_management.backend import SecretsBackend
from secrets_management.errors import SecretResolutionError
from secrets_management.reference import parse_credential_reference


class SecretsResolver:
    """Owns zero state about any individual secret — only which backend
    answers for which scheme.
    """

    def __init__(self) -> None:
        self._backends: dict[str, SecretsBackend] = {}

    def register(self, backend: SecretsBackend, *, override: bool = False) -> None:
        """Registers `backend` for its own declared `scheme`. Raises
        `ValueError` if that scheme already has a backend, unless
        `override=True` — the same test-double seam
        docs/runtime/DEPENDENCY_INJECTION.md §4 already establishes for the
        Runtime Container, applied here.
        """

        if backend.scheme in self._backends and not override:
            raise ValueError(
                f"a backend is already registered for scheme '{backend.scheme}://' "
                f"(pass override=True to replace it)"
            )
        self._backends[backend.scheme] = backend

    def resolve(self, credential_reference: str) -> str:
        """Resolves `credential_reference` (e.g. `"env://API_KEY"`) to its
        value. Raises `InvalidCredentialReferenceError` if the reference
        string is malformed, or `SecretResolutionError` if no backend is
        registered for its scheme, or the backend found nothing for its key.
        """

        reference = parse_credential_reference(credential_reference)
        backend = self._backends.get(reference.scheme)
        if backend is None:
            raise SecretResolutionError(
                f"no backend registered for scheme '{reference.scheme}://' "
                f"(reference: '{credential_reference}')"
            )

        value = backend.resolve(reference.key)
        if value is None:
            raise SecretResolutionError(
                f"credential reference '{credential_reference}' could not be resolved"
            )
        return value
