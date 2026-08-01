"""Tests for `architect patterns report` (Evidence Platform CLI
Architecture Specification v1.1 §3.3, §6, §7).

Real command, real artifacts on disk. The fixtures below build a genuine
`PatternSet` by invoking the real `evidence extract` and
`patterns aggregate` commands, so what `report` renders is what the
engines actually produced -- not a hand-written stand-in that could drift
from the contract.

The load-bearing assertions here are the ones that prove `report` stays a
renderer: it writes nothing, it computes nothing, and every value it
prints can be found verbatim in the persisted artifact.
"""

from __future__ import annotations

import json as json_module
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from runtime.cli import app
from runtime.output import SECTION_ORDER

runner = CliRunner()

_CUSTOMER_PY = """
class Customer:
    def validate(self):
        pass

    def on_submit(self):
        pass
"""

_API_PY = """
import frappe


@frappe.whitelist()
def get_data():
    return {}


@frappe.whitelist()
def get_more():
    return {}


@frappe.whitelist()
@frappe.read_only()
def get_report():
    return {}
"""

_COMMIT = "61ab7e2b2409b293ffd3c8f72d730fa89b201332"
_VERSION = "v15.102.0"

#: The repository these fixtures measure.
#:
#: **`frappe`, because its registered supporting-corpus closure is
#: empty** (ADR-0017). `patterns report` is read-only and repository-
#: agnostic; every test here is about how an artifact is rendered. The
#: fixture has to *produce* an artifact first, though, and producing
#: one for `erpnext` now requires supplying `frappe` context -- an
#: irrelevant complication for a rendering test.
_NEUTRAL_REPOSITORY = "frappe"


@pytest.fixture
def pattern_dir(tmp_path: Path) -> Path:
    """A real Pattern artifact, produced by the real extract + aggregate
    commands -- the exact input `report` is meant to read.
    """

    source_root = tmp_path / "src"
    (source_root / "erpnext" / "doctype" / "customer").mkdir(parents=True)
    (source_root / "erpnext" / "doctype" / "customer" / "customer.py").write_text(_CUSTOMER_PY)
    (source_root / "erpnext" / "api.py").write_text(_API_PY)

    evidence_dir = tmp_path / "evidence-out"
    extracted = runner.invoke(
        app,
        [
            "evidence",
            "extract",
            _NEUTRAL_REPOSITORY,
            "--version",
            _VERSION,
            "--commit",
            _COMMIT,
            "--source-root",
            str(source_root),
            "--output-dir",
            str(evidence_dir),
        ],
    )
    assert extracted.exit_code == 0

    patterns_out = tmp_path / "pattern-out"
    aggregated = runner.invoke(
        app,
        [
            "patterns",
            "aggregate",
            _NEUTRAL_REPOSITORY,
            "--version",
            _VERSION,
            "--evidence-dir",
            str(evidence_dir),
            "--output-dir",
            str(patterns_out),
            "--min-occurrences",
            "2",
        ],
    )
    assert aggregated.exit_code == 0
    return patterns_out


def _args(pattern_dir: Path, *extra: str) -> list[str]:
    return [
        "patterns",
        "report",
        _NEUTRAL_REPOSITORY,
        "--version",
        _VERSION,
        "--pattern-dir",
        str(pattern_dir),
        *extra,
    ]


