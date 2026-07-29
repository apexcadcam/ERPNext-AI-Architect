"""The Aggregation Capability Matrix, as an executable registry.

Implements Pattern Aggregation Engine Architecture Specification v1.0 §2
and §7.2. This module is **pure declaration**: it states, per Evidence
category, whether a valid population (denominator) can be derived from
persisted Evidence alone, and if not, precisely what blocks it. It
computes nothing -- population arithmetic lives in
`aggregation.resolvers`, and aggregation itself in `aggregation.engine`.

That separation is deliberate. A failure in this module can only ever
mean "the registry disagrees with the specification"; it can never mean
"the denominator was computed wrongly". Keeping the two apart is why
`tests/aggregation/test_population_matrix.py` is a conformance suite
rather than a behavioral one.

**The matrix is the source of truth, not the prose.** §2 of the
specification and `POPULATION_BASES` below must agree, and a test
asserts exactly that -- so the document cannot quietly drift away from
the code, in either direction.

The same Rule Metadata Registry pattern
`evaluation.rules.RULE_THRESHOLDS` and
`recommendation.scoring.PRIORITY_WEIGHTS` already established, applied
here to capability rather than to numeric thresholds.
"""

from __future__ import annotations

from evidence.contract import EvidenceCategory

from aggregation.contract import AggregationStatus, PopulationBasis

#: Evidence categories that are **topology, not signal**.
#:
#: `CLASS_DEFINITION` and `CLASS_BASE_DECLARATION` describe the shape of
#: the class graph. They exist so that a population can be *resolved*
#: (Inheritance Resolution §2); they are not observations anyone measures
#: a share of. "What fraction of class definitions are class definitions"
#: is not a question, so these categories have no row in the Capability
#: Matrix -- and, unlike a category whose denominator is merely missing,
#: their absence is a statement rather than a gap.
#:
#: The engine therefore excludes them from aggregation entirely: they are
#: neither measured nor reported as skipped. Letting them fall through to
#: the matrix's default-deny would file them as "we could not measure
#: this", which is the wrong claim -- nobody tried, because there is
#: nothing there to measure.
STRUCTURAL_CATEGORIES: frozenset[EvidenceCategory] = frozenset(
    {EvidenceCategory.CLASS_DEFINITION, EvidenceCategory.CLASS_BASE_DECLARATION}
)

#: §2's Aggregation Capability Matrix, verbatim.
#:
#: Ordered by `EvidenceCategory` declaration order for stable iteration.
#: A category absent from this tuple is *not* aggregatable -- see
#: `get_population_basis`'s default-deny contract below.
POPULATION_BASES: tuple[PopulationBasis, ...] = (
    PopulationBasis(
        evidence_category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        status=AggregationStatus.AGGREGATED,
        description=(
            "Distinct classes descending from frappe.model.document.Document, resolved "
            "transitively across the measured corpus and any supporting corpora -- the set a "
            "lifecycle hook could possibly appear on."
        ),
    ),
    PopulationBasis(
        evidence_category=EvidenceCategory.WHITELISTED_API_DECORATION,
        status=AggregationStatus.AGGREGATED,
        description=(
            "Distinct symbols carrying a whitelist-family subject (frappe.whitelist or bare "
            "whitelist) -- every whitelisted function emits at least one such record by "
            "construction, so the population is complete within the Evidence itself."
        ),
        blocker=None,
    ),
)


def get_population_basis(category: EvidenceCategory) -> PopulationBasis | None:
    """Returns the matrix row for `category`, or `None` if the category is
    not registered.

    **Default-deny (§8).** `None` means "not aggregatable" -- never "try
    anyway". A future Evidence category added without a corresponding
    matrix entry therefore degrades to a recorded `SkippedAggregation`
    rather than silently producing a wrong denominator. Returning `None`
    rather than raising is what lets the engine record the skip as a
    result instead of aborting the run (§10).
    """

    for basis in POPULATION_BASES:
        if basis.evidence_category is category:
            return basis
    return None
