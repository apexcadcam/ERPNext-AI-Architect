"""Repository Discovery — Sprint 16.

Implements the Repository Discovery Engine Specification v1.1 in full:
given a resolved, concrete filesystem path, recursively enumerates its
contents (respecting exclusion patterns and size/time budgets), classifies
each entry by a fixed, deterministic rule (never by content
interpretation), and produces one self-contained `RepositoryInventory`
artifact. Zero Reasoning Engine calls anywhere in this package.

Depends only on `integration.contract`/
`integration.connectors.filesystem.connector` (for `FilesystemConnector`,
constructed directly rather than discovered via `ConnectorRegistry` — see
`discovery.engine.resolve_connector`'s own docstring for why) and
`runtime.pipeline.engine`/`runtime.modules.base`/`runtime.modules.manifest`/
`runtime.container.di`. Nothing in this package imports `analysis/`,
`knowledge/`, `intelligence/`, `planning/`, `execution/`, `orchestration/`,
or `composition_root/`.
"""

from __future__ import annotations

from discovery.contract import (
    DiscoveredFile,
    DiscoveryFileError,
    DiscoveryRequest,
    RepositoryFileType,
    RepositoryInventory,
    RepositoryMetadata,
    RepositoryStatistics,
)
from discovery.engine import discover_repository
from discovery.errors import DiscoveryError_, RepositoryAccessError, RepositoryNotFoundError

__all__ = [
    "DiscoveredFile",
    "DiscoveryError_",
    "DiscoveryFileError",
    "DiscoveryRequest",
    "RepositoryAccessError",
    "RepositoryFileType",
    "RepositoryInventory",
    "RepositoryMetadata",
    "RepositoryNotFoundError",
    "RepositoryStatistics",
    "discover_repository",
]