def _persisted(pattern_dir: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    """The artifact as it sits on disk, parsed independently of the CLI."""

    meta = json_module.loads(
        (pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.meta.json").read_text(encoding="utf-8")
    )
    lines = (
        (pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.patterns.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    patterns = [json_module.loads(line) for line in lines if line.strip()]
    assert isinstance(meta, dict)
    return meta, patterns


def _summary(pattern_dir: Path, *extra: str) -> dict[str, str]:
    result = runner.invoke(app, _args(pattern_dir, "--json", *extra))
    assert result.exit_code == 0
    payload = json_module.loads(result.stdout)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    return summary


# -- The happy path ------------------------------------------------------------------------------------


def test_report_succeeds_against_a_real_artifact(pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(pattern_dir))
    assert result.exit_code == 0


def test_provenance_rows_are_the_persisted_values_verbatim(pattern_dir: Path) -> None:
    meta, _ = _persisted(pattern_dir)
    summary = _summary(pattern_dir)

    assert summary["repository"] == meta["repository"]
    assert summary["version"] == meta["version"]
    assert summary["commit"] == meta["commit"]
    assert summary["aggregated at"] == meta["aggregated_at"]


def test_every_persisted_pattern_appears_with_its_own_counts(pattern_dir: Path) -> None:
    _, patterns = _persisted(pattern_dir)
    summary = _summary(pattern_dir)
    assert patterns  # the fixture must actually produce Patterns

    for pattern in patterns:
        label = f"pattern: {pattern['evidence_category']} / {pattern['subject']}"
        assert label in summary
        assert f"{pattern['occurrences']}/{pattern['population']}" in summary[label]


def test_patterns_are_rendered_in_the_order_they_were_persisted(pattern_dir: Path) -> None:
    # §3.3: "sorted as persisted". The engine owns the ordering; the CLI
    # must not re-sort, which would silently substitute its own ranking.
    _, patterns = _persisted(pattern_dir)
    summary = _summary(pattern_dir)

    rendered = [label for label in summary if label.startswith("pattern: ")]
    expected = [f"pattern: {p['evidence_category']} / {p['subject']}" for p in patterns]
    assert rendered == expected


def test_every_below_threshold_subject_is_reported_with_its_count(pattern_dir: Path) -> None:
    meta, _ = _persisted(pattern_dir)
    summary = _summary(pattern_dir)
    observed = meta["observed_below_threshold"]
    assert isinstance(observed, list)
    assert observed  # the fixture's `frappe.read_only` sits below the threshold

    for entry in observed:
        label = f"below threshold: {entry['evidence_category']} / {entry['subject']}"
        assert summary[label] == str(entry["occurrences"])


def test_the_population_description_is_stated_once_per_category(pattern_dir: Path) -> None:
    _, patterns = _persisted(pattern_dir)
    summary = _summary(pattern_dir)

    categories = {str(pattern["evidence_category"]) for pattern in patterns}
    population_rows = [label for label in summary if label.startswith("population: ")]
    assert len(population_rows) == len(categories)
    for pattern in patterns:
        assert summary[f"population: {pattern['evidence_category']}"] == pattern["population_description"]


def test_summary_row_order_is_provenance_then_population_then_patterns_then_below_threshold(
    pattern_dir: Path,
) -> None:
    labels = list(_summary(pattern_dir))
    assert labels[:4] == ["repository", "version", "commit", "aggregated at"]

    groups = [
        next(index for index, label in enumerate(labels) if label.startswith(prefix))
        for prefix in ("population: ", "pattern: ", "below threshold: ")
    ]
    assert groups == sorted(groups)


# -- It computes nothing -------------------------------------------------------------------------------


def test_support_is_read_from_the_artifact_not_recomputed(pattern_dir: Path) -> None:
    # The decisive test. A support value is rewritten on disk so that it
    # *disagrees* with occurrences/population. If the CLI ever divided the
    # two itself, it would print the recomputed figure and this fails.
    patterns_path = pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.patterns.jsonl"
    lines = patterns_path.read_text(encoding="utf-8").splitlines()
    first = json_module.loads(lines[0])
    assert first["occurrences"] / first["population"] != pytest.approx(0.1234)
    first["support"] = 0.1234
    patterns_path.write_text(
        "\n".join([json_module.dumps(first, sort_keys=True), *lines[1:]]) + "\n", encoding="utf-8"
    )

    summary = _summary(pattern_dir)
    label = f"pattern: {first['evidence_category']} / {first['subject']}"
    assert "support 0.1234" in summary[label]


def test_the_reported_counts_are_never_derived_from_the_evidence_set(pattern_dir: Path) -> None:
    # Occurrences and population are rewritten on disk; the report must
    # follow the artifact, because it is a renderer of a stored result and
    # not a second opinion about it.
    patterns_path = pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.patterns.jsonl"
    lines = patterns_path.read_text(encoding="utf-8").splitlines()
    first = json_module.loads(lines[0])
    first["occurrences"] = 7
    first["population"] = 9
    patterns_path.write_text(
        "\n".join([json_module.dumps(first, sort_keys=True), *lines[1:]]) + "\n", encoding="utf-8"
    )

    summary = _summary(pattern_dir)
    assert "7/9" in summary[f"pattern: {first['evidence_category']} / {first['subject']}"]


def test_no_total_or_ranking_row_is_invented(pattern_dir: Path) -> None:
    # §3.3 names four groups. A "total", "top pattern", or "average" row
    # would be the CLI producing a statistic the engine never computed.
    summary = _summary(pattern_dir)
    for label in summary:
        assert label.startswith(("pattern: ", "population: ", "below threshold: ")) or label in {
            "repository",
            "version",
            "commit",
            "aggregated at",
        }


# -- It writes nothing ---------------------------------------------------------------------------------


def test_report_writes_no_file_and_modifies_none(pattern_dir: Path) -> None:
    before = {path: path.read_bytes() for path in sorted(pattern_dir.rglob("*")) if path.is_file()}
    assert before

    result = runner.invoke(app, _args(pattern_dir))
    assert result.exit_code == 0

    after = {path: path.read_bytes() for path in sorted(pattern_dir.rglob("*")) if path.is_file()}
    assert after == before


def test_the_artifacts_written_section_is_empty(pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(pattern_dir, "--json"))
    assert json_module.loads(result.stdout)["artifacts_written"] == []


def test_report_needs_neither_the_evidence_artifact_nor_the_source_tree(
    pattern_dir: Path, tmp_path: Path
) -> None:
    # Deleting both proves the command reads the Pattern artifact alone and
    # re-runs no stage of the platform.
    shutil.rmtree(tmp_path / "evidence-out")
    shutil.rmtree(tmp_path / "src")

    result = runner.invoke(app, _args(pattern_dir))
    assert result.exit_code == 0


# -- Skipped aggregations ------------------------------------------------------------------------------


def test_every_skipped_aggregation_is_reported(pattern_dir: Path) -> None:
    meta, _ = _persisted(pattern_dir)
    skipped_meta = meta["skipped_aggregations"]
    assert isinstance(skipped_meta, list)
    assert skipped_meta  # controller_lifecycle_hook is always present in v1.0

    result = runner.invoke(app, _args(pattern_dir, "--json"))
    assert len(json_module.loads(result.stdout)["skipped"]) == len(skipped_meta)


def test_the_skip_reason_is_printed_in_full_and_unedited(pattern_dir: Path) -> None:
    meta, _ = _persisted(pattern_dir)
    skipped_meta = meta["skipped_aggregations"]
    assert isinstance(skipped_meta, list)

    result = runner.invoke(app, _args(pattern_dir, "--json"))
    rendered = json_module.loads(result.stdout)["skipped"]
    for entry, line in zip(skipped_meta, rendered, strict=True):
        assert str(entry["reason"]) in line
        assert str(entry["evidence_category"]) in line
        assert str(entry["status"]) in line
        assert str(entry["evidence_records_present"]) in line


def test_aggregate_and_report_describe_the_same_skip_identically(pattern_dir: Path, tmp_path: Path) -> None:
    # Two commands, one shared template. If either ever grows its own
    # wording, the platform would describe the same declared gap two
    # different ways depending on which command a reader ran.
    reported = runner.invoke(app, _args(pattern_dir, "--json"))
    aggregated = runner.invoke(
        app,
        [
            "patterns",
            "aggregate",
            _NEUTRAL_REPOSITORY,
            "--version",
            _VERSION,
            "--evidence-dir",
            str(tmp_path / "evidence-out"),
            "--output-dir",
            str(tmp_path / "pattern-recheck"),
            "--min-occurrences",
            "2",
            "--json",
        ],
    )
    assert aggregated.exit_code == 0
    assert json_module.loads(reported.stdout)["skipped"] == json_module.loads(aggregated.stdout)["skipped"]


def test_a_skip_does_not_make_the_command_fail(pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(pattern_dir, "--json"))
    payload = json_module.loads(result.stdout)
    assert payload["skipped"] != []
    assert payload["errors"] == []
    assert result.exit_code == 0


# -- Output Contract conformance -----------------------------------------------------------------------


def test_human_output_emits_all_six_sections_in_order(pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(pattern_dir))
    headings = [section.upper().replace("_", " ") for section in SECTION_ORDER]
    positions = [result.stdout.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert result.stdout.rstrip().endswith("exit: 0")


def test_json_output_emits_all_six_keys_plus_exit_code(pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(pattern_dir, "--json"))
    assert list(json_module.loads(result.stdout)) == [*SECTION_ORDER, "exit_code"]


def test_both_modes_report_identical_values(pattern_dir: Path) -> None:
    human = runner.invoke(app, _args(pattern_dir))
    summary = _summary(pattern_dir)
    for label, value in summary.items():
        assert label in human.stdout
        assert value in human.stdout


# -- Failure handling ----------------------------------------------------------------------------------


def test_a_missing_pattern_artifact_fails_with_a_next_step(tmp_path: Path) -> None:
    result = runner.invoke(app, _args(tmp_path / "nothing-here"))
    assert result.exit_code == 1
    assert "architect patterns aggregate" in result.stdout


def test_unknown_repository_fails_with_a_readable_message(pattern_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["patterns", "report", "hrms", "--version", _VERSION, "--pattern-dir", str(pattern_dir)],
    )
    assert result.exit_code == 1
    assert "Unknown repository 'hrms'" in result.stdout
    assert "frappe" in result.stdout
    assert "erpnext" in result.stdout


def test_a_failing_run_still_emits_all_six_sections(tmp_path: Path) -> None:
    result = runner.invoke(app, _args(tmp_path / "nothing-here"))
    for section in SECTION_ORDER:
        assert section.upper().replace("_", " ") in result.stdout
    assert result.stdout.rstrip().endswith("exit: 1")


def test_a_failing_run_in_json_mode_is_still_parseable(tmp_path: Path) -> None:
    result = runner.invoke(app, _args(tmp_path / "nothing-here", "--json"))
    payload = json_module.loads(result.stdout)
    assert list(payload) == [*SECTION_ORDER, "exit_code"]
    assert payload["exit_code"] == 1
    assert payload["errors"]
    assert payload["summary"] == {}


def test_a_corrupt_pattern_artifact_fails_with_the_engines_own_message(pattern_dir: Path) -> None:
    (pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.patterns.jsonl").write_text(
        "{not json", encoding="utf-8"
    )
    result = runner.invoke(app, _args(pattern_dir))
    assert result.exit_code == 1
    assert "Traceback" not in result.stdout


def test_an_artifact_violating_the_contract_fails_without_a_traceback(pattern_dir: Path) -> None:
    # `support` outside 0.0-1.0 is rejected by `Pattern`'s own field
    # constraint; §7 requires that reach the user as one readable line.
    patterns_path = pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.patterns.jsonl"
    lines = patterns_path.read_text(encoding="utf-8").splitlines()
    first = json_module.loads(lines[0])
    first["support"] = 42.0
    patterns_path.write_text(
        "\n".join([json_module.dumps(first, sort_keys=True), *lines[1:]]) + "\n", encoding="utf-8"
    )

    result = runner.invoke(app, _args(pattern_dir))
    assert result.exit_code == 1
    assert "Traceback" not in result.stdout


def test_version_is_required(pattern_dir: Path) -> None:
    result = runner.invoke(
        app, ["patterns", "report", _NEUTRAL_REPOSITORY, "--pattern-dir", str(pattern_dir)]
    )
    assert result.exit_code != 0


def test_report_appears_in_the_patterns_help() -> None:
    result = runner.invoke(app, ["patterns", "--help"])
    assert result.exit_code == 0
    assert "report" in result.stdout
