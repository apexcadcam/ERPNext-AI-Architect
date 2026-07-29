"""Tests for `aggregation.persistence` (Pattern Aggregation Engine Architecture
Specification v1.0 §12, §16).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.contract import CanonicalRepository, EvidenceCategory

from aggregation.contract import (
    AggregationStatistics,
    AggregationStatus,
    ObservedBelowThreshold,
    Pattern,
    PatternSet,
    SkippedAggregation,
)
from aggregation.errors import AggregationError_
from aggregation.persistence import read_pattern_set, write_pattern_set

_COMMIT = "1d14ba16398db3a220873509565c60f2932bed81"

# -- Fixture builders --------------------------------------------------------------------------------


def _pattern(
    *,
    subject: str = "frappe.validate_and_sanitize_search_inputs",
    occurrences: int = 59,
    population: int = 705,
    pattern_id: str = "a" * 64,
) -> Pattern:
    return Pattern(
        pattern_id=pattern_id,
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        subject=subject,
        occurrences=occurrences,
        population=population,
        support=occurrences / population,
        population_description="distinct symbols carrying a whitelist-family decorator",
        supporting_evidence_ids=("b" * 64,),
        repository=CanonicalRepository.ERPNEXT,
        version="v15.102.0",
        commit=_COMMIT,
    )


def _skipped() -> SkippedAggregation:
    return SkippedAggregation(
        evidence_category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        status=AggregationStatus.SKIPPED_NO_POPULATION,
        reason="population is not derivable from persisted Evidence alone (Sprint 22)",
        evidence_records_present=476,
    )


def _statistics(**overrides: object) -> AggregationStatistics:
    defaults: dict[str, object] = {
        "evidence_records_consumed": 1245,
        "categories_present": 2,
        "categories_aggregated": 1,
        "categories_skipped": 1,
        "patterns_produced": 1,
        "subjects_below_threshold": 0,
    }
    defaults.update(overrides)
    return AggregationStatistics(**defaults)  # type: ignore[arg-type]


def _pattern_set(**overrides: object) -> PatternSet:
    defaults: dict[str, object] = {
        "pattern_set_id": "pset-1",
        "schema_version": "1.0",
        "source_evidence_set_id": "evset-1",
        "repository": CanonicalRepository.ERPNEXT,
        "version": "v15.102.0",
        "commit": _COMMIT,
        "aggregated_at": "2026-07-27T13:00:00+00:00",
        "correlation_id": "corr-1",
        "patterns": (_pattern(),),
        "skipped_aggregations": (),
        "observed_below_threshold": (),
        "statistics": _statistics(),
    }
    defaults.update(overrides)
    return PatternSet(**defaults)  # type: ignore[arg-type]


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return (
        tmp_path / "erpnext-v15.102.0.patterns.jsonl",
        tmp_path / "erpnext-v15.102.0.meta.json",
    )


# -- Round trip -------------------------------------------------------------------------------------


def test_round_trip_preserves_the_pattern_set_exactly(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set()

    write_pattern_set(original, patterns_path, meta_path)

    assert read_pattern_set(patterns_path, meta_path) == original


def test_round_trip_preserves_every_metadata_field(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set(
        observed_below_threshold=(
            ObservedBelowThreshold(
                evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
                subject="staticmethod",
                occurrences=1,
            ),
        ),
        statistics=_statistics(subjects_below_threshold=1),
    )

    write_pattern_set(original, patterns_path, meta_path)
    restored = read_pattern_set(patterns_path, meta_path)

    assert restored.pattern_set_id == "pset-1"
    assert restored.schema_version == "1.0"
    assert restored.source_evidence_set_id == "evset-1"
    assert restored.repository is CanonicalRepository.ERPNEXT
    assert restored.version == "v15.102.0"
    assert restored.commit == _COMMIT
    assert restored.aggregated_at == original.aggregated_at
    assert restored.correlation_id == "corr-1"
    assert restored.observed_below_threshold == original.observed_below_threshold
    assert restored.statistics == original.statistics


def test_round_trip_preserves_support_precisely(tmp_path: Path) -> None:
    # The measured figure is the point of the artifact; a float that does
    # not survive serialization would silently corrupt it.
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set()

    write_pattern_set(original, patterns_path, meta_path)
    restored = read_pattern_set(patterns_path, meta_path)

    assert restored.patterns[0].support == original.patterns[0].support
    assert restored.patterns[0].support == pytest.approx(59 / 705)


def test_round_trip_preserves_supporting_evidence_ids(tmp_path: Path) -> None:
    # Traceability back to Evidence is what makes a Pattern auditable.
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set()

    write_pattern_set(original, patterns_path, meta_path)
    restored = read_pattern_set(patterns_path, meta_path)

    assert restored.patterns[0].supporting_evidence_ids == original.patterns[0].supporting_evidence_ids


# -- skipped_aggregations survives the round trip (§9) -----------------------------------------------


def test_skipped_aggregations_survive_the_round_trip(tmp_path: Path) -> None:
    # SS9 makes this a first-class result. Losing it in serialization would
    # silently erase the platform's own declaration of what it could not
    # measure -- the single most important thing this artifact carries
    # into Sprint 22.
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set(skipped_aggregations=(_skipped(),))

    write_pattern_set(original, patterns_path, meta_path)
    restored = read_pattern_set(patterns_path, meta_path)

    assert restored.skipped_aggregations == original.skipped_aggregations
    assert restored.skipped_aggregations[0].status is AggregationStatus.SKIPPED_NO_POPULATION
    assert restored.skipped_aggregations[0].evidence_records_present == 476
    assert "Sprint 22" in restored.skipped_aggregations[0].reason


def test_a_pattern_set_with_no_patterns_but_a_skip_survives_the_round_trip(tmp_path: Path) -> None:
    # SS7.7's "nothing was measurable, and here is precisely why" must
    # persist as faithfully as a populated result.
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set(
        patterns=(),
        skipped_aggregations=(_skipped(),),
        # `categories_present` moves with `categories_aggregated`: the
        # invariant added in Sprint 22 caught this fixture describing one
        # aggregated and one skipped category out of two present, while
        # aggregating none of them.
        statistics=_statistics(categories_present=1, categories_aggregated=0, patterns_produced=0),
    )

    write_pattern_set(original, patterns_path, meta_path)
    restored = read_pattern_set(patterns_path, meta_path)

    assert restored == original
    assert restored.patterns == ()
    assert len(restored.skipped_aggregations) == 1


# -- Ordering is replayed, never re-derived ----------------------------------------------------------


def test_round_trip_preserves_pattern_order_exactly(tmp_path: Path) -> None:
    # Deliberately stored in an order that is NOT the engine's own sort
    # order. Persistence must replay exactly what it was given: re-sorting
    # here would let a storage bug silently repair, and therefore hide, an
    # engine bug.
    patterns_path, meta_path = _paths(tmp_path)
    patterns = (
        _pattern(subject="zzz_last", occurrences=1, pattern_id="c" * 64),
        _pattern(subject="aaa_first", occurrences=99, pattern_id="b" * 64),
        _pattern(subject="mmm_middle", occurrences=50, pattern_id="d" * 64),
    )
    original = _pattern_set(patterns=patterns, statistics=_statistics(patterns_produced=3))

    write_pattern_set(original, patterns_path, meta_path)
    restored = read_pattern_set(patterns_path, meta_path)

    assert [p.pattern_id for p in restored.patterns] == [p.pattern_id for p in patterns]
    assert [p.subject for p in restored.patterns] == ["zzz_last", "aaa_first", "mmm_middle"]


# -- On-disk format ----------------------------------------------------------------------------------


def test_writes_one_json_object_per_line(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set(
        patterns=(
            _pattern(subject="a", pattern_id="a" * 64),
            _pattern(subject="b", pattern_id="b" * 64),
        ),
        statistics=_statistics(patterns_produced=2),
    )

    write_pattern_set(original, patterns_path, meta_path)

    lines = patterns_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        assert json.loads(line)["evidence_category"] == "whitelisted_api_decoration"


def test_the_meta_file_excludes_the_pattern_tuple(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)

    write_pattern_set(_pattern_set(skipped_aggregations=(_skipped(),)), patterns_path, meta_path)

    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "patterns" not in payload
    assert payload["schema_version"] == "1.0"
    assert payload["repository"] == "erpnext"
    assert len(payload["skipped_aggregations"]) == 1


def test_an_empty_pattern_set_writes_an_empty_patterns_file(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    original = _pattern_set(patterns=(), statistics=_statistics(patterns_produced=0))

    write_pattern_set(original, patterns_path, meta_path)

    assert patterns_path.read_text(encoding="utf-8") == ""
    assert read_pattern_set(patterns_path, meta_path) == original


def test_write_creates_missing_parent_directories(tmp_path: Path) -> None:
    patterns_path = tmp_path / "nested" / "deeper" / "erpnext.patterns.jsonl"
    meta_path = tmp_path / "nested" / "deeper" / "erpnext.meta.json"

    write_pattern_set(_pattern_set(), patterns_path, meta_path)

    assert patterns_path.is_file()
    assert meta_path.is_file()


def test_read_skips_blank_lines(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    write_pattern_set(_pattern_set(), patterns_path, meta_path)
    patterns_path.write_text(patterns_path.read_text(encoding="utf-8") + "\n   \n", encoding="utf-8")

    assert len(read_pattern_set(patterns_path, meta_path).patterns) == 1


# -- Byte-identical repeated writes ------------------------------------------------------------------


def test_serialization_is_byte_identical_across_repeated_writes(tmp_path: Path) -> None:
    # sort_keys=True: without it, JSON key order is insertion-ordered, so
    # two semantically identical runs would produce textually different
    # files -- exactly the spurious git diff noise JSONL was chosen to
    # avoid.
    first_patterns, first_meta = tmp_path / "first.jsonl", tmp_path / "first.json"
    second_patterns, second_meta = tmp_path / "second.jsonl", tmp_path / "second.json"
    pattern_set = _pattern_set(skipped_aggregations=(_skipped(),))

    write_pattern_set(pattern_set, first_patterns, first_meta)
    write_pattern_set(pattern_set, second_patterns, second_meta)

    assert first_patterns.read_bytes() == second_patterns.read_bytes()
    assert first_meta.read_bytes() == second_meta.read_bytes()


def test_rewriting_over_an_existing_file_is_byte_identical(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    pattern_set = _pattern_set()

    write_pattern_set(pattern_set, patterns_path, meta_path)
    first = (patterns_path.read_bytes(), meta_path.read_bytes())
    write_pattern_set(pattern_set, patterns_path, meta_path)

    assert (patterns_path.read_bytes(), meta_path.read_bytes()) == first


# -- Failure handling: AggregationError_ only --------------------------------------------------------


def test_read_raises_aggregation_error_for_a_missing_file(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)

    with pytest.raises(AggregationError_):
        read_pattern_set(patterns_path, meta_path)


def test_read_raises_aggregation_error_for_malformed_meta_json(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    write_pattern_set(_pattern_set(), patterns_path, meta_path)
    meta_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(AggregationError_, match="malformed pattern metadata"):
        read_pattern_set(patterns_path, meta_path)


def test_read_raises_aggregation_error_for_a_malformed_pattern_line(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    write_pattern_set(_pattern_set(), patterns_path, meta_path)
    patterns_path.write_text('{"pattern_id": "incomplete"}\n', encoding="utf-8")

    with pytest.raises(AggregationError_, match="malformed pattern record"):
        read_pattern_set(patterns_path, meta_path)


def test_the_malformed_line_error_names_the_offending_line_number(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    write_pattern_set(_pattern_set(), patterns_path, meta_path)
    good_line = patterns_path.read_text(encoding="utf-8").splitlines()[0]
    patterns_path.write_text(f"{good_line}\n{{broken\n", encoding="utf-8")

    with pytest.raises(AggregationError_, match="line 2"):
        read_pattern_set(patterns_path, meta_path)


def test_read_raises_aggregation_error_when_meta_json_violates_the_contract(tmp_path: Path) -> None:
    patterns_path, meta_path = _paths(tmp_path)
    write_pattern_set(_pattern_set(), patterns_path, meta_path)
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    del payload["statistics"]
    meta_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AggregationError_, match="malformed pattern metadata"):
        read_pattern_set(patterns_path, meta_path)


def test_read_raises_aggregation_error_for_a_pattern_violating_its_own_constraints(
    tmp_path: Path,
) -> None:
    # A persisted Pattern with population 0 must not be reconstructable:
    # SS5's "no population, no Pattern" holds on the way in as well as out.
    patterns_path, meta_path = _paths(tmp_path)
    write_pattern_set(_pattern_set(), patterns_path, meta_path)
    payload = json.loads(patterns_path.read_text(encoding="utf-8").splitlines()[0])
    payload["population"] = 0
    patterns_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(AggregationError_, match="malformed pattern record"):
        read_pattern_set(patterns_path, meta_path)
