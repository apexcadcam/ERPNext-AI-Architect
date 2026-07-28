"""Tests for `aggregation.resolvers` (Pattern Aggregation Engine Architecture
Specification v1.0 §8).
"""

from __future__ import annotations

from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceKind,
    Source,
)

from aggregation.contract import AggregationStatus
from aggregation.population import POPULATION_BASES
from aggregation.resolvers import (
    POPULATION_RESOLVERS,
    WHITELIST_FAMILY_SUBJECTS,
    resolve_whitelisted_api_population,
)

_COMMIT = "1d14ba16398db3a220873509565c60f2932bed81"


def _evidence(
    *,
    symbol: str,
    subject: str,
    category: EvidenceCategory = EvidenceCategory.WHITELISTED_API_DECORATION,
    relative_path: str = "erpnext/accounts/custom/address.py",
    line: int = 49,
) -> Evidence:
    return Evidence(
        evidence_id=f"{symbol}|{subject}|{line}".ljust(64, "0")[:64],
        kind=EvidenceKind.IMPLEMENTATION,
        category=category,
        symbol=symbol,
        subject=subject,
        source=Source(
            repository=CanonicalRepository.ERPNEXT,
            version="v15.102.0",
            commit=_COMMIT,
            relative_path=relative_path,
            line=line,
        ),
        collector=CollectorName.WHITELISTED_API_DECORATION_COLLECTOR,
        collected_at="2026-07-27T12:00:00+00:00",
    )


# -- The rule this module exists to enforce: distinct symbols, never records -------------------------


def test_counts_distinct_symbols_not_records() -> None:
    # The exact failure mode SS8 names. One function carrying three
    # decorators emits three Evidence records but is ONE member of the
    # population. Counting records would inflate the denominator and
    # silently deflate every support figure computed from it.
    records = [
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.api.get_data", subject="frappe.read_only"),
        _evidence(symbol="erpnext.api.get_data", subject="rate_limit"),
    ]

    population, _ = resolve_whitelisted_api_population(records)

    assert population == 1


def test_counts_each_distinct_symbol_once() -> None:
    records = [
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.api.get_other", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.api.get_third", subject="frappe.whitelist"),
    ]

    population, _ = resolve_whitelisted_api_population(records)

    assert population == 3


def test_the_same_symbol_across_different_files_is_still_counted_once() -> None:
    # Defensive: `symbol` is already fully module-qualified by Sprint 20,
    # so an identical symbol string is genuinely the same function.
    records = [
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist", relative_path="a.py", line=1),
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist", relative_path="b.py", line=2),
    ]

    population, _ = resolve_whitelisted_api_population(records)

    assert population == 1


# -- Both whitelist-family markers count ---------------------------------------------------------------


