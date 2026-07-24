"""The `dotenv://` backend — resolves a secret from a local `.env` file.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §8.2's `dotenv://` scheme:
"A local `.env` file (never committed)... local development."

A minimal `KEY=VALUE` parser, deliberately — not a full dotenv-format
implementation. Supports one entry per line, blank lines, `#`-prefixed
comment lines, an optional leading `export ` (common in hand-written `.env`
files), and one layer of matching `'...'`/`"..."` quoting around a value.
Does not support inline comments, multi-line values, or variable
interpolation — none of Phase 1's own requirements need them, and adding
support nobody asked for is exactly what this project's own YAGNI
discipline (R009) argues against, applied here to its own tooling.
"""

from __future__ import annotations

from pathlib import Path


class DotenvSecretsBackend:
    """Re-reads and re-parses `dotenv_path` on every `resolve()` call —
    never caches file contents, so an edited `.env` file is picked up
    without restarting anything. A missing file is not an error at this
    layer: `resolve()` simply returns `None` for every key, the same as an
    empty file would, per SecretsBackend's own "no value found -> None,
    never raise" contract.
    """

    scheme = "dotenv"

    def __init__(self, dotenv_path: Path) -> None:
        self._dotenv_path = dotenv_path

    def resolve(self, key: str) -> str | None:
        return self._parse().get(key)

    def _parse(self) -> dict[str, str]:
        if not self._dotenv_path.is_file():
            return {}

        values: dict[str, str] = {}
        for raw_line in self._dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            line = line.removeprefix("export ").strip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]

            if key:
                values[key] = value

        return values
