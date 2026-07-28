"""Evidence Extraction Engine's own orchestration.

Implements Evidence Extraction Engine Architecture Specification v1.1 §8
exactly: walk, parse, collect, sort, assemble -- five deterministic steps,
zero Reasoning Engine calls, zero pattern aggregation, zero confidence
computation. This module orchestrates `evidence.collectors`' two existing
collectors; it contains no collection logic of its own.

`resolve_connector` mirrors `discovery.engine.resolve_connector`'s own
"direct construction" precedent exactly: an in-memory `ConnectorManifest`,
`FilesystemConnector` instantiated directly, no `connector.yaml`, no
`ConnectorRegistry.discover()` -- the same reasoning `composition_root/
root.py` already established for `PlanningModule`, applied here to a
second, independent lineage.

`_walk_all_files` mirrors `discovery.engine.walk_tree`'s own recursive
`list_directory`-based traversal technique almost exactly (same
file-vs-directory determination via `NotADirectoryError`, same
depth-first sorted-order recursion, same deadline/count budget) --
walking every file, not just `.py` ones, so `EvidenceStatistics.
files_skipped` carries real meaning (non-`.py` files walked but not
examined further), distinct from `files_failed` (`.py` files that were
examined but failed to parse).
"""

from __future__ import annotations

import ast
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from integration.connectors.filesystem.connector import FilesystemConnector
from integration.contract import ConnectorManifest
from integration.errors import ConnectorLifecycleError

from evidence.collectors import (
    _FileContext,
    collect_controller_lifecycle_hook_evidence,
    collect_whitelisted_api_decoration_evidence,
)
from evidence.contract import (
    Evidence,
    EvidenceExtractionError,
    EvidenceExtractionRequest,
    EvidenceSet,
    EvidenceStatistics,
)
from evidence.errors import EvidenceError_

#: §6.10's fixed schema version for this Sprint's contract shape. Bumped
#: only when `Evidence`'s own fields change.
_SCHEMA_VERSION = "1.0"


# -- Step 1: Root Resolution --------------------------------------------------------------------------


def resolve_connector(source_root: str) -> FilesystemConnector:
    """§8 Step 1. Constructs an **in-memory** `ConnectorManifest` and
    instantiates `FilesystemConnector` directly -- the same
    "direct construction" precedent `discovery.engine.resolve_connector`
    already establishes, applied here to Evidence Extraction's own,
    independent lineage.
    """

    manifest = ConnectorManifest(
        connector_id="filesystem.evidence",
        display_name="Evidence Extraction Filesystem Access",
        maintained_by="evidence",
        target_system_type="filesystem",
        version="0.1.0",
        endpoint_kind="local_path",
        endpoint_reference=source_root,
        entry_point="connector:create",
    )
    connector = FilesystemConnector(manifest)
    try:
        connector.connect()
    except (ConnectorLifecycleError, OSError) as exc:
        raise EvidenceError_(str(exc)) from exc
    return connector


# -- Step 2: Tree Walk ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _WalkResult:
    """Package-internal only -- never leaves `engine.py`."""

    relative_paths: tuple[str, ...]
    truncated: bool


def _walk_all_files(connector: FilesystemConnector, *, max_files: int, timeout_seconds: float) -> _WalkResult:
    """§8 Step 2. Recursively enumerates every file under `connector`'s
    root, budgeted by `max_files`/`timeout_seconds`. Every file, not just
    `.py` ones -- `.py`-vs-not is decided one step later, so a non-`.py`
    file is genuinely "skipped", not silently absent from the walk.
    """

    relative_paths: list[str] = []
    truncated = False
    deadline = time.monotonic() + timeout_seconds

    def visit(directory: str) -> None:
        nonlocal truncated
        if truncated:
            return  # pragma: no cover - structurally unreachable, mirrors discovery.engine.walk_tree's own identical guard
        try:
            names = connector.list_directory(directory)
        except OSError:
            return

        for name in sorted(names):
            if time.monotonic() > deadline or len(relative_paths) >= max_files:
                truncated = True
                return

            child = name if directory in ("", ".") else f"{directory}/{name}"
            try:
                connector.list_directory(child)
            except NotADirectoryError:
                relative_paths.append(child)
            except OSError:
                continue
            else:
                visit(child)

    visit(".")

    return _WalkResult(relative_paths=tuple(relative_paths), truncated=truncated)