def test_the_attribute_form_frappe_whitelist_counts() -> None:
    records = [_evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist")]
    population, _ = resolve_whitelisted_api_population(records)
    assert population == 1


def test_the_bare_form_whitelist_counts() -> None:
    # Real, observed in frappe v15.103.1 -- e.g. `frappe/__init__.py`'s own
    # `rename_doc`, decorated with a directly-imported `@whitelist(...)`.
    records = [_evidence(symbol="frappe.rename_doc", subject="whitelist")]
    population, _ = resolve_whitelisted_api_population(records)
    assert population == 1


def test_both_forms_together_are_counted_as_distinct_symbols() -> None:
    records = [
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist"),
        _evidence(symbol="frappe.rename_doc", subject="whitelist"),
    ]
    population, _ = resolve_whitelisted_api_population(records)
    assert population == 2


def test_whitelist_family_contains_exactly_the_two_documented_markers() -> None:
    assert WHITELIST_FAMILY_SUBJECTS == frozenset({"frappe.whitelist", "whitelist"})


# -- Non-whitelist subjects do not inflate the population ---------------------------------------------


def test_a_symbol_with_only_non_whitelist_subjects_is_not_in_the_population() -> None:
    records = [
        _evidence(symbol="erpnext.helpers.cached", subject="frappe.read_only"),
        _evidence(symbol="erpnext.helpers.cached", subject="redis_cache"),
    ]

    population, _ = resolve_whitelisted_api_population(records)

    assert population == 0


def test_non_whitelist_subjects_are_ignored_while_whitelist_ones_are_counted() -> None:
    records = [
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.helpers.cached", subject="redis_cache"),
        _evidence(symbol="erpnext.helpers.other", subject="staticmethod"),
    ]

    population, _ = resolve_whitelisted_api_population(records)

    assert population == 1


def test_a_subject_that_merely_contains_whitelist_does_not_count() -> None:
    # Exact membership, not substring matching -- `not_whitelist` and
    # `whitelist_helper` are different decorators entirely.
    records = [
        _evidence(symbol="erpnext.api.a", subject="not_whitelist"),
        _evidence(symbol="erpnext.api.b", subject="whitelist_helper"),
        _evidence(symbol="erpnext.api.c", subject="frappe.whitelist_v2"),
    ]

    population, _ = resolve_whitelisted_api_population(records)

    assert population == 0


# -- Empty input ---------------------------------------------------------------------------------------


def test_empty_input_yields_a_zero_population_without_raising() -> None:
    # SS10: no ordinary-data path raises. A zero population is a legitimate
    # observation the engine turns into a recorded SkippedAggregation.
    population, description = resolve_whitelisted_api_population([])

    assert population == 0
    assert description.strip() != ""


# -- The description is part of the contract ------------------------------------------------------------


def test_the_returned_description_is_non_empty() -> None:
    # It becomes Pattern.population_description; an empty one would orphan
    # a measured number from what it counted.
    _, description = resolve_whitelisted_api_population(
        [_evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist")]
    )
    assert description.strip() != ""


def test_the_description_states_what_was_counted() -> None:
    _, description = resolve_whitelisted_api_population([])
    assert "distinct symbols" in description
    assert "whitelist" in description


def test_the_description_is_stable_regardless_of_input() -> None:
    # Determinism (SS11): the description describes the population's
    # definition, not the particular records seen.
    _, empty_description = resolve_whitelisted_api_population([])
    _, populated_description = resolve_whitelisted_api_population(
        [_evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist")]
    )
    assert empty_description == populated_description


# -- Determinism -----------------------------------------------------------------------------------------


def test_resolution_is_deterministic_across_repeated_calls() -> None:
    records = [
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.api.get_other", subject="frappe.whitelist"),
    ]

    assert resolve_whitelisted_api_population(records) == resolve_whitelisted_api_population(records)


def test_resolution_does_not_depend_on_record_order() -> None:
    records = [
        _evidence(symbol="erpnext.api.get_data", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.api.get_other", subject="frappe.read_only"),
        _evidence(symbol="erpnext.api.get_other", subject="frappe.whitelist"),
    ]

    assert resolve_whitelisted_api_population(records) == resolve_whitelisted_api_population(
        list(reversed(records))
    )


# -- Registry synchronization with the Capability Matrix (Commit 3) -----------------------------------


def test_every_aggregated_matrix_entry_has_a_resolver() -> None:
    # A category declared aggregatable with no way to compute its
    # denominator would be a promise the engine cannot keep.
    for basis in POPULATION_BASES:
        if basis.status is AggregationStatus.AGGREGATED:
            assert basis.evidence_category in POPULATION_RESOLVERS, basis.evidence_category


def test_no_skipped_matrix_entry_has_a_resolver() -> None:
    # The inverse: a resolver for a category the matrix says cannot be
    # measured would let the engine bypass its own declared limits.
    for basis in POPULATION_BASES:
        if basis.status is AggregationStatus.SKIPPED_NO_POPULATION:
            assert basis.evidence_category not in POPULATION_RESOLVERS, basis.evidence_category


def test_every_resolver_corresponds_to_a_registered_matrix_entry() -> None:
    # No resolver may exist for a category absent from the matrix
    # entirely -- that would be computation with no declaration behind it.
    registered = {basis.evidence_category for basis in POPULATION_BASES}
    assert set(POPULATION_RESOLVERS) <= registered


def test_the_resolver_table_contains_exactly_the_aggregated_categories() -> None:
    aggregated = {
        basis.evidence_category for basis in POPULATION_BASES if basis.status is AggregationStatus.AGGREGATED
    }
    assert set(POPULATION_RESOLVERS) == aggregated


def test_the_whitelisted_api_resolver_is_the_registered_one() -> None:
    assert (
        POPULATION_RESOLVERS[EvidenceCategory.WHITELISTED_API_DECORATION]
        is resolve_whitelisted_api_population
    )


def test_every_registered_resolver_is_callable() -> None:
    assert all(callable(resolver) for resolver in POPULATION_RESOLVERS.values())
