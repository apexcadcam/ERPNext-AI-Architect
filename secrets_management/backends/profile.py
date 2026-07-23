"""The `profile://` backend — resolves `profile://<profile>/<key>` against
a Profile-scoped secrets file.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8.2's `profile://` scheme:
"A named Profile's own scoped secrets file." Reuses `DotenvSecretsBackend`
(Phase 1, frozen, unmodified) for the actual `KEY=VALUE` parsing — a
Profile's secrets file is the same minimal format as a `.env` file, just
addressed by profile name instead of a fixed path, so that format is not
reinvented here.

Per SPRINT3_ARCHITECTURE_PACKAGE.md §8.4/§14: each Profile's file is
expected at `<profiles_dir>/<profile>.secrets`, a location `.gitignore`
already excludes (`profiles/*.secrets`, added in Phase 1) — this backend
never writes that file, only reads it.
"""

from __future__ import annotations

from pathlib import Path

from secrets_management.backends.dotenv import DotenvSecretsBackend
from secrets_management.errors import InvalidCredentialReferenceError
from secrets_management.profile import InvalidProfileNameError, Profile


class ProfileSecretsBackend:
    """`key`, as received from `SecretsResolver`, is the full
    `"<profile>/<secret_key>"` remainder of a `profile://<profile>/<key>`
    reference — `parse_credential_reference` (Phase 1, unmodified) treats
    everything after `profile://` as one opaque key; this backend is what
    splits it into a profile name and a secret key.

    Cross-profile isolation is structural, not merely conventional: this
    backend only ever opens the one file `<profile>/...` names, per
    SPRINT3_ARCHITECTURE_PACKAGE.md §14's "nothing in the Secrets Resolver
    contract allows cross-profile resolution."
    """

    scheme = "profile"

    def __init__(self, profiles_dir: Path) -> None:
        self._profiles_dir = profiles_dir

    def resolve(self, key: str) -> str | None:
        profile_name, separator, secret_key = key.partition("/")
        if not separator or not secret_key:
            raise InvalidCredentialReferenceError(
                f"profile credential reference 'profile://{key}' is not shaped 'profile://<profile>/<key>'"
            )

        try:
            profile = Profile(profile_name)
        except InvalidProfileNameError as exc:
            raise InvalidCredentialReferenceError(
                f"profile credential reference 'profile://{key}' names an invalid profile: {exc}"
            ) from exc

        backend = DotenvSecretsBackend(self._profile_file(profile))
        return backend.resolve(secret_key)

    def _profile_file(self, profile: Profile) -> Path:
        return self._profiles_dir / f"{profile.name}.secrets"
