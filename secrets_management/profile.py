"""Profiles: named Environment-layer values, not a new configuration layer.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8.3 / §9.1 / ADR-0008: a Profile
("Development", "Production", "Customer A", "Customer B", "Local ERP",
"Cloud ERP", or any other operator-chosen name) is an arbitrary,
never-hardcoded identifier — the same identifier
docs/runtime/CONFIGURATION_SYSTEM.md § 2's existing Environment layer
already accepts today, since that layer's own text already treats
`dev`/`staging`/`production` as illustrative examples, not a closed enum.

This module never imports from, or otherwise touches, `runtime/config/` —
`Profile.environment_value` documents the mapping (a Profile's name *is*
the value a caller passes as `ConfigLoader(environment=...)`) without this
package taking on a dependency on `runtime/`, which Phase 2 does not
introduce. Wiring an active Profile into a running Configuration System
resolution is a caller's own responsibility, not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidProfileNameError(ValueError):
    """A profile name is empty, whitespace-only, or contains `/` (the
    `profile://<profile>/<key>` separator, per §8.2). Never raised for a
    name simply being unrecognized — this project defines no fixed set of
    valid profile names to check against.
    """


@dataclass(frozen=True)
class Profile:
    """An arbitrary, operator-chosen identifier — with no meaning to this
    module beyond being a valid Environment-layer value and a valid
    `profile://<profile>/<key>` path segment.
    """

    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidProfileNameError("profile name must not be empty or whitespace-only")
        if "/" in self.name:
            raise InvalidProfileNameError(
                f"profile name '{self.name}' must not contain '/' "
                f"(reserved as the profile://<profile>/<key> separator)"
            )

    @property
    def environment_value(self) -> str:
        """The value to pass as `environment=` to a Configuration System
        resolution (e.g. `runtime.config.loader.ConfigLoader`) — an
        identity mapping, per ADR-0008: a Profile *is* an Environment-layer
        value, not a separate concept. Stated explicitly here so the
        relationship is documented in code, not only in the architecture
        package.
        """
        return self.name
