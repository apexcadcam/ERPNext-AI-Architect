"""Conformance tests for `aggregation.population` (Pattern Aggregation Engine
Architecture Specification v1.0 §2, §7.2, §8).

This is a **conformance suite**, not a behavioral one: it asserts that the
executable registry says exactly what the specification's Aggregation
Capability Matrix says. A failure here means the matrix and the code have
drifted apart -- never that a denominator was computed wrongly, since this
module computes nothing.
"""

from __future__ import annotations

from evidence.contract import EvidenceCategory

from aggregation.contract import AggregationStatus, PopulationBasis
from aggregation.population import POPULATION_BASES, get_population_basis

# -- Matrix conformance: the registry matches §2 exactly ---------------------------------------------


def test_registry_covers_exactly_the_categories_the_matrix_lists() -> None:
    # SS2 lists two rows. No more (a category aggregated without being
    # specified), no fewer (a category silently absent).
    assert {basis.evidence_category for basis in POPULATION_BASES} == {
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        EvidenceCategory.WHITELISTED_API_DECORATION,
    }


#: Categories that are structural input to inheritance resolution rather
#: than signals to be measured (Sprint 22). "What share of class
#: definitions are class definitions" is not a question, so these have no
#: row in the Capability Matrix -- their absence is a statement, not a
#: gap, and the test below asserts it rather than tolerating it.
_STRUCTURAL_CATEGORIES = frozenset(
    {EvidenceCategory.CLASS_DEFINITION, EvidenceCategory.CLASS_BASE_DECLARATION}
)


def test_registry_covers_every_measurable_signal_category() -> None:
    # Every category that *is* a signal must appear in the matrix with an
    # explicit verdict. A signal category existing in the Evidence
    # contract but absent here would be an undeclared gap -- which is the
    # guard this test exists to provide, and which still holds.
    signal_categories = set(EvidenceCategory) - _STRUCTURAL_CATEGORIES
    assert {basis.evidence_category for basis in POPULATION_BASES} == signal_categories


def test_the_structural_categories_are_deliberately_absent_from_the_matrix() -> None:
    # Asserted explicitly so that adding a matrix row for one of them --
    # which would mean the engine had begun trying to compute support over
    # class definitions -- fails loudly instead of passing quietly.
    matrix_categories = {basis.evidence_category for basis in POPULATION_BASES}
    assert matrix_categories & _STRUCTURAL_CATEGORIES == set()
    for category in _STRUCTURAL_CATEGORIES:
        assert get_population_basis(category) is None


def test_registry_has_no_duplicate_categories() -> None:
    categories = [basis.evidence_category for basis in POPULATION_BASES]
    assert len(categories) == len(set(categories))


def test_whitelisted_api_decoration_is_aggregated_with_no_blocker() -> None:
    basis = get_population_basis(EvidenceCategory.WHITELISTED_API_DECORATION)
    assert basis is not None
    assert basis.status is AggregationStatus.AGGREGATED
    assert basis.blocker is None


def test_controller_lifecycle_hook_is_now_aggregated_with_no_blocker() -> None:
    # Sprint 22 closed the gap this row declared from v1.2.0 to v1.3.0.
    # The blocker is *removed* rather than edited, because there is no
    # longer anything blocking: the denominator is derivable.
    basis = get_population_basis(EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK)
    assert basis is not None
    assert basis.status is AggregationStatus.AGGREGATED
    assert basis.blocker is None


def test_the_lifecycle_hook_population_names_what_it_counts() -> None:
    # A measured number must never be orphaned from its meaning: the
    # description travels onto Pattern.population_description, so a reader
    # of a support figure can see what the denominator was.
    basis = get_population_basis(EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK)
    assert basis is not None
    assert "Document" in basis.description
    assert "transitively" in basis.description


# -- Structural invariants: hold for every future row, not just today's two --------------------------


def test_every_aggregated_entry_has_no_blocker() -> None:
    # A category declared aggregatable cannot simultaneously be blocked.
    for basis in POPULATION_BASES:
        if basis.status is AggregationStatus.AGGREGATED:
            assert basis.blocker is None, basis.evidence_category


def test_every_skipped_entry_has_a_non_empty_blocker() -> None:
    # A skip without a stated cause is exactly the silent gap SS9 exists to
    # prevent.
    for basis in POPULATION_BASES:
        if basis.status is AggregationStatus.SKIPPED_NO_POPULATION:
            assert basis.blocker is not None, basis.evidence_category
            assert basis.blocker.strip() != "", basis.evidence_category


def test_every_entry_has_a_non_empty_description() -> None:
    # The description becomes Pattern.population_description, so an empty
    # one would orphan a measured number from what it counted.
    for basis in POPULATION_BASES:
        assert basis.description.strip() != "", basis.evidence_category


def test_every_entry_is_a_population_basis_instance() -> None:
    assert all(isinstance(basis, PopulationBasis) for basis in POPULATION_BASES)


def test_every_entry_status_is_a_known_aggregation_status() -> None:
    # Guards against a raw string sneaking in past the enum.
    assert all(basis.status in set(AggregationStatus) for basis in POPULATION_BASES)


# -- Lookup contract, including default-deny (§8) ------------------------------------------------------


def test_get_population_basis_returns_the_matching_row() -> None:
    basis = get_population_basis(EvidenceCategory.WHITELISTED_API_DECORATION)
    assert basis is not None
    assert basis.evidence_category is EvidenceCategory.WHITELISTED_API_DECORATION


def test_get_population_basis_returns_a_row_for_every_registered_category() -> None:
    for basis in POPULATION_BASES:
        assert get_population_basis(basis.evidence_category) is basis


def test_get_population_basis_returns_none_for_an_unregistered_category() -> None:
    # SS8's default-deny. Simulated with a stand-in that is not in the
    # registry, since every real category currently is -- this proves the
    # behavior that protects a *future* category added without a matrix
    # entry: it degrades to a recorded skip, never a fabricated denominator.
    class _UnregisteredCategory:
        pass

    assert get_population_basis(_UnregisteredCategory()) is None  # type: ignore[arg-type]


def test_get_population_basis_does_not_raise_for_an_unregistered_category() -> None:
    # SS10: no ordinary-data path raises. The engine must be able to record
    # the skip as a result rather than aborting the whole run.
    class _UnregisteredCategory:
        pass

    result = get_population_basis(_UnregisteredCategory())  # type: ignore[arg-type]
    assert result is None


# -- The registry is data only: no computation lives here ---------------------------------------------


def test_population_module_defines_no_resolver_or_arithmetic() -> None:
    # Commit 3 is declaration only; resolvers are Commit 4's own scope.
    # Asserted structurally so the boundary cannot erode silently.
    #
    # Filtered by __module__ so imported names (AggregationStatus,
    # PopulationBasis, EvidenceCategory -- all classes, all callable) are
    # not mistaken for functions this module defines.
    import aggregation.population as population_module

    defined_here = [
        name
        for name in dir(population_module)
        if not name.startswith("_")
        and callable(getattr(population_module, name))
        and getattr(getattr(population_module, name), "__module__", None) == "aggregation.population"
    ]
    assert defined_here == ["get_population_basis"]
