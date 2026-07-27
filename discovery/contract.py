"""Repository Discovery's own contract: the one fixed set of types every
stage produces and consumes, and the final `RepositoryInventory` artifact
callers receive.

Implements Repository Discovery Engine Specification v1.1 §2 and §4 in
full. Every model is frozen, matching every other contract in this
project (`integration.contract.ConnectorManifest`, `planning.contract.Goal`,
`orchestration.contract.GoalRunResult`, ...).
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field

#: §2's Input defaults — overridable per request.
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (".git", "node_modules", "__pycache__", ".venv", ".pytest_cache")
DEFAULT_MAX_FILES: int = 10_000
DEFAULT_TIMEOUT_SECONDS: float = 30.0


class DiscoveryRequest(BaseModel):
    """§2's Input. `repository_root` is already a resolved, concrete
    filesystem path — Target Resolution (turning a goal token like
    "apex-dashboard" into this path) is a separate, still-missing
    capability per the Capability Discovery Report, never Discovery's own
    responsibility.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_root: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS
    max_files: int = Field(default=DEFAULT_MAX_FILES, ge=1)
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)


class DiscoveryFileError(BaseModel):
    """One path that failed during the walk without aborting the whole
    run — §6's "partial scan" outcome, made visible in the artifact
    itself rather than swallowed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RepositoryFileType(str, enum.Enum):
    """§3a's closed classification vocabulary. Evaluated in a fixed
    precedence order (`discovery.engine`'s own `_CLASSIFICATION_RULES`) —
    never a free string, so no two runs (or two downstream consumers) can
    drift on what a given path "counts as."
    """

    HOOK = "hook"
    TEST = "test"
    DOCTYPE = "doctype"
    CONFIG = "config"
    README = "readme"
    JSON = "json"
    PYTHON_SOURCE = "python_source"
    TEMPLATE = "template"
    STATIC = "static"
    UNKNOWN = "unknown"


class DiscoveredFile(BaseModel):
    """One classified file. `relative_path` is kept so a future capability
    can `read_text()` this exact path from the same root on demand —
    Discovery itself never stores file bodies (§4).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1)
    file_type: RepositoryFileType
    size_bytes: int = Field(ge=0)
    is_binary: bool


class RepositoryStatistics(BaseModel):
    """§4's deterministic, purely structural metadata — counts and sums
    only, never a semantic judgment.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_files: int = Field(ge=0)
    total_directories: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    files_by_type: dict[RepositoryFileType, int]
    largest_file_size: int = Field(ge=0)
    largest_file_path: str | None = None


class RepositoryMetadata(BaseModel):
    """§4's deterministic repository-level metadata. Every field is
    derived from path/extension histograms or fixed, named marker-file
    *presence* checks only — never from file content, never from
    reasoning. `detected_frameworks` in particular is a best-effort
    structural signal, not a verified fact (§4's own disclosed caveat).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_name: str = Field(min_length=1)
    detected_languages: tuple[str, ...] = ()
    detected_frameworks: tuple[str, ...] = ()
    top_level_directories: tuple[str, ...] = ()
    entry_point_candidates: tuple[str, ...] = ()


class RepositoryInventory(BaseModel):
    """§4's final artifact — the one thing `discover_repository()`
    returns. Determinism (§5): two runs against byte-for-byte identical
    repository contents produce an identical `RepositoryInventory` in
    every field except `inventory_id`, `discovered_at`, and
    `correlation_id`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    inventory_id: str = Field(min_length=1)
    repository_root: str = Field(min_length=1)
    discovered_at: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    files: tuple[DiscoveredFile, ...]
    truncated: bool
    excluded_paths: tuple[str, ...]
    errors: tuple[DiscoveryFileError, ...]
    statistics: RepositoryStatistics
    metadata: RepositoryMetadata
