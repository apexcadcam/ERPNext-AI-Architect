"""Repository Discovery's own stage logic.

Implements Repository Discovery Engine Specification v1.1 §3 exactly:
four deterministic stages, zero Reasoning Engine calls, `FilesystemConnector`
reuse per the "direct construction" precedent `composition_root/root.py`
already establishes for `PlanningModule` (see `resolve_connector`'s own
docstring below for the identical reasoning, applied here).

Two real, implementation-time findings are disclosed inline rather than
folding a design change back into the frozen v1.1 specification, per this
Sprint's own instruction to document a revealed problem separately rather
than change the design:

1. `FilesystemConnector` exposes no `is_dir()`/stat-shaped operation, only
   `read_text`/`write_text`/`exists`/`list_directory`. File-vs-directory
   determination during the walk is therefore done by attempting
   `list_directory()` on each discovered name: success means a directory
   (recurse), `NotADirectoryError` means a leaf file — reusing the
   connector's existing, unmodified API rather than adding a new method
   to it.
2. `size_bytes` cannot be obtained through the connector at all (no size
   operation exists, and reading file content via `read_text()` to
   measure it would both defeat the point of deferring content reads and
   crash on any binary file). Since Stage 1 already validates
   `repository_root` is a real, existing directory via the connector's
   own `connect()`, `classify_entries` re-derives each file's absolute
   path as `Path(repository_root) / relative_path` and stats it directly
   — still read-only, still confined to paths the connector's own
   `list_directory` already enumerated, but not routed through the
   connector object itself.

`resolve_connector`, `walk_tree`, `classify_entries`, `compute_statistics`,
`compute_metadata`, and `assemble_inventory` are package-internal, shared
between `discover_repository()` (this module's own public interface) and
`discovery.module`'s Container-registered stage wrappers — they are not
part of the Specification's own Public Contract (§2), which names exactly
three interfaces: `discover_repository`, `DiscoveryModule`, and
`DISCOVERY_REPOSITORY_PIPELINE`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from integration.connectors.filesystem.connector import FilesystemConnector
from integration.contract import ConnectorManifest
from integration.errors import ConnectorLifecycleError

from discovery.contract import (
    DiscoveredFile,
    DiscoveryFileError,
    DiscoveryRequest,
    RepositoryFileType,
    RepositoryInventory,
    RepositoryMetadata,
    RepositoryStatistics,
)
from discovery.errors import RepositoryAccessError, RepositoryNotFoundError

# -- §3a Classification Priority — evaluated top to bottom, first match wins -----------------------

_CONFIG_FILENAMES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "tsconfig.json",
        "requirements.txt",
        "Pipfile",
        "MANIFEST.in",
    }
)
_CONFIG_EXTENSIONS = frozenset({".cfg", ".ini", ".toml"})
_TEMPLATE_EXTENSIONS = frozenset({".html", ".jinja", ".j2"})
_STATIC_EXTENSIONS = frozenset(
    {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf"}
)
#: Extensions never assumed to be safely decodable text — deliberately
#: distinct from, and a subset of, `_STATIC_EXTENSIONS` above (`.css`/`.js`
#: are static but textual, not binary).
_BINARY_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".pyc"}
)

_LANGUAGE_BY_EXTENSION = {".py": "python", ".js": "javascript", ".ts": "typescript"}
#: §4's fixed entry-point candidate list — presence only, nothing inferred.
_ENTRY_POINT_CANDIDATE_NAMES: tuple[str, ...] = (
    "hooks.py",
    "__init__.py",
    "manage.py",
    "main.py",
    "app.py",
    "cli.py",
)


def _classify(relative_path: str) -> RepositoryFileType:
    """§3a's ordered precedence table. A specific rule (e.g. rule 1,
    `hooks.py`) is always checked, and can therefore always match, before
    a more generic one (e.g. rule 7, `*.py`) — the exact
    `hooks.py`-before-`*.py` guarantee the specification requires.
    """

    path = Path(relative_path)
    name = path.name
    parts = path.parts
    suffix = path.suffix.lower()
    stem_lower = path.stem.lower()

    if name == "hooks.py":
        return RepositoryFileType.HOOK
    if "tests" in parts or "test" in parts or name.startswith("test_") or name.endswith("_test.py"):
        return RepositoryFileType.TEST
    if suffix == ".json" and "doctype" in parts:
        return RepositoryFileType.DOCTYPE
    if name in _CONFIG_FILENAMES or suffix in _CONFIG_EXTENSIONS:
        return RepositoryFileType.CONFIG
    if stem_lower == "readme":
        return RepositoryFileType.README
    if suffix == ".json":
        return RepositoryFileType.JSON
    if suffix == ".py":
        return RepositoryFileType.PYTHON_SOURCE
    if suffix in _TEMPLATE_EXTENSIONS or "templates" in parts:
        return RepositoryFileType.TEMPLATE
    if suffix in _STATIC_EXTENSIONS:
        return RepositoryFileType.STATIC
    return RepositoryFileType.UNKNOWN


# -- Stage 1: Root Resolution ------------------------------------------------------------------------


def resolve_connector(repository_root: str) -> FilesystemConnector:
    """§3 Stage 1. Constructs an **in-memory** `ConnectorManifest` and
    instantiates `FilesystemConnector` directly, rather than discovering
    one from a `connector.yaml` file via `ConnectorRegistry`.

    `ConnectorRegistry.discover()` is the right mechanism for a fixed,
    known-ahead-of-time integration — Repository Discovery's root is
    chosen per goal, not known ahead of time, so no fixed `connector.yaml`
    could declare it. This mirrors the exact, already-established
    precedent `composition_root/root.py` documents for `PlanningModule`:
    "there is no way to route [per-call data] through [the standard
    factory]," so it constructs the module directly instead of through
    `PluginRegistry.instantiate()`. The same move, applied here, to
    `FilesystemConnector` — same class, same four methods, same
    root-containment security check, just built from an in-memory
    manifest instead of a YAML file. Nothing in `integration/` changes.
    """

    manifest = ConnectorManifest(
        connector_id="filesystem.discovery",
        display_name="Repository Discovery Filesystem Access",
        maintained_by="discovery",
        target_system_type="filesystem",
        version="0.1.0",
        endpoint_kind="local_path",
        endpoint_reference=repository_root,
        entry_point="connector:create",
    )
    connector = FilesystemConnector(manifest)
    try:
        connector.connect()
    except ConnectorLifecycleError as exc:
        raise RepositoryNotFoundError(str(exc)) from exc
    except OSError as exc:
        raise RepositoryAccessError(str(exc)) from exc
    return connector


# -- Stage 2: Tree Walk ------------------------------------------------------------------------------


@dataclass(frozen=True)
class _WalkResult:
    """Package-internal only — never leaves `engine.py`."""

    relative_paths: tuple[str, ...]
    truncated: bool
    errors: tuple[DiscoveryFileError, ...]
    directory_count: int
    top_level_directories: tuple[str, ...]


def walk_tree(
    connector: FilesystemConnector,
    *,
    exclude_patterns: Sequence[str],
    max_files: int,
    timeout_seconds: float,
) -> _WalkResult:
    """§3 Stage 2. Recursively enumerates `connector`'s root using only
    its existing, unmodified `list_directory(path)` (single-level) —
    Discovery performs the recursion itself, since the connector is
    deliberately kept minimal (its own docstring: "no recursive copy").

    File-vs-directory determination (finding 1, module docstring):
    attempts `list_directory()` on every discovered name; a
    `NotADirectoryError` means it is a leaf file.

    Traversal is depth-first, in sorted order at every level (§5
    Determinism) — `FilesystemConnector.list_directory` already returns a
    sorted tuple; the explicit `sorted()` below re-states that guarantee
    in this function's own code rather than relying silently on the
    connector's internal behavior.
    """

    relative_paths: list[str] = []
    walk_errors: list[DiscoveryFileError] = []
    top_level_directories: list[str] = []
    directory_count = 0
    truncated = False
    deadline = time.monotonic() + timeout_seconds
    exclude = frozenset(exclude_patterns)

    def visit(directory: str) -> None:
        nonlocal truncated, directory_count
        if truncated:
            # Structurally unreachable given this function's own control
            # flow: every path that sets truncated=True returns
            # immediately from its own frame, and the *only* other call
            # site that could re-enter visit() (the sibling-name loop
            # below) re-checks the same budget condition before ever
            # calling visit() again -- so visit() is never invoked a
            # second time after truncated is set. Kept as a defensive,
            # disclosed guard rather than a silent assumption, mirroring
            # composition_root/root.py's own identical
            # "# pragma: no cover - structurally unreachable" precedent.
            return  # pragma: no cover - structurally unreachable
        try:
            names = connector.list_directory(directory)
        except OSError as exc:
            walk_errors.append(DiscoveryFileError(relative_path=directory or ".", reason=str(exc)))
            return

        for name in sorted(names):
            if name in exclude:
                continue
            if time.monotonic() > deadline or len(relative_paths) >= max_files:
                truncated = True
                return

            child = name if directory in ("", ".") else f"{directory}/{name}"
            try:
                connector.list_directory(child)
            except NotADirectoryError:
                relative_paths.append(child)
            except OSError as exc:
                walk_errors.append(DiscoveryFileError(relative_path=child, reason=str(exc)))
            else:
                directory_count += 1
                if directory in ("", "."):
                    top_level_directories.append(name)
                visit(child)

    visit(".")

    return _WalkResult(
        relative_paths=tuple(relative_paths),
        truncated=truncated,
        errors=tuple(walk_errors),
        directory_count=directory_count,
        top_level_directories=tuple(sorted(top_level_directories)),
    )


# -- Stage 3: Content Classification -------------------------------------------------------------------


def classify_entries(repository_root: str, relative_paths: Sequence[str]) -> tuple[DiscoveredFile, ...]:
    """§3 Stage 3. Classifies each path by `_classify`'s fixed rule table
    and stats it for size (finding 2, module docstring) — never reads
    file content, so a corrupted or otherwise unreadable file body is not
    reachable here (§6).
    """

    root = Path(repository_root)
    files = []
    for relative_path in sorted(relative_paths):
        size_bytes = (root / relative_path).stat().st_size
        files.append(
            DiscoveredFile(
                relative_path=relative_path,
                file_type=_classify(relative_path),
                size_bytes=size_bytes,
                is_binary=Path(relative_path).suffix.lower() in _BINARY_EXTENSIONS,
            )
        )
    return tuple(files)


# -- Stage 4: Inventory Assembly -----------------------------------------------------------------------


def compute_statistics(files: tuple[DiscoveredFile, ...], directory_count: int) -> RepositoryStatistics:
    files_by_type: dict[RepositoryFileType, int] = {}
    total_size = 0
    largest_size = 0
    largest_path: str | None = None
    for discovered_file in files:
        files_by_type[discovered_file.file_type] = files_by_type.get(discovered_file.file_type, 0) + 1
        total_size += discovered_file.size_bytes
        if discovered_file.size_bytes > largest_size:
            largest_size = discovered_file.size_bytes
            largest_path = discovered_file.relative_path
    return RepositoryStatistics(
        total_files=len(files),
        total_directories=directory_count,
        total_size_bytes=total_size,
        files_by_type=files_by_type,
        largest_file_size=largest_size,
        largest_file_path=largest_path,
    )


def compute_metadata(
    repository_root: str,
    top_level_directories: Sequence[str],
    files: tuple[DiscoveredFile, ...],
) -> RepositoryMetadata:
    names = {Path(f.relative_path).name for f in files}
    extensions = {Path(f.relative_path).suffix.lower() for f in files}

    detected_languages = tuple(
        sorted({_LANGUAGE_BY_EXTENSION[ext] for ext in extensions if ext in _LANGUAGE_BY_EXTENSION})
    )

    frameworks: list[str] = []
    if "hooks.py" in names and "modules.txt" in names:
        frameworks.append("frappe")
    if "package.json" in names:
        frameworks.append("node")
    if "pyproject.toml" in names or "setup.py" in names:
        frameworks.append("python-packaging")

    entry_point_candidates = tuple(name for name in _ENTRY_POINT_CANDIDATE_NAMES if name in names)

    return RepositoryMetadata(
        repository_name=Path(repository_root).name,
        detected_languages=detected_languages,
        detected_frameworks=tuple(sorted(frameworks)),
        top_level_directories=tuple(top_level_directories),
        entry_point_candidates=entry_point_candidates,
    )


def assemble_inventory(
    request: DiscoveryRequest, walk_result: _WalkResult, files: tuple[DiscoveredFile, ...]
) -> RepositoryInventory:
    """§3 Stage 4. Pure aggregation over `files` (already produced by the
    separate `classify_entries` stage) — no new file reads of its own.
    """

    statistics = compute_statistics(files, walk_result.directory_count)
    metadata = compute_metadata(request.repository_root, walk_result.top_level_directories, files)

    return RepositoryInventory(
        inventory_id=str(uuid.uuid4()),
        repository_root=request.repository_root,
        discovered_at=datetime.now(UTC).isoformat(),
        correlation_id=request.correlation_id,
        files=files,
        truncated=walk_result.truncated,
        excluded_paths=tuple(sorted(request.exclude_patterns)),
        errors=tuple(sorted(walk_result.errors, key=lambda e: e.relative_path)),
        statistics=statistics,
        metadata=metadata,
    )


# -- §2's public interface: the plain-function composition of all four stages --------------------------


def discover_repository(request: DiscoveryRequest) -> RepositoryInventory:
    """The single, plain-function composition of all four stages — §2's
    first interface: no Container, no Module, no Pipeline Engine required.
    """

    connector = resolve_connector(request.repository_root)
    walk_result = walk_tree(
        connector,
        exclude_patterns=request.exclude_patterns,
        max_files=request.max_files,
        timeout_seconds=request.timeout_seconds,
    )
    files = classify_entries(request.repository_root, walk_result.relative_paths)
    return assemble_inventory(request, walk_result, files)