# -- Step 3: Parse + Step 4: Collect --------------------------------------------------------------------


def _collect_from_file(
    connector: FilesystemConnector,
    relative_path: str,
    context: _FileContext,
) -> tuple[tuple[Evidence, ...], EvidenceExtractionError | None]:
    """§8 Steps 3-4 for one already-known-`.py` file. A `SyntaxError` or
    `OSError` is caught and returned as an `EvidenceExtractionError` --
    never raised -- so one unparseable file never aborts the whole run
    (the same graceful-degradation precedent `synthesis.engine.
    extract_apis` already establishes for the identical exception pair).
    """

    try:
        content = connector.read_text(relative_path)
        tree = ast.parse(content, filename=relative_path)
    except (SyntaxError, OSError) as exc:
        return (), EvidenceExtractionError(relative_path=relative_path, reason=str(exc))

    hook_evidence = collect_controller_lifecycle_hook_evidence(tree, context)
    decoration_evidence = collect_whitelisted_api_decoration_evidence(tree, context)
    return hook_evidence + decoration_evidence, None


# -- Step 5: Stable Sort ---------------------------------------------------------------------------


def _sort_key(evidence: Evidence) -> tuple[str, str, int, str, str]:
    """§9's mandatory stable ordering:
    `(repository, relative_path, line, category, symbol)`. Filesystem
    traversal order is not guaranteed portable across platforms; without
    this explicit sort, `EvidenceSet.evidence`'s *order* (never its
    content) could vary between environments even when every element is
    identical.
    """

    return (
        evidence.source.repository.value,
        evidence.source.relative_path,
        evidence.source.line,
        evidence.category.value,
        evidence.symbol,
    )


# -- Public interface ------------------------------------------------------------------------------


def extract_evidence(request: EvidenceExtractionRequest) -> EvidenceSet:
    """§15's one public entry point. Composes Steps 1-6 exactly as §8
    specifies: resolve the connector, walk the tree, parse and collect
    per file, sort, assemble. Contains no collection logic, no pattern
    aggregation, no confidence computation, and no inference of any
    relationship between Evidence records -- every one of those is
    explicitly out of this Sprint's scope (§4, §5).
    """

    connector = resolve_connector(request.source_root)
    walk_result = _walk_all_files(
        connector, max_files=request.max_files, timeout_seconds=request.timeout_seconds
    )

    extracted_at = datetime.now(UTC).isoformat()
    all_evidence: list[Evidence] = []
    errors: list[EvidenceExtractionError] = []
    files_skipped = 0
    files_failed = 0

    for relative_path in walk_result.relative_paths:
        if not relative_path.endswith(".py"):
            files_skipped += 1
            continue

        context = _FileContext(
            repository=request.repository,
            version=request.version,
            commit=request.commit,
            relative_path=relative_path,
            collected_at=extracted_at,
        )
        evidence, error = _collect_from_file(connector, relative_path, context)
        if error is not None:
            errors.append(error)
            files_failed += 1
        else:
            all_evidence.extend(evidence)

    sorted_evidence = tuple(sorted(all_evidence, key=_sort_key))

    statistics = EvidenceStatistics(
        files_examined=len(walk_result.relative_paths),
        files_skipped=files_skipped,
        files_failed=files_failed,
        evidence_extracted=len(sorted_evidence),
    )

    return EvidenceSet(
        evidence_set_id=str(uuid.uuid4()),
        schema_version=_SCHEMA_VERSION,
        repository=request.repository,
        version=request.version,
        commit=request.commit,
        extracted_at=extracted_at,
        correlation_id=request.correlation_id,
        evidence=sorted_evidence,
        errors=tuple(errors),
        truncated=walk_result.truncated,
        statistics=statistics,
    )
