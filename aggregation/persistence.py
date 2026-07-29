"""Pattern Aggregation Engine's own persistence layer.

Implements Pattern Aggregation Engine Architecture Specification v1.0
§12 and §16: a pure serialize/deserialize pair over JSON Lines, mirroring
`evidence.persistence`'s technique field for field. No database, no
network, no query engine.

**Pure storage only.** Nothing here aggregates, resolves, counts, filters,
or reorders. `read_pattern_set` reconstructs exactly what
`write_pattern_set` was given -- including `PatternSet.patterns`' order,
which the engine already sorted (§11) and which this layer must never
re-derive. Re-sorting here would let a storage-layer bug silently repair
(and therefore hide) an engine-layer one.

**`skipped_aggregations` survives the round trip.** §9 makes it a
first-class result rather than a diagnostic, so losing it in
serialization would silently erase the platform's own declaration of what
it could not measure -- the single most important thing this artifact
carries into Sprint 22. A dedicated test asserts it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aggregation.contract import Pattern, PatternSet
from aggregation.errors import AggregationError_

#: Every `PatternSet` field except `patterns` itself. The pattern tuple
#: lives in its own `.jsonl` file, one record per line; everything else --
#: including `skipped_aggregations` and `observed_below_threshold` -- is
#: the header written to the companion `.meta.json`.
_META_FIELDS: tuple[str, ...] = (
    "pattern_set_id",
    "schema_version",
    "source_evidence_set_id",
    "repository",
    "version",
    "commit",
    "aggregated_at",
    "correlation_id",
    "skipped_aggregations",
    "observed_below_threshold",
    "statistics",
    # Sprint 22. Written because a population that can be derived from
    # more than one corpus is not reproducible without recording which
    # corpora produced it -- 510 and 492 are both defensible ERPNext
    # figures differing only by what was supplied.
    "resolution_provenance",
)


def write_pattern_set(pattern_set: PatternSet, patterns_path: Path, meta_path: Path) -> None:
    """§16's serializer. Writes `pattern_set.patterns` to `patterns_path`
    as JSON Lines -- one `Pattern` JSON object per line, in exactly the
    order the tuple already holds -- and every other field to `meta_path`
    as a single JSON object.

    Both files use `sort_keys=True` so a given `PatternSet` always
    serializes to byte-identical output: JSON object key order is
    otherwise insertion-ordered, which would make two runs' files differ
    textually while being semantically identical -- exactly the spurious
    `git diff` noise the JSON Lines choice exists to avoid.
    """

    patterns_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        json.dumps(pattern.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        for pattern in pattern_set.patterns
    ]
    # A trailing newline after the final record, and an empty file for an
    # empty PatternSet -- the standard JSON Lines shape, and what
    # `read_pattern_set`'s own blank-line skipping below expects.
    patterns_path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    payload = pattern_set.model_dump(mode="json", include=set(_META_FIELDS))
    meta_path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_pattern_set(patterns_path: Path, meta_path: Path) -> PatternSet:
    """§16's deserializer -- the exact inverse of `write_pattern_set`.

    Line order in `patterns_path` is preserved as-is into
    `PatternSet.patterns`: this layer never re-sorts, since the ordering
    it reads was already established deterministically by the engine
    (§11).

    A malformed file -- unreadable, invalid JSON, or JSON that does not
    satisfy the contract -- raises `AggregationError_` rather than a raw
    `json`/`pydantic` error, so callers only ever catch this package's own
    exception type.
    """

    try:
        meta_content = meta_path.read_text(encoding="utf-8")
        patterns_content = patterns_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AggregationError_(str(exc)) from exc

    try:
        payload: dict[str, Any] = json.loads(meta_content)
    except json.JSONDecodeError as exc:
        raise AggregationError_(f"malformed pattern metadata in '{meta_path}': {exc}") from exc

    patterns: list[Pattern] = []
    for line_number, line in enumerate(patterns_content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            patterns.append(Pattern.model_validate_json(line))
        except ValueError as exc:
            raise AggregationError_(
                f"malformed pattern record at '{patterns_path}' line {line_number}: {exc}"
            ) from exc

    payload["patterns"] = patterns
    try:
        return PatternSet.model_validate(payload)
    except ValueError as exc:
        raise AggregationError_(f"malformed pattern metadata in '{meta_path}': {exc}") from exc
