"""Tests for `aggregation.inheritance` (Inheritance Resolution Specification §4).

The resolver is a pure function over records, so every test here builds
its graph explicitly rather than extracting one. That is the point of
isolating it as a component: its behaviour is stated in classes and bases,
not in a repository that has to be on disk.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceKind,
    EvidenceSet,
    EvidenceStatistics,
    Source,
)

from aggregation.errors import AggregationError_
from aggregation.inheritance import ClassDescentResult, resolve_descent

_COMMIT = "1d14ba16398db3a220873509565c60f2932bed81"


def _record(
    repository: CanonicalRepository,
    category: EvidenceCategory,
    symbol: str,
    subject: str,
    line: int,
) -> Evidence:
    return Evidence(
        evidence_id=f"{symbol}|{subject}|{category.value}",
        kind=EvidenceKind.IMPLEMENTATION,
        category=category,
        symbol=symbol,
        subject=subject,
        source=Source(
            repository=repository,
            version="v1.0.0",
            commit=_COMMIT,
            relative_path="pkg/module.py",
            line=line,
        ),
        collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
        collected_at="2026-07-29T12:00:00+00:00",
    )


def _corpus(
    repository: CanonicalRepository,
    classes: dict[str, list[str]],
    *,
    module: str = "pkg.module",
) -> EvidenceSet:
    """Builds an `EvidenceSet` from `{"ClassName": ["Base", ...]}`.

    A class with an empty base list still produces its definition record
    and no edge records -- the shape the collector guarantees, reproduced
    here so the resolver is tested against the real record layout.
    """

    records: list[Evidence] = []
    for line, (class_name, bases) in enumerate(classes.items(), start=1):
        symbol = f"{module}.{class_name}"
        records.append(_record(repository, EvidenceCategory.CLASS_DEFINITION, symbol, class_name, line))
        for base in bases:
            records.append(_record(repository, EvidenceCategory.CLASS_BASE_DECLARATION, symbol, base, line))
    return EvidenceSet(
        evidence_set_id=f"evset-{repository.value}",
        schema_version="1.0",
        repository=repository,
        version="v1.0.0",
        commit=_COMMIT,
        extracted_at="2026-07-29T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=tuple(records),
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=len(records)
        ),
    )


def _names(result: ClassDescentResult) -> set[str]:
    return {symbol.rsplit(".", 1)[-1] for symbol in result.descendants}


# -- Direct inheritance ---------------------------------------------------------------------------------


def test_a_class_declaring_the_root_descends_from_it() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Customer": ["Document"], "Helper": []})
    result = resolve_descent(corpus, root="Document")

    assert _names(result) == {"Customer"}


def test_the_root_need_not_be_defined_in_any_supplied_corpus() -> None:
    # Membership is by name, not by definition. Measuring ERPNext without
    # frappe must still resolve its 448 direct subclasses rather than
    # collapsing to zero because `Document` itself was not supplied.
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Customer": ["Document"]})
    assert _names(resolve_descent(corpus, root="Document")) == {"Customer"}


def test_a_qualified_base_spelling_matches_the_bare_root() -> None:
    # §4.2 rule 1. Both spellings occur in the real trees; reconciling
    # them is this component's one normalising step.
    corpus = _corpus(
        CanonicalRepository.ERPNEXT,
        {"A": ["Document"], "B": ["frappe.model.document.Document"], "C": ["document.Document"]},
    )
    assert _names(resolve_descent(corpus, root="Document")) == {"A", "B", "C"}


def test_a_class_with_no_bases_never_descends() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Plain": [], "Customer": ["Document"]})
    assert _names(resolve_descent(corpus, root="Document")) == {"Customer"}


def test_multiple_inheritance_counts_the_class_once() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Customer": ["Document", "NestedSet"]})
    result = resolve_descent(corpus, root="Document")

    assert len(result.descendants) == 1


# -- Multi-level inheritance ----------------------------------------------------------------------------


def test_descent_is_transitive_through_an_intermediate_base() -> None:
    corpus = _corpus(
        CanonicalRepository.ERPNEXT,
        {"AccountsController": ["Document"], "SalesInvoice": ["AccountsController"]},
    )
    assert _names(resolve_descent(corpus, root="Document")) == {"AccountsController", "SalesInvoice"}


def test_a_chain_of_depth_six_is_fully_resolved() -> None:
    # RQ-0002 measured depth 6 in real ERPNext. A resolver that stopped
    # following chains early would still return plausible descendants --
    # it would simply return fewer of them, silently.
    chain = {"L0": ["Document"]}
    for level in range(1, 7):
        chain[f"L{level}"] = [f"L{level - 1}"]
    result = resolve_descent(_corpus(CanonicalRepository.ERPNEXT, chain), root="Document")

    assert _names(result) == {f"L{level}" for level in range(7)}
    assert result.max_depth == 6


def test_a_single_level_check_would_not_satisfy_these_tests() -> None:
    # Stated as its own case because the failure mode is quiet: matching
    # only `class X(Document)` returns a correct-looking subset.
    corpus = _corpus(
        CanonicalRepository.ERPNEXT,
        {"Base": ["Document"], "Middle": ["Base"], "Leaf": ["Middle"]},
    )
    direct_only = {"Base"}
    assert _names(resolve_descent(corpus, root="Document")) > direct_only


# -- Cross-repository resolution ------------------------------------------------------------------------


def test_a_supporting_corpus_completes_a_chain_that_leaves_the_repository() -> None:
    # RQ-0002 F6, in miniature: 18 real ERPNext controllers reach Document
    # only through NestedSet or WebsiteGenerator, both defined in frappe.
    frappe = _corpus(CanonicalRepository.FRAPPE, {"NestedSet": ["Document"]}, module="frappe.utils")
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Account": ["NestedSet"]})

    assert _names(resolve_descent(erpnext, root="Document")) == set()
    assert _names(resolve_descent(erpnext, (frappe,), root="Document")) == {"Account"}


def test_supporting_classes_never_enter_the_result() -> None:
    # §5.2, enforced by the shape of the output rather than by a caller
    # remembering it: frappe's NestedSet explains why an ERPNext class is
    # a controller; it does not thereby become one of ERPNext's.
    frappe = _corpus(CanonicalRepository.FRAPPE, {"NestedSet": ["Document"]}, module="frappe.utils")
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Account": ["NestedSet"]})

    result = resolve_descent(erpnext, (frappe,), root="Document")
    assert result.descendants == ("pkg.module.Account",)
    for symbol in result.descendants:
        assert not symbol.startswith("frappe.")


def test_the_measured_corpus_is_never_swapped_for_a_supporting_one() -> None:
    frappe = _corpus(CanonicalRepository.FRAPPE, {"NestedSet": ["Document"]}, module="frappe.utils")
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Account": ["NestedSet"]})

    measuring_frappe = resolve_descent(frappe, (erpnext,), root="Document")
    assert _names(measuring_frappe) == {"NestedSet"}


# -- Corpus validation ----------------------------------------------------------------------------------


def test_the_measured_repository_is_rejected_as_its_own_support() -> None:
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Customer": ["Document"]})
    with pytest.raises(AggregationError_, match="own resolution context"):
        resolve_descent(erpnext, (erpnext,), root="Document")


def test_a_duplicate_supporting_repository_is_rejected() -> None:
    # Typically two versions of the same repository -- under which a class
    # name could resolve against either, making descent ambiguous.
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Customer": ["Document"]})
    frappe = _corpus(CanonicalRepository.FRAPPE, {"NestedSet": ["Document"]})
    other = frappe.model_copy(update={"version": "v15.99.0"})

    with pytest.raises(AggregationError_, match="more than once"):
        resolve_descent(erpnext, (frappe, other), root="Document")


# -- Unresolved bases -----------------------------------------------------------------------------------


def test_a_base_matching_no_definition_is_reported_as_unresolved() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Error": ["Exception"], "Customer": ["Document"]})
    result = resolve_descent(corpus, root="Document")

    assert result.unresolved_bases == ("Exception",)
    assert _names(result) == {"Customer"}


def test_unresolved_bases_keep_their_written_spelling() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Error": ["exceptions.ValidationError"]})
    assert resolve_descent(corpus, root="Document").unresolved_bases == ("exceptions.ValidationError",)


def test_the_root_itself_is_never_reported_unresolved() -> None:
    # `Document` is usually not defined in the corpus being measured; that
    # is expected, not a residue.
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Customer": ["Document"]})
    assert resolve_descent(corpus, root="Document").unresolved_bases == ()


def test_a_base_defined_in_a_supporting_corpus_is_not_unresolved() -> None:
    frappe = _corpus(CanonicalRepository.FRAPPE, {"NestedSet": ["Document"]}, module="frappe.utils")
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Account": ["NestedSet"]})

    assert resolve_descent(erpnext, root="Document").unresolved_bases == ("NestedSet",)
    assert resolve_descent(erpnext, (frappe,), root="Document").unresolved_bases == ()


# -- Cycles ---------------------------------------------------------------------------------------------


def test_a_cycle_that_never_reaches_the_root_terminates() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"A": ["B"], "B": ["A"]})
    result = resolve_descent(corpus, root="Document")

    assert result.descendants == ()


def test_a_cycle_reachable_from_the_root_terminates_and_resolves_once() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"A": ["Document", "B"], "B": ["A"], "C": ["B"]})
    result = resolve_descent(corpus, root="Document")

    assert _names(result) == {"A", "B", "C"}
    assert len(result.descendants) == len(set(result.descendants))


def test_a_self_referential_class_terminates() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"A": ["Document", "A"]})
    assert _names(resolve_descent(corpus, root="Document")) == {"A"}


# -- Determinism ----------------------------------------------------------------------------------------


def test_descendants_are_sorted() -> None:
    corpus = _corpus(
        CanonicalRepository.ERPNEXT, {"Zebra": ["Document"], "Alpha": ["Document"], "Middle": ["Document"]}
    )
    result = resolve_descent(corpus, root="Document")

    assert list(result.descendants) == sorted(result.descendants)


def test_unresolved_bases_are_sorted_and_deduplicated() -> None:
    corpus = _corpus(
        CanonicalRepository.ERPNEXT,
        {"A": ["Zed", "Ack"], "B": ["Zed"], "C": ["Document"]},
    )
    assert resolve_descent(corpus, root="Document").unresolved_bases == ("Ack", "Zed")


def test_repeated_runs_produce_an_identical_result() -> None:
    frappe = _corpus(CanonicalRepository.FRAPPE, {"NestedSet": ["Document"]}, module="frappe.utils")
    erpnext = _corpus(
        CanonicalRepository.ERPNEXT,
        {"Account": ["NestedSet"], "Customer": ["Document"], "Error": ["Exception"]},
    )
    first = resolve_descent(erpnext, (frappe,), root="Document")
    second = resolve_descent(erpnext, (frappe,), root="Document")

    assert first == second


def test_the_result_does_not_depend_on_class_declaration_order() -> None:
    forward = _corpus(
        CanonicalRepository.ERPNEXT, {"Base": ["Document"], "Middle": ["Base"], "Leaf": ["Middle"]}
    )
    reversed_order = _corpus(
        CanonicalRepository.ERPNEXT, {"Leaf": ["Middle"], "Middle": ["Base"], "Base": ["Document"]}
    )
    assert resolve_descent(forward, root="Document").descendants == (
        resolve_descent(reversed_order, root="Document").descendants
    )


# -- The component's own boundary -----------------------------------------------------------------------


def test_the_result_carries_nothing_from_the_aggregation_vocabulary() -> None:
    # §4: it answers a question about a class graph. Population, support,
    # thresholds and status belong to layers above it.
    fields = set(ClassDescentResult.model_fields)
    for forbidden in ("population", "support", "occurrences", "status", "patterns", "threshold"):
        assert forbidden not in fields


def test_the_result_is_frozen_and_rejects_unknown_fields() -> None:
    result = resolve_descent(_corpus(CanonicalRepository.ERPNEXT, {"A": ["Document"]}), root="Document")
    with pytest.raises(ValidationError):
        result.max_depth = 99
    with pytest.raises(ValidationError):
        ClassDescentResult.model_validate({"unexpected": "field"})


def test_an_empty_corpus_resolves_to_nothing_rather_than_failing() -> None:
    corpus = _corpus(CanonicalRepository.ERPNEXT, {})
    result = resolve_descent(corpus, root="Document")

    assert result == ClassDescentResult()


def test_the_root_is_a_parameter_not_a_hardcoded_name() -> None:
    # No repository-specific logic: `Document` is an argument, and the
    # resolver behaves identically for any other root.
    corpus = _corpus(CanonicalRepository.ERPNEXT, {"Report": ["BaseReport"], "Other": ["Document"]})
    assert _names(resolve_descent(corpus, root="BaseReport")) == {"Report"}


# -- The residue is measured-repository scoped (Sprint 22, Commit 5) -------------------------------------


def test_supporting_external_bases_are_not_attributed_to_the_measured_corpus() -> None:
    # A supporting corpus contributes resolution context and nothing else.
    # Its own unresolved external bases are not the measured repository's
    # residue -- otherwise the diagnostic would grow simply because more
    # context was supplied, which is the opposite of what it reports.
    frappe = _corpus(
        CanonicalRepository.FRAPPE,
        {"NestedSet": ["Document"], "Meta": ["ABC"], "Flags": ["Enum"]},
        module="frappe.utils",
    )
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Account": ["NestedSet"], "Err": ["Exception"]})

    alone = resolve_descent(erpnext, root="Document")
    with_support = resolve_descent(erpnext, (frappe,), root="Document")

    assert alone.unresolved_bases == ("Exception", "NestedSet")
    # `NestedSet` stops being unresolved because frappe defines it; `ABC`
    # and `Enum` never appear, because they are frappe's residue, not
    # ERPNext's.
    assert with_support.unresolved_bases == ("Exception",)


def test_supplying_more_context_never_grows_the_residue() -> None:
    # The property the scoping guarantees, stated directly: context can
    # only ever resolve names, never add unresolved ones.
    frappe = _corpus(
        CanonicalRepository.FRAPPE, {"NestedSet": ["Document"], "Meta": ["ABC"]}, module="frappe.utils"
    )
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Account": ["NestedSet"], "Err": ["Exception"]})

    alone = set(resolve_descent(erpnext, root="Document").unresolved_bases)
    with_support = set(resolve_descent(erpnext, (frappe,), root="Document").unresolved_bases)

    assert with_support <= alone


def test_resolution_still_consults_every_corpus_for_lookup() -> None:
    # Only the attribution is narrowed. A base defined anywhere counts as
    # resolved, which is what lets a cross-repository chain complete.
    frappe = _corpus(CanonicalRepository.FRAPPE, {"NestedSet": ["Document"]}, module="frappe.utils")
    erpnext = _corpus(CanonicalRepository.ERPNEXT, {"Account": ["NestedSet"]})

    result = resolve_descent(erpnext, (frappe,), root="Document")
    assert result.unresolved_bases == ()
    assert _names(result) == {"Account"}
