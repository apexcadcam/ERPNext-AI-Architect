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
from pathlib import Path

import pytest

from composition_root import evidence_platform
from composition_root.evidence_platform import (
    aggregate_repository_patterns,
    extract_repository_evidence,
    read_repository_patterns,
)
from evidence.contract import CanonicalRepository, EvidenceExtractionRequest
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


def _request(source_root: Path) -> EvidenceExtractionRequest:
    return EvidenceExtractionRequest(
        repository=CanonicalRepository.ERPNEXT,
        source_root=str(source_root),
        version="v15.102.0",
        commit="0" * 40,
        correlation_id="corr-1",
        requested_by="test-suite",
        max_files=1_000,
        timeout_seconds=30.0,
    )


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


# -- extract_repository_evidence -------------------------------------------------------------------------


def test_extract_runs_the_real_engine_and_persists_both_artifacts(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    evidence_set = extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )

    assert evidence_set.statistics.evidence_extracted > 0
    assert artifacts["evidence_path"].exists()
    assert artifacts["meta_path"].exists()


def test_extract_returns_exactly_what_it_wrote(source_root: Path, artifacts: dict[str, Path]) -> None:
    # The returned object is the persisted object -- a caller rendering the
    # return value is rendering the artifact, not a second computation.
    from evidence.persistence import read_evidence_set

    returned = extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )
    assert read_evidence_set(artifacts["evidence_path"], artifacts["meta_path"]) == returned


def test_extract_lets_an_engine_error_propagate_unchanged(tmp_path: Path, artifacts: dict[str, Path]) -> None:
    # The Composition Root owns no error policy. Mapping EvidenceError_ to
    # an exit code is the CLI's job (§7), not this layer's.
    request = _request(tmp_path / "does-not-exist")
    with pytest.raises(EvidenceError_):
        extract_repository_evidence(
            request,
            evidence_path=artifacts["evidence_path"],
            meta_path=artifacts["meta_path"],
        )
    assert not artifacts["evidence_path"].exists()


# -- aggregate_repository_patterns ------------------------------------------------------------------------


def test_aggregate_reads_persisted_evidence_and_persists_patterns(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )

    pattern_set = aggregate_repository_patterns(
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
        min_occurrences=1,
        correlation_id="corr-2",
        requested_by="test-suite",
    )

    assert pattern_set.statistics.patterns_produced > 0
    assert artifacts["patterns_path"].exists()
    assert artifacts["pattern_meta_path"].exists()


def test_aggregate_honours_the_supplied_min_occurrences(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )

    def run(min_occurrences: int) -> int:
        return aggregate_repository_patterns(
            evidence_path=artifacts["evidence_path"],
            meta_path=artifacts["meta_path"],
            patterns_path=artifacts["patterns_path"],
            pattern_meta_path=artifacts["pattern_meta_path"],
            min_occurrences=min_occurrences,
            correlation_id="corr-2",
            requested_by="test-suite",
        ).statistics.patterns_produced

    # `frappe.read_only` occurs once in the fixture: visible at 1, filtered at 2.
    assert run(1) > run(2)


def test_aggregate_surfaces_the_declared_skip(source_root: Path, artifacts: dict[str, Path]) -> None:
    # The lifecycle-hook denominator gap must survive the trip through this
    # layer intact -- it is a result, not a diagnostic.
    extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )
    pattern_set = aggregate_repository_patterns(
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
        min_occurrences=1,
        correlation_id="corr-2",
        requested_by="test-suite",
    )
    assert len(pattern_set.skipped_aggregations) == 1
    assert pattern_set.skipped_aggregations[0].reason


def test_aggregate_never_reaches_for_a_source_tree(source_root: Path, artifacts: dict[str, Path]) -> None:
    # Delete the source tree after extraction: aggregation must still work,
    # proving it consumed the persisted artifact only.
    import shutil

    extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )
    shutil.rmtree(source_root)

    pattern_set = aggregate_repository_patterns(
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
        min_occurrences=1,
        correlation_id="corr-2",
        requested_by="test-suite",
    )
    assert pattern_set.statistics.patterns_produced > 0


# -- read_repository_patterns -------------------------------------------------------------------------------


def test_read_returns_the_persisted_pattern_set_unchanged(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )
    written = aggregate_repository_patterns(
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
        min_occurrences=1,
        correlation_id="corr-2",
        requested_by="test-suite",
    )

    restored = read_repository_patterns(
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
    )
    assert restored == written


# -- The chain end to end ------------------------------------------------------------------------------------


def test_extract_then_aggregate_then_read_is_one_coherent_chain(
    source_root: Path, artifacts: dict[str, Path]
) -> None:
    evidence_set = extract_repository_evidence(
        _request(source_root),
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
    )
    pattern_set = aggregate_repository_patterns(
        evidence_path=artifacts["evidence_path"],
        meta_path=artifacts["meta_path"],
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
        min_occurrences=1,
        correlation_id="corr-2",
        requested_by="test-suite",
    )
    read_back = read_repository_patterns(
        patterns_path=artifacts["patterns_path"],
        pattern_meta_path=artifacts["pattern_meta_path"],
    )

    assert pattern_set.repository is evidence_set.repository
    assert pattern_set.statistics.evidence_records_consumed == evidence_set.statistics.evidence_extracted
    assert read_back.pattern_set_id == pattern_set.pattern_set_id


# -- These functions stay thin -------------------------------------------------------------------------------


def test_the_composition_root_owns_no_analysis_logic() -> None:
    # §5: each function calls an engine entry point and a persistence
    # function, nothing more. Checked against the parsed AST rather than
    # the source text, so a docstring can discuss branching without the
    # test mistaking prose for code.
    tree = ast.parse(inspect.getsource(evidence_platform))
    forbidden = (ast.If, ast.For, ast.While, ast.Try, ast.Compare, ast.BinOp, ast.comprehension)
    violations = [type(node).__name__ for node in ast.walk(tree) if isinstance(node, forbidden)]
    assert violations == []


def test_these_functions_only_call_engine_and_persistence_entry_points() -> None:
    # If arithmetic, filtering, or a threshold decision ever appears here,
    # it has escaped the engine that tests it.
    tree = ast.parse(inspect.getsource(evidence_platform))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called == {
        "extract_evidence",
        "write_evidence_set",
        "read_evidence_set",
        "AggregationRequest",
        "aggregate_patterns",
        "write_pattern_set",
        "read_pattern_set",
    }


def test_composition_root_package_does_not_re_export_these_functions() -> None:
    # Deliberate: re-exporting would make `import composition_root` pull in
    # `evidence` and `aggregation` on every CLI invocation, including
    # `architect doctor`. The CLI imports this module lazily instead.
    import composition_root

    assert composition_root.__all__ == ["run_goal_end_to_end"]
    for name in ("extract_repository_evidence", "aggregate_repository_patterns", "read_repository_patterns"):
        assert not hasattr(composition_root, name)
