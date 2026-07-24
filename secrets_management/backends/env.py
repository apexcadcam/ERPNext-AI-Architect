"""The `env://` backend — resolves a secret from the process's own OS
environment variables.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8.2's `env://` scheme: "The
process's own OS environment variables... CI, containerized deployments
where secrets are already injected by the orchestrator."
"""

from __future__ import annotations

import os


class EnvSecretsBackend:
    """Reads fresh from `os.environ` on every `resolve()` call — never
    snapshots the environment at construction time, so a value set after
    this backend is created is still visible.
    """

    scheme = "env"

    def resolve(self, key: str) -> str | None:
        return os.environ.get(key)
