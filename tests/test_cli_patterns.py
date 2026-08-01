"""Tests for `architect patterns aggregate` (Evidence Platform CLI
Architecture Specification v1.1 §3.2, §6, §7).

Real command, real engines, real artifacts on disk -- the command is a
thin adapter, so mocking the layer beneath it would leave nothing under
test.
"""

from __future__ import annotations

import json as json_module
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

#: The repository the single-corpus fixtures measure.
#:
#: **`frappe`, because its registered supporting-corpus closure is
#: empty** (ADR-0017). These tests exercise the aggregate command --
#: its output sections, its skip rendering, its failure paths -- and
#: never ERPNext semantics. `erpnext` now requires `frappe` context and
#: would refuse, so measuring it here would test admission by accident
#: in thirty places instead of deliberately in one.
#:
#: The cross-repository tests below keep `erpnext`, supplied with
#: `frappe` -- the real canonical pairing, which admission accepts.
_NEUTRAL_REPOSITORY = "frappe"


@pytest.fixture
def evidence_dir(tmp_path: Path) -> Path:
    """A real Evidence artifact, produced by the real extract command."""

    source_root = tmp_path / "src"
    (source_root / "erpnext" / "doctype" / "customer").mkdir(parents=True)
    (source_root / "erpnext" / "doctype" / "customer" / "customer.py").write_text(_CUSTOMER_PY)
    (source_root / "erpnext" / "api.py").write_text(_API_PY)

    out = tmp_path / "evidence-out"
    result = runner.invoke(
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
            str(out),
        ],
    )
    assert result.exit_code == 0
    return out


@pytest.fixture
def pattern_dir(tmp_path: Path) -> Path:
    return tmp_path / "pattern-out"


def _args(
    evidence_dir: Path,
    pattern_dir: Path,
    *extra: str,
    repository: str = _NEUTRAL_REPOSITORY,
    version: str = _VERSION,
) -> list[str]:
    return [
        "patterns",
        "aggregate",
        repository,
        "--version",
        version,
        "--evidence-dir",
        str(evidence_dir),
        "--output-dir",
        str(pattern_dir),
        *extra,
    ]


# -- The happy path ------------------------------------------------------------------------------------


