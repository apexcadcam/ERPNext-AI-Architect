"""Real-corpus regression tests over the committed Evidence and Pattern
artifacts.

**Why this file exists.** Until Sprint 24 every figure this platform has
published -- 275, 510, 153, `validate 84/275`, `180/510`, `66/153` -- was
verified by hand, once, at release time. Nothing in the suite read
`evidence-data/` or `pattern-data/` at all, so a regeneration that
silently moved a denominator would have passed every test in the
repository. RQ-0004 is the reason that matters: it measured a population
coming out 143, 145, 150 or 153 depending on context, with no error
raised in any of the wrong cases. A wrong number here does not announce
itself.

**What this file deliberately is not.** It is not a golden-file test of
every Pattern line -- the artifacts are already the detailed record, and
duplicating them here would create a second copy to keep in sync and
would fail noisily for changes nobody cares about. It asserts the
*load-bearing* facts: the published figures a reader would quote, the
schema label, the resolution context each population depended on, and the
accounting invariants that must hold whatever the numbers are.

**It is also not a second implementation of the engine.** Nothing here
resolves descent, walks a class graph, or recomputes a population. The
Sprint 22 membership invariant is asserted in the strongest form the
artifacts themselves support -- occurrences drawn from the measured
corpus, bounded by the population -- and the graph-level proof stays in
`tests/aggregation/test_inheritance.py`, where the resolver is under test
and the input is controlled.

No network, no source tree, no extraction. These tests read six committed
files and nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "evidence-data"
PATTERN_DIR = REPO_ROOT / "pattern-data"

#: The artifact schema every committed corpus must carry. `3.0` since
#: Sprint 24, when `CanonicalRepository` gained `hrms` -- a `3.0` artifact
#: may name a repository a `2.0` reader has never seen.
EXPECTED_SCHEMA_VERSION = "3.0"

#: The three committed corpora, by artifact stem. `hrms` deliberately has
#: no `v` prefix: `hrms/__init__.py` declares `15.51.0`, `version`
#: participates in artifact identity, and normalising it would rename the
#: artifact (W10).
FRAPPE = "frappe-v15.103.1"
ERPNEXT = "erpnext-v15.102.0"
HRMS = "hrms-15.51.0"
ALL_CORPORA = (FRAPPE, ERPNEXT, HRMS)

_LIFECYCLE = "controller_lifecycle_hook"
_WHITELIST = "whitelisted_api_decoration"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _patterns(stem: str) -> list[dict[str, Any]]:
    return _read_jsonl(PATTERN_DIR / f"{stem}.patterns.jsonl")


def _pattern_meta(stem: str) -> dict[str, Any]:
    return dict(json.loads((PATTERN_DIR / f"{stem}.meta.json").read_text(encoding="utf-8")))


def _evidence(stem: str) -> list[dict[str, Any]]:
    return _read_jsonl(EVIDENCE_DIR / f"{stem}.evidence.jsonl")


def _evidence_meta(stem: str) -> dict[str, Any]:
    return dict(json.loads((EVIDENCE_DIR / f"{stem}.meta.json").read_text(encoding="utf-8")))


def _measure(stem: str, category: str, subject: str) -> tuple[int, int]:
    """One published figure, as `(occurrences, population)`."""

    pattern = next(
        p for p in _patterns(stem) if p["evidence_category"] == category and p["subject"] == subject
    )
    return pattern["occurrences"], pattern["population"]


def _population(stem: str, category: str) -> set[int]:
    """Every population quoted for a category -- a set, because all
    Patterns of one category share one denominator by construction, and a
    set with two members would mean that stopped being true.
    """

    return {p["population"] for p in _patterns(stem) if p["evidence_category"] == category}


# -- The published figures -----------------------------------------------------------------------------
#
# These are the numbers a reader quotes. They move only when a corpus is
# repinned to a new commit, which is a deliberate act with its own review.


def test_frappe_publishes_its_released_measurements() -> None:
    assert _population(FRAPPE, _LIFECYCLE) == {275}
    assert _measure(FRAPPE, _LIFECYCLE, "validate") == (84, 275)
    assert _measure(FRAPPE, _WHITELIST, "frappe.whitelist") == (518, 520)
    assert _measure(FRAPPE, _WHITELIST, "frappe.validate_and_sanitize_search_inputs") == (15, 520)


def test_erpnext_publishes_its_released_measurements() -> None:
    assert _population(ERPNEXT, _LIFECYCLE) == {510}
    assert _measure(ERPNEXT, _LIFECYCLE, "validate") == (180, 510)
    assert _measure(ERPNEXT, _WHITELIST, "frappe.whitelist") == (705, 705)
    assert _measure(ERPNEXT, _WHITELIST, "frappe.validate_and_sanitize_search_inputs") == (59, 705)


def test_hrms_reproduces_the_figures_rq_0004_measured() -> None:
    # The whole point of ADR-0017: 143, 145 and 150 are all reachable, all
    # plausible, and all wrong. Only the complete closure yields 153.
    assert _population(HRMS, _LIFECYCLE) == {153}
    assert _measure(HRMS, _LIFECYCLE, "validate") == (66, 153)
    assert _population(HRMS, _WHITELIST) == {198}
    assert _measure(HRMS, _WHITELIST, "frappe.whitelist") == (198, 198)


def test_hrms_evidence_reproduces_the_extraction_rq_0004_measured() -> None:
    meta = _evidence_meta(HRMS)
    statistics = meta["statistics"]

    assert meta["commit"] == "031e97ba05ea9ba3250278450c58be01b7774f6a"
    assert meta["version"] == "15.51.0"  # never normalised to v15.51.0
    assert statistics["evidence_extracted"] == 976
    assert statistics["files_failed"] == 0
    # RQ-0004's "613 files" is Python files *parsed*, not filesystem
    # entries walked. The walker examines the whole tree and skips
    # everything that is not Python, so the two metrics are far apart and
    # must not be conflated.
    assert statistics["files_examined"] - statistics["files_skipped"] == 613


# -- Resolution context: which corpora produced each population ----------------------------------------


def test_frappe_resolved_its_population_without_any_supporting_corpus() -> None:
    provenance = _pattern_meta(FRAPPE)["resolution_provenance"]

    assert provenance["strategy"] == "single_corpus"
    assert provenance["supporting_corpora"] == []
    # 40 legitimate stdlib and third-party bases. Recorded, never used as
    # an admission rule -- ADR-0017 §6 rejects requiring zero, precisely
    # because it would disqualify the framework itself.
    assert provenance["unresolved_bases_count"] == 40


def test_erpnext_resolved_its_population_with_frappe_context() -> None:
    provenance = _pattern_meta(ERPNEXT)["resolution_provenance"]

    assert provenance["strategy"] == "multi_corpus"
    assert [c["repository"] for c in provenance["supporting_corpora"]] == ["frappe"]
    assert provenance["supporting_corpora"][0]["version"] == "v15.103.1"
    assert provenance["unresolved_bases_count"] == 4


def test_hrms_resolved_its_population_with_its_complete_registered_closure() -> None:
    provenance = _pattern_meta(HRMS)["resolution_provenance"]

    assert provenance["strategy"] == "multi_corpus"
    # Canonically ordered by `(repository, version, commit)`, so the
    # artifact does not depend on the order the flags were typed in. The
    # order carries no precedence: `erpnext` first is alphabetical, not
    # architectural.
    assert [c["repository"] for c in provenance["supporting_corpora"]] == ["erpnext", "frappe"]
    assert [c["version"] for c in provenance["supporting_corpora"]] == ["v15.102.0", "v15.103.1"]
    assert provenance["unresolved_bases_count"] == 0


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_every_measured_corpus_records_its_own_identity(stem: str) -> None:
    meta = _pattern_meta(stem)
    measured = meta["resolution_provenance"]["measured_corpus"]

    assert measured["repository"] == meta["repository"]
    assert measured["version"] == meta["version"]
    assert measured["commit"] == meta["commit"]


# -- Invariants that must hold whatever the numbers are ------------------------------------------------


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_the_artifact_declares_the_current_schema_version(stem: str) -> None:
    assert _evidence_meta(stem)["schema_version"] == EXPECTED_SCHEMA_VERSION
    assert _pattern_meta(stem)["schema_version"] == EXPECTED_SCHEMA_VERSION


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_every_support_is_a_real_share_of_its_population(stem: str) -> None:
    for pattern in _patterns(stem):
        assert 1 <= pattern["occurrences"] <= pattern["population"]
        assert 0.0 <= pattern["support"] <= 1.0
        assert pattern["support"] == pytest.approx(pattern["occurrences"] / pattern["population"])


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_category_accounting_adds_up(stem: str) -> None:
    statistics = _pattern_meta(stem)["statistics"]

    assert (
        statistics["categories_aggregated"] + statistics["categories_skipped"]
        == statistics["categories_present"]
    )
    assert statistics["patterns_produced"] == len(_patterns(stem))


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_every_pattern_is_owned_by_the_measured_repository(stem: str) -> None:
    # ADR-0015 containment, as the artifact shows it: a supporting corpus
    # explains why a class is a controller; it never becomes one, and it
    # owns nothing here.
    meta = _pattern_meta(stem)
    for pattern in _patterns(stem):
        assert pattern["repository"] == meta["repository"]
        assert pattern["version"] == meta["version"]
        assert pattern["commit"] == meta["commit"]


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_no_supporting_corpus_evidence_was_counted_as_an_occurrence(stem: str) -> None:
    """The leakage check, done entirely from artifact-local facts.

    Every `supporting_evidence_id` a Pattern cites must be an
    `evidence_id` from the *measured* corpus's own EvidenceSet. This is
    the strongest containment statement the artifacts can make without
    re-resolving the class graph, and it is the one that would have caught
    a supporting record entering a numerator.
    """

    measured_ids = {record["evidence_id"] for record in _evidence(stem)}
    cited = {cited_id for pattern in _patterns(stem) for cited_id in pattern["supporting_evidence_ids"]}

    assert cited - measured_ids == set()


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_lifecycle_occurrences_are_hook_records_from_the_measured_corpus(stem: str) -> None:
    """Sprint 22's membership invariant, in its artifact-local form.

    `occurrence_symbols ⊆ population_symbols` cannot be proved from the
    artifacts alone -- the population is a property of the resolved class
    graph, and reconstructing it here would make this file a second
    implementation of `resolve_descent`. What the artifacts *do* support
    is the half that caught the real defect in Sprint 22 Commit 7: every
    counted occurrence is a lifecycle-hook record belonging to the
    measured corpus, and the count never exceeds the denominator.
    """

    hook_ids = {r["evidence_id"] for r in _evidence(stem) if r["category"] == _LIFECYCLE}
    lifecycle = [p for p in _patterns(stem) if p["evidence_category"] == _LIFECYCLE]

    for pattern in lifecycle:
        assert set(pattern["supporting_evidence_ids"]) <= hook_ids
        assert pattern["occurrences"] <= pattern["population"]


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_pattern_ordering_is_the_engines_deterministic_order(stem: str) -> None:
    # §11: category, then most frequent first, ties alphabetical. Asserted
    # on the file as committed, because persistence replays this order and
    # never re-derives it -- so a storage bug would otherwise be invisible.
    patterns = _patterns(stem)
    keys = [(p["evidence_category"], -p["occurrences"], p["subject"]) for p in patterns]

    assert keys == sorted(keys)


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_pattern_and_evidence_identities_are_unique_within_a_corpus(stem: str) -> None:
    # Both are content-addressed, so a collision would mean two different
    # facts hashing alike -- a far more serious failure than a wrong count.
    patterns = _patterns(stem)
    evidence = _evidence(stem)

    assert len({p["pattern_id"] for p in patterns}) == len(patterns)
    assert len({r["evidence_id"] for r in evidence}) == len(evidence)


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_the_pattern_set_was_built_from_the_committed_evidence_set(stem: str) -> None:
    # The two artifacts are a pair: the Pattern metadata records how many
    # Evidence records it consumed, and the Evidence artifact must contain
    # exactly that many.
    assert _pattern_meta(stem)["statistics"]["evidence_records_consumed"] == len(_evidence(stem))
    assert _evidence_meta(stem)["statistics"]["evidence_extracted"] == len(_evidence(stem))


# -- The corpus is complete and loadable ---------------------------------------------------------------


def test_every_canonical_repository_has_a_committed_corpus() -> None:
    """A repository admitted but never measured is a claim with nothing
    behind it. Derived from the enum rather than listed, so admitting a
    fourth repository without publishing its corpus fails here.
    """

    from evidence.contract import CanonicalRepository

    committed = {_evidence_meta(stem)["repository"] for stem in ALL_CORPORA}
    assert committed == {member.value for member in CanonicalRepository}


@pytest.mark.parametrize("stem", ALL_CORPORA)
def test_the_committed_artifacts_load_under_the_current_contracts(stem: str) -> None:
    # Not a JSON check: the real deserializers, so `extra="forbid"` and
    # every field constraint are exercised against what is on disk.
    from aggregation.persistence import read_pattern_set
    from evidence.persistence import read_evidence_set

    evidence_set = read_evidence_set(
        EVIDENCE_DIR / f"{stem}.evidence.jsonl", EVIDENCE_DIR / f"{stem}.meta.json"
    )
    pattern_set = read_pattern_set(PATTERN_DIR / f"{stem}.patterns.jsonl", PATTERN_DIR / f"{stem}.meta.json")

    assert evidence_set.schema_version == EXPECTED_SCHEMA_VERSION
    assert pattern_set.schema_version == EXPECTED_SCHEMA_VERSION
    assert pattern_set.repository is evidence_set.repository
