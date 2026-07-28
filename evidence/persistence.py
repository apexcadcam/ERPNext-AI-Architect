"""Evidence Extraction Engine's own persistence layer.

Implements Evidence Extraction Engine Architecture Specification v1.1 §10
exactly: a pure serialize/deserialize pair over JSON Lines, no database,
no network, no query engine.

**Why JSON Lines and not SQLite/DuckDB/PostgreSQL** (§10, recorded here so
the reasoning travels with the code): PostgreSQL is disproportionate --
this project has no server or networking infrastructure anywhere. DuckDB
would be a genuinely new third-party dependency (`pyproject.toml`
currently declares only `typer`, `pydantic`, `PyYAML`). SQLite adds no
dependency but is binary, so `git diff` on a stored Evidence file would
show nothing -- directly against this project's own established value of
every change being reviewable. JSON Lines costs nothing new (stdlib
`json`) and makes a `git diff` show *exactly* which facts changed between
two extraction runs or two pinned versions, which is precisely the future
cross-version comparison this whole design exists to serve.

**Pure storage only.** Nothing here extracts, collects, aggregates,
scores, filters, or reorders anything. `read_evidence_set` reconstructs
byte-for-byte what `write_evidence_set` was given -- including
`EvidenceSet.evidence`'s exact order, which the engine already sorted
(§9) and which this layer must never re-derive or "helpfully" re-sort.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence.contract import Evidence, EvidenceSet
from evidence.errors import EvidenceError_

#: Every `EvidenceSet` field except `evidence` itself. The evidence tuple
#: lives in its own `.jsonl` file, one record per line; everything else is
#: the header written to the companion `.meta.json`.
_META_FIELDS: tuple[str, ...] = (
    "evidence_set_id",
    "schema_version",
    "repository",
    "version",
    "commit",
    "extracted_at",
    "correlation_id",
    "errors",
    "truncated",
    "statistics",
)


def write_evidence_set(evidence_set: EvidenceSet, evidence_path: Path, meta_path: Path) -> None:
    """§10's serializer. Writes `evidence_set.evidence` to `evidence_path`
    as JSON Lines -- one `Evidence` JSON object per line, in exactly the
    order the tuple already holds -- and every other field to `meta_path`
    as a single JSON object.

    Both files are written with `sort_keys=True` so a given `EvidenceSet`
    always serializes to byte-identical output: JSON object key order is
    otherwise insertion-ordered, which would make two runs' files differ
    textually while being semantically identical -- exactly the kind of
    spurious `git diff` noise the JSON Lines choice exists to avoid.
    """

    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        json.dumps(record.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        for record in evidence_set.evidence
    ]
    # A trailing newline after the final record (and an empty file for an
    # empty EvidenceSet) -- the standard JSON Lines shape, and what
    # `read_evidence_set`'s own blank-line skipping below expects.
    evidence_path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    payload = evidence_set.model_dump(mode="json", include=set(_META_FIELDS))
    meta_path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_evidence_set(evidence_path: Path, meta_path: Path) -> EvidenceSet:
    """§10's deserializer -- the exact inverse of `write_evidence_set`.

    Line order in `evidence_path` is preserved as-is into
    `EvidenceSet.evidence`: this layer never re-sorts, since the ordering
    it is reading was already established deterministically by the engine
    (§9) and re-deriving it here would let a storage-layer bug silently
    "fix" (and therefore hide) an engine-layer one.

    A malformed file -- unreadable, invalid JSON, or JSON that does not
    satisfy the contract -- raises `EvidenceError_` rather than a raw
    `json`/`pydantic` error, so callers only ever catch this package's own
    exception type.
    """

    try:
        meta_content = meta_path.read_text(encoding="utf-8")
        evidence_content = evidence_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvidenceError_(str(exc)) from exc

    try:
        payload: dict[str, Any] = json.loads(meta_content)
    except json.JSONDecodeError as exc:
        raise EvidenceError_(f"malformed evidence metadata in '{meta_path}': {exc}") from exc

    records: list[Evidence] = []
    for line_number, line in enumerate(evidence_content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(Evidence.model_validate_json(line))
        except ValueError as exc:
            raise EvidenceError_(
                f"malformed evidence record at '{evidence_path}' line {line_number}: {exc}"
            ) from exc

    payload["evidence"] = records
    try:
        return EvidenceSet.model_validate(payload)
    except ValueError as exc:
        raise EvidenceError_(f"malformed evidence metadata in '{meta_path}': {exc}") from exc