def test_aggregate_succeeds_and_writes_both_artifacts(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir))

    assert result.exit_code == 0
    assert (pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.patterns.jsonl").exists()
    assert (pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.meta.json").exists()


def test_summary_rows_are_engine_statistics_verbatim(evidence_dir: Path, pattern_dir: Path) -> None:
    # Every value below is read back off the persisted PatternSet, so this
    # asserts the CLI reported the engine's numbers rather than its own.
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--json"))
    summary = json_module.loads(result.stdout)["summary"]

    meta = json_module.loads((pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.meta.json").read_text())
    statistics = meta["statistics"]

    assert summary["evidence records consumed"] == str(statistics["evidence_records_consumed"])
    assert summary["categories present"] == str(statistics["categories_present"])
    assert summary["categories aggregated"] == str(statistics["categories_aggregated"])
    assert summary["categories skipped"] == str(statistics["categories_skipped"])
    assert summary["patterns produced"] == str(statistics["patterns_produced"])
    assert summary["subjects below threshold"] == str(statistics["subjects_below_threshold"])


def test_reported_artifact_paths_are_the_files_actually_written(
    evidence_dir: Path, pattern_dir: Path
) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--json"))
    written = json_module.loads(result.stdout)["artifacts_written"]

    assert len(written) == 2
    for path in written:
        assert Path(path).exists()


# -- SkippedAggregation reaches the terminal intact -----------------------------------------------------


def test_every_skipped_aggregation_is_reported(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--json"))
    skipped = json_module.loads(result.stdout)["skipped"]

    # The CLI's invariant is that it reports every skip the artifact
    # holds -- not that the artifact holds a particular number of them.
    # Asserting a literal count here made this a test of the corpus
    # rather than of the command, and it broke the moment Sprint 22 added
    # structural Evidence that also has no population basis.
    meta = json_module.loads((pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.meta.json").read_text())
    assert len(skipped) == len(meta["skipped_aggregations"])
    assert skipped, "the lifecycle-hook gap must always be among them"


def test_the_skip_reason_is_printed_in_full_and_unedited(evidence_dir: Path, pattern_dir: Path) -> None:
    # The declared denominator gap is the platform's own account of what it
    # cannot yet measure. Truncating or paraphrasing it for terminal
    # tidiness would turn a disclosed limitation back into a footnote.
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--json"))
    skipped = json_module.loads(result.stdout)["skipped"]

    meta = json_module.loads((pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.meta.json").read_text())
    reason = meta["skipped_aggregations"][0]["reason"]

    assert reason in skipped[0]
    assert "..." not in skipped[0]


def test_the_skip_line_carries_category_status_and_record_count(
    evidence_dir: Path, pattern_dir: Path
) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir))

    assert "controller_lifecycle_hook" in result.stdout
    assert "skipped_no_population" in result.stdout
    # The difference between "no records" and "no denominator" is the whole
    # point of `evidence_records_present`.
    assert "2 Evidence record(s) present" in result.stdout


def test_a_skip_does_not_make_the_command_fail(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--json"))
    payload = json_module.loads(result.stdout)

    assert payload["exit_code"] == 0
    assert payload["errors"] == []
    assert payload["skipped"] != []


# -- The threshold comes from the registry, not from the CLI ---------------------------------------------


def test_the_default_threshold_is_the_registered_one(evidence_dir: Path, pattern_dir: Path) -> None:
    from aggregation.engine import MIN_OCCURRENCES_THRESHOLD
    from composition_root.evidence_platform import DEFAULT_MIN_OCCURRENCES

    assert DEFAULT_MIN_OCCURRENCES == MIN_OCCURRENCES_THRESHOLD.value

    default_run = runner.invoke(app, _args(evidence_dir, pattern_dir, "--json"))
    explicit_run = runner.invoke(
        app, _args(evidence_dir, pattern_dir, "--min-occurrences", str(DEFAULT_MIN_OCCURRENCES), "--json")
    )
    assert (
        json_module.loads(default_run.stdout)["summary"] == json_module.loads(explicit_run.stdout)["summary"]
    )


def test_min_occurrences_is_honoured(evidence_dir: Path, pattern_dir: Path) -> None:
    # `frappe.read_only` occurs once in the fixture: promoted at 1, below
    # threshold at 2.
    at_one = json_module.loads(
        runner.invoke(app, _args(evidence_dir, pattern_dir, "--min-occurrences", "1", "--json")).stdout
    )["summary"]
    at_two = json_module.loads(
        runner.invoke(app, _args(evidence_dir, pattern_dir, "--min-occurrences", "2", "--json")).stdout
    )["summary"]

    assert int(at_one["patterns produced"]) > int(at_two["patterns produced"])
    assert int(at_one["subjects below threshold"]) < int(at_two["subjects below threshold"])


# -- Output Contract conformance (§6) ---------------------------------------------------------------------


def test_human_output_emits_all_six_sections_in_order(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir))
    positions = [result.stdout.index(section.upper().replace("_", " ")) for section in SECTION_ORDER]

    assert positions == sorted(positions)
    assert result.stdout.strip().endswith("exit: 0")


def test_json_output_emits_all_six_keys_plus_exit_code(evidence_dir: Path, pattern_dir: Path) -> None:
    payload = json_module.loads(runner.invoke(app, _args(evidence_dir, pattern_dir, "--json")).stdout)

    assert list(payload) == [*SECTION_ORDER, "exit_code"]
    assert payload["warnings"] == []


def test_both_modes_report_identical_numbers(evidence_dir: Path, pattern_dir: Path) -> None:
    human = runner.invoke(app, _args(evidence_dir, pattern_dir)).stdout
    payload = json_module.loads(runner.invoke(app, _args(evidence_dir, pattern_dir, "--json")).stdout)

    for label, value in payload["summary"].items():
        assert label in human
        assert value in human


# -- Failure paths (§7) ------------------------------------------------------------------------------------


def test_a_missing_evidence_artifact_fails_with_a_next_step(tmp_path: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(tmp_path / "empty", pattern_dir))

    assert result.exit_code == 1
    assert "No Evidence artifact at" in result.stdout
    assert "architect evidence extract" in result.stdout
    assert "Traceback" not in result.stdout


def test_unknown_repository_fails_with_a_readable_message(evidence_dir: Path, pattern_dir: Path) -> None:
    args = _args(evidence_dir, pattern_dir)
    args[2] = "apex_dashboard"
    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "Unknown repository 'apex_dashboard'" in result.stdout
    assert "Traceback" not in result.stdout


def test_a_failing_run_still_emits_all_six_sections(tmp_path: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(tmp_path / "empty", pattern_dir))

    for section in SECTION_ORDER:
        assert section.upper().replace("_", " ") in result.stdout
    assert result.stdout.strip().endswith("exit: 1")


def test_a_failing_run_in_json_mode_is_still_parseable(tmp_path: Path, pattern_dir: Path) -> None:
    payload = json_module.loads(runner.invoke(app, _args(tmp_path / "empty", pattern_dir, "--json")).stdout)

    assert list(payload) == [*SECTION_ORDER, "exit_code"]
    assert payload["exit_code"] == 1
    assert payload["skipped"] == []
    assert len(payload["errors"]) == 1


def test_nothing_is_written_when_the_run_fails(tmp_path: Path, pattern_dir: Path) -> None:
    runner.invoke(app, _args(tmp_path / "empty", pattern_dir))
    assert not (pattern_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.patterns.jsonl").exists()


def test_a_corrupt_evidence_artifact_fails_with_the_engines_own_message(
    evidence_dir: Path, pattern_dir: Path
) -> None:
    # `read_evidence_set` wraps every malformed-input case in
    # `EvidenceError_`; the CLI maps that to exit 1 and prints the message.
    (evidence_dir / f"{_NEUTRAL_REPOSITORY}-{_VERSION}.evidence.jsonl").write_text("{not json at all\n")
    result = runner.invoke(app, _args(evidence_dir, pattern_dir))

    assert result.exit_code == 1
    assert "malformed evidence record" in result.stdout
    assert "Traceback" not in result.stdout


def test_a_zero_min_occurrences_fails_cleanly(evidence_dir: Path, pattern_dir: Path) -> None:
    # `AggregationRequest.min_occurrences` is `ge=1`: a floor of zero would
    # promote every one-off observation to a Pattern. Rejected by the
    # contract, reported by the CLI, never a traceback.
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--min-occurrences", "0"))

    assert result.exit_code == 1
    assert "Invalid input: min_occurrences" in result.stdout
    assert "Traceback" not in result.stdout


def test_version_is_required(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(
        app, ["patterns", "aggregate", _NEUTRAL_REPOSITORY, "--evidence-dir", str(evidence_dir)]
    )
    assert result.exit_code != 0


# -- Aggregation never re-runs extraction ------------------------------------------------------------------


def test_aggregate_works_after_the_source_tree_is_gone(
    evidence_dir: Path, pattern_dir: Path, tmp_path: Path
) -> None:
    import shutil

    shutil.rmtree(tmp_path / "src")
    result = runner.invoke(app, _args(evidence_dir, pattern_dir))

    assert result.exit_code == 0


# -- --supporting: multi-corpus resolution (Sprint 22, Commit 6) ----------------------------------------


def _extract_into(out: Path, repository: str, version: str, source_root: Path) -> None:
    result = runner.invoke(
        app,
        [
            "evidence",
            "extract",
            repository,
            "--version",
            version,
            "--commit",
            _COMMIT,
            "--source-root",
            str(source_root),
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0


@pytest.fixture
def frappe_evidence_dir(tmp_path: Path) -> Path:
    """Two real Evidence artifacts in one directory.

    The erpnext corpus holds a controller whose chain **leaves the
    repository**: `Account(Mixin)`, where `Mixin(Document)` is defined only
    in frappe. Resolved alone it yields a population of 1 (`Direct`);
    resolved with frappe supplied it yields 2. That difference is the
    feature, so the fixture is built to exhibit it.
    """

    out = tmp_path / "multi-evidence"

    erpnext_src = tmp_path / "erpnext-multi"
    (erpnext_src / "erpnext" / "accounts").mkdir(parents=True)
    # `Account` carries no hook deliberately. With only `Direct` bearing
    # one, the numerator stays inside the population whether or not frappe
    # is supplied -- otherwise this fixture would trip the numerator-scope
    # defect recorded in the Commit 6 report rather than test the flag.
    (erpnext_src / "erpnext" / "accounts" / "account.py").write_text(
        "class Direct(Document):\n"
        "    def validate(self):\n"
        "        pass\n\n\n"
        "class Account(Mixin):\n"
        "    pass\n"
    )
    _extract_into(out, "erpnext", _VERSION, erpnext_src)

    frappe_src = tmp_path / "frappe-src"
    (frappe_src / "frappe" / "utils").mkdir(parents=True)
    # `Mixin` carries a hook so this corpus can also be *measured*, not only
    # supplied: a single-corpus provenance is only observable from a run
    # whose lifecycle category actually resolves a population.
    (frappe_src / "frappe" / "utils" / "nestedset.py").write_text(
        "class Mixin(Document):\n    def validate(self):\n        pass\n"
    )
    _extract_into(out, "frappe", "v15.103.1", frappe_src)

    return out


def test_supporting_is_optional_and_absent_by_default(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--json"))
    assert result.exit_code == 0


def test_aggregating_erpnext_without_frappe_is_refused(frappe_evidence_dir: Path, pattern_dir: Path) -> None:
    """The user-visible behaviour change (ADR-0017).

    This invocation used to succeed and publish a population resolved
    without frappe context -- 492 against the real corpus, where the true
    figure is 510. It is now refused, and the message names what to add.
    """

    result = runner.invoke(app, _args(frappe_evidence_dir, pattern_dir, repository="erpnext"))

    assert result.exit_code == 1
    assert "frappe" in result.stdout
    assert "Traceback" not in result.stdout
    assert not (pattern_dir / f"erpnext-{_VERSION}.patterns.jsonl").exists()


def test_a_refused_aggregation_still_emits_all_six_sections(
    frappe_evidence_dir: Path, pattern_dir: Path
) -> None:
    result = runner.invoke(app, _args(frappe_evidence_dir, pattern_dir, repository="erpnext"))
    for section in SECTION_ORDER:
        assert section.upper().replace("_", " ") in result.stdout
    assert result.stdout.rstrip().endswith("exit: 1")


def test_supporting_appears_in_the_command_help() -> None:
    result = runner.invoke(app, ["patterns", "aggregate", "--help"])
    assert result.exit_code == 0
    assert "--supporting" in result.stdout


def test_a_supporting_corpus_is_recorded_in_the_provenance(
    frappe_evidence_dir: Path, pattern_dir: Path
) -> None:
    result = runner.invoke(
        app,
        _args(
            frappe_evidence_dir,
            pattern_dir,
            "--supporting",
            "frappe:v15.103.1",
            "--json",
            repository="erpnext",
        ),
    )
    assert result.exit_code == 0

    meta = json_module.loads((pattern_dir / f"erpnext-{_VERSION}.meta.json").read_text())
    provenance = meta["resolution_provenance"]
    assert provenance["strategy"] == "multi_corpus"
    assert [ref["repository"] for ref in provenance["supporting_corpora"]] == ["frappe"]
    assert provenance["supporting_corpora"][0]["version"] == "v15.103.1"


def test_without_supporting_the_strategy_is_single_corpus(
    frappe_evidence_dir: Path, pattern_dir: Path
) -> None:
    # Measured against `frappe`, whose registered closure is empty. A
    # single-corpus run is only a *publishable* result for such a
    # repository: the same invocation against `erpnext` is now refused
    # rather than recorded as single-corpus, which the admission tests
    # assert directly.
    result = runner.invoke(app, _args(frappe_evidence_dir, pattern_dir, "--json", version="v15.103.1"))
    assert result.exit_code == 0

    meta = json_module.loads((pattern_dir / f"{_NEUTRAL_REPOSITORY}-v15.103.1.meta.json").read_text())
    provenance = meta["resolution_provenance"]
    assert provenance["strategy"] == "single_corpus"
    assert provenance["supporting_corpora"] == []


def test_a_supporting_corpus_contributes_no_pattern_of_its_own(
    frappe_evidence_dir: Path, pattern_dir: Path
) -> None:
    # §5.2. frappe explains why an erpnext class is a controller; it does
    # not thereby become one, and it owns nothing in this artifact.
    result = runner.invoke(
        app,
        _args(
            frappe_evidence_dir,
            pattern_dir,
            "--supporting",
            "frappe:v15.103.1",
            "--json",
            repository="erpnext",
        ),
    )
    assert result.exit_code == 0

    lines = (pattern_dir / f"erpnext-{_VERSION}.patterns.jsonl").read_text().splitlines()
    for line in lines:
        if line.strip():
            assert json_module.loads(line)["repository"] == "erpnext"


def test_a_malformed_supporting_value_fails_with_a_readable_message(
    evidence_dir: Path, pattern_dir: Path
) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--supporting", "frappe"))
    assert result.exit_code == 1
    assert "<repository>:<version>" in result.stdout


def test_supporting_may_not_name_the_measured_repository(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(
        app, _args(evidence_dir, pattern_dir, "--supporting", f"{_NEUTRAL_REPOSITORY}:{_VERSION}")
    )
    assert result.exit_code == 1
    assert "its own resolution context" in result.stdout


def test_a_missing_supporting_artifact_fails_with_a_next_step(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--supporting", "erpnext:v99.0.0"))
    assert result.exit_code == 1
    assert "architect evidence extract erpnext" in result.stdout


def test_the_same_supporting_repository_twice_is_rejected_by_the_engine(
    frappe_evidence_dir: Path, pattern_dir: Path
) -> None:
    # The CLI validates shape; whether a corpus may support this subject is
    # the engine's precondition, so there is exactly one place that decides.
    result = runner.invoke(
        app,
        _args(
            frappe_evidence_dir,
            pattern_dir,
            "--supporting",
            "frappe:v15.103.1",
            "--supporting",
            "frappe:v15.103.1",
            repository="erpnext",
        ),
    )
    assert result.exit_code == 1
    assert "more than once" in result.stdout


def test_a_failing_supporting_run_still_emits_all_six_sections(evidence_dir: Path, pattern_dir: Path) -> None:
    result = runner.invoke(app, _args(evidence_dir, pattern_dir, "--supporting", "nonsense"))
    for section in SECTION_ORDER:
        assert section.upper().replace("_", " ") in result.stdout
    assert result.stdout.rstrip().endswith("exit: 1")
