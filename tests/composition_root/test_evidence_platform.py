"""Tests for `composition_root.evidence_platform` (Evidence Platform CLI
Architecture Specification v1.1 §5).

These run the **real** engines against a small, real, self-authored source
tree -- no mock of `extract_evidence` or `aggregate_patterns` anywhere.
The functions under test are thin by design, so a test that stubbed the
engines would assert nothing but its own stubs.
"""

from __future__ import annotations

import ast
import inspect
import shutil
from pathlib import Path

import pytest

from aggregation.contract import PatternSet
from composition_root import evidence_platform
from composition_root.evidence_platform import (
    CANONICAL_REPOSITORY_NAMES,
    EVIDENCE_PLATFORM_ERRORS,
    aggregate_repository_patterns,
    extract_repository_evidence,
    read_repository_patterns,
)
from evidence.contract import EvidenceCategory, EvidenceSet
from evidence.errors import EvidenceError_

# -- A small, real Frappe-shaped tree ------------------------------------------------------------------

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
@frappe.read_only()
def get_report():
    return {}
"""


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "erpnext" / "doctype" / "customer").mkdir(parents=True)
    (root / "erpnext" / "doctype" / "customer" / "customer.py").write_text(_CUSTOMER_PY)
    (root / "erpnext" / "api.py").write_text(_API_PY)
    return root


@pytest.fixture
def artifacts(tmp_path: Path) -> dict[str, Path]:
    out = tmp_path / "out"
    out.mkdir()
    return {
        "evidence_path": out / "erpnext.evidence.jsonl",
        "meta_path": out / "erpnext.meta.json",
        "patterns_path": out / "erpnext.patterns.jsonl",
        "pattern_meta_path": out / "erpnext.patterns.meta.json",
    }


def _extract(source_root: Path, artifacts: dict[str, Path], *, repository: str = "erpnext") -> EvidenceSet:
    return extract_repository_evidence(
        repository=repository,
        source_root=str(source_root),
        version="v15.102.0",
        commit="0" * 40,
        correlation_id="corr-1",
        requested_by="test-suite",
        max_files=1_000,
        timeout_seconds=30.0,
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )


def _aggregate(artifacts: dict[str, Path], *, min_occurrences: int = 1) -> PatternSet:
    return aggregate_repository_patterns(
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
        min_occurrences=min_occurrences,
        correlation_id="corr-2",
        requested_by="test-suite",
    )


# -- The two constants the CLI reads instead of importing an engine ------------------------------------


def test_canonical_repository_names_are_plain_strings() -> None:
    # The CLI puts these in --help and in its own error text. If they were
    # enum members, the CLI would be handling an engine type.
    assert CANONICAL_REPOSITORY_NAMES == ("frappe", "erpnext")
    for name in CANONICAL_REPOSITORY_NAMES:
        assert type(name) is str


def test_exposed_error_types_are_the_two_engine_base_classes() -> None:
    from aggregation.errors import AggregationError_

    assert EVIDENCE_PLATFORM_ERRORS == (EvidenceError_, AggregationError_)


# -- extract_repository_evidence -------------------------------------------------------------------------


def test_extract_runs_the_real_engine_and_persists_both_artifacts(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    evidence_set = _extract(source_root, artifacts)

    assert evidence_set.statistics.evidence_extracted > 0
    assert artifacts["evidence_path"].exists()
    assert artifacts["meta_path"].exists()


def test_extract_returns_exactly_what_it_wrote(source_root: Path, artifacts: dict[str, Path]) -> None:
    # The returned object is the persisted object -- a caller rendering the
    # return value is rendering the artifact, not a second computation.
    from evidence.persistence import read_evidence_set

    returned = _extract(source_root, artifacts)
    assert read_evidence_set(artifacts["evidence_path"], artifacts["meta_path"]) == returned


def test_extract_accepts_the_repository_as_a_plain_string(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    # The caller never constructs `CanonicalRepository`; this function does.
    evidence_set = _extract(source_root, artifacts, repository="frappe")
    assert evidence_set.repository.value == "frappe"


def test_extract_rejects_an_unknown_repository_name(source_root: Path, artifacts: dict[str, Path]) -> None:
    with pytest.raises(ValueError):
        _extract(source_root, artifacts, repository="apex_dashboard")


def test_extract_lets_an_engine_error_propagate_unchanged(tmp_path: Path, artifacts: dict[str, Path]) -> None:
    # The Composition Root owns no error policy. Mapping EvidenceError_ to
    # an exit code is the CLI's job (§7), not this layer's.
    with pytest.raises(EvidenceError_):
        _extract(tmp_path / "does-not-exist", artifacts)
    assert not artifacts["evidence_path"].exists()


# -- aggregate_repository_patterns ------------------------------------------------------------------------


def test_aggregate_reads_persisted_evidence_and_persists_patterns(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    _extract(source_root, artifacts)
    pattern_set = _aggregate(artifacts)

    assert pattern_set.statistics.patterns_produced > 0
    assert artifacts["patterns_path"].exists()
    assert artifacts["pattern_meta_path"].exists()


def test_aggregate_honours_the_supplied_min_occurrences(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    _extract(source_root, artifacts)
    # `frappe.read_only` occurs once in the fixture: visible at 1, filtered at 2.
    assert _aggregate(artifacts, min_occurrences=1).statistics.patterns_produced > (
        _aggregate(artifacts, min_occurrences=2).statistics.patterns_produced
    )


def test_aggregate_surfaces_the_declared_skip(source_root: Path, artifacts: dict[str, Path]) -> None:
    # The lifecycle-hook denominator gap must survive the trip through this
    # layer intact -- it is a result, not a diagnostic.
    _extract(source_root, artifacts)
    pattern_set = _aggregate(artifacts)

    # Asserted by category rather than by count: since Sprint 22 the
    # corpus also carries structural class-definition Evidence, which
    # has no population basis and therefore also skips. The invariant
    # that matters is that the lifecycle-hook gap is reported with its
    # reason intact, not how many skips happen to exist alongside it.
    hook_skips = [
        skipped
        for skipped in pattern_set.skipped_aggregations
        if skipped.evidence_category is EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK
    ]
    assert len(hook_skips) == 1
    assert hook_skips[0].reason


def test_aggregate_never_reaches_for_a_source_tree(source_root: Path, artifacts: dict[str, Path]) -> None:
    # Delete the source tree after extraction: aggregation must still work,
    # proving it consumed the persisted artifact only.
    _extract(source_root, artifacts)
    shutil.rmtree(source_root)

    assert _aggregate(artifacts).statistics.patterns_produced > 0


# -- read_repository_patterns -------------------------------------------------------------------------------


def test_read_returns_the_persisted_pattern_set_unchanged(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    _extract(source_root, artifacts)
    written = _aggregate(artifacts)

    restored = read_repository_patterns(
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
    )
    assert restored == written


# -- The chain end to end ------------------------------------------------------------------------------------


def test_extract_then_aggregate_then_read_is_one_coherent_chain(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    evidence_set = _extract(source_root, artifacts)
    pattern_set = _aggregate(artifacts)
    read_back = read_repository_patterns(
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
    )

    assert pattern_set.repository is evidence_set.repository
    assert pattern_set.statistics.evidence_records_consumed == evidence_set.statistics.evidence_extracted
    assert read_back.pattern_set_id == pattern_set.pattern_set_id


# -- These functions stay thin -------------------------------------------------------------------------------


def _function_bodies() -> list[ast.FunctionDef]:
    tree = ast.parse(inspect.getsource(evidence_platform))
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def test_the_composition_root_owns_no_analysis_logic() -> None:
    # §5: each function calls an engine entry point and a persistence
    # function, nothing more. Scoped to function bodies -- the module-level
    # `CANONICAL_REPOSITORY_NAMES` derives its value from the enum, which is
    # data exposure, not logic. Checked against the parsed AST rather than
    # the source text, so a docstring can discuss branching without the
    # test mistaking prose for code.
    #
    # `ast.comprehension` was originally forbidden too, as a crisp proxy
    # for "owns no logic". Sprint 22's `--supporting` made that proxy wrong
    # rather than the code: reading N supporting artifacts is unavoidably a
    # repetition over N, and it filters nothing, counts nothing and decides
    # nothing. The narrower guard below is what the rule always meant --
    # no branching, no comparison, no arithmetic -- and a comprehension is
    # still only permitted because the call allow-list in the next test
    # constrains what may appear inside one.
    forbidden = (ast.If, ast.While, ast.Try, ast.Compare, ast.BinOp)
    violations = [
        type(node).__name__
        for function in _function_bodies()
        for node in ast.walk(function)
        if isinstance(node, forbidden)
    ]
    assert violations == []


def test_these_functions_only_call_engine_and_persistence_entry_points() -> None:
    # If arithmetic, filtering, or a threshold decision ever appears here,
    # it has escaped the engine that tests it.
    called = {
        node.func.id
        for function in _function_bodies()
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called == {
        "CanonicalRepository",
        "EvidenceExtractionRequest",
        "extract_evidence",
        "write_evidence_set",
        "read_evidence_set",
        "AggregationRequest",
        "aggregate_patterns",
        "write_pattern_set",
        "read_pattern_set",
        # A container constructor, not analysis: it materialises the
        # supporting corpora the caller already named. Nothing is selected
        # or rejected -- every path supplied is read, in the order given.
        "tuple",
    }


def test_no_loop_statement_appears_anywhere() -> None:
    # A `for` statement is where filtering and accumulation live, so it
    # stays forbidden even though a comprehension is now allowed: the
    # comprehension's permitted calls are bounded by the allow-list above,
    # a loop body's would not be.
    violations = [
        type(node).__name__
        for function in _function_bodies()
        for node in ast.walk(function)
        if isinstance(node, ast.For | ast.AsyncFor)
    ]
    assert violations == []


def test_composition_root_package_does_not_re_export_these_functions() -> None:
    # Deliberate: re-exporting would make `import composition_root` pull in
    # `evidence` and `aggregation` on every CLI invocation, including
    # `architect doctor`. The CLI imports this module lazily instead.
    import composition_root

    assert composition_root.__all__ == ["run_goal_end_to_end"]
    for name in ("extract_repository_evidence", "aggregate_repository_patterns", "read_repository_patterns"):
        assert not hasattr(composition_root, name)
