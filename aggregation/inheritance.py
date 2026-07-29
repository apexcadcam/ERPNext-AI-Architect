"""The Inheritance Resolver -- Inheritance Resolution Specification §4.

**An independent component, not a step inside aggregation.** It answers
exactly one question about a class graph -- *which classes descend from a
named root* -- and knows nothing about Patterns, populations, thresholds,
support, or `AggregationStatus`. It performs no I/O, reads no clock, and
touches no filesystem: given the same records it returns the same result,
which makes it testable without a repository.

**Where the inference lives.** The collectors record raw facts -- "this
class exists", "this class declares this base name, spelled this way".
Nothing in the corpus says a class descends from `Document`. That
judgement is made here, from stored inputs, so it can be recomputed under
a better matching rule without re-extracting a single repository
(ADR-0015).

**Why the result carries measured-corpus classes only.** A supporting
corpus contributes class definitions used to resolve inheritance and
nothing else -- never an occurrence, never population membership, never a
`Pattern` (§5.2). Rather than trusting every future caller to remember
that, `ClassDescentResult.descendants` simply does not contain them: a
downstream consumer cannot count a supporting class into a population
because it is not there to count. The rule is enforced by the shape of
the output instead of by a comment.
"""

from __future__ import annotations

import collections

from pydantic import BaseModel, ConfigDict, Field

from evidence.contract import CanonicalRepository, Evidence, EvidenceCategory, EvidenceSet

from aggregation.errors import AggregationError_


class ClassDescentResult(BaseModel):
    """§4.1's output. A resolved graph, not a measurement.

    Deliberately defined here rather than in `aggregation.contract`: it is
    this component's own return type, never persisted and never part of
    any artifact, and keeping it local is what lets the resolver be
    reasoned about -- and tested -- without reference to the aggregation
    contract at all.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Qualified symbols descending from `root`, **from the measured
    #: corpus only**, sorted. This is the set a population is drawn from.
    descendants: tuple[str, ...] = ()

    #: Base names, as written, matching no class definition in any
    #: supplied corpus -- `object`, `Exception`, a third-party class.
    #: A non-empty residue is normal and expected; it is reported rather
    #: than swallowed so that what was *not* resolved stays visible.
    unresolved_bases: tuple[str, ...] = ()

    #: Longest chain observed, `0` meaning "declares the root directly".
    #: Its consumer is verification: RQ-0002 measured depth 6 in ERPNext,
    #: and a resolver that silently stopped following chains would still
    #: return plausible `descendants` while this collapsed toward 0.
    max_depth: int = Field(default=0, ge=0)


def _final_segment(dotted_name: str) -> str:
    """§4.2 rule 1's one normalising step, and the only inference in this
    module that touches a name's spelling.

    `Document`, `frappe.model.document.Document` and `document.Document`
    all denote the same class and all appear in the real trees. Matching
    on the final segment is what reconciles them. It lives here rather
    than in the collector precisely so that changing it never requires
    re-extracting a corpus.
    """

    return dotted_name.rsplit(".", 1)[-1]


def _records(evidence_set: EvidenceSet, category: EvidenceCategory) -> list[Evidence]:
    return [record for record in evidence_set.evidence if record.category is category]


def _reject_ambiguous_corpora(measured: EvidenceSet, supporting: tuple[EvidenceSet, ...]) -> None:
    """A supporting corpus must be a different repository from the
    subject, and from every other supporting corpus.

    The same checks `AggregationRequest` already performs, repeated here
    because this component has its own entry point and its own callers:
    a precondition enforced only by a sibling type is a precondition that
    holds until someone calls this function directly.
    """

    seen: set[CanonicalRepository] = set()
    for corpus in supporting:
        if corpus.repository is measured.repository:
            raise AggregationError_(
                f"supporting corpus '{corpus.repository.value}' is the measured repository; "
                f"a corpus cannot be its own resolution context"
            )
        if corpus.repository in seen:
            raise AggregationError_(
                f"supporting corpus '{corpus.repository.value}' was supplied more than once; "
                f"descent would be ambiguous"
            )
        seen.add(corpus.repository)


def resolve_descent(
    measured: EvidenceSet,
    supporting: tuple[EvidenceSet, ...] = (),
    *,
    root: str,
) -> ClassDescentResult:
    """Resolve which classes in `measured` descend from `root`, using
    `supporting` corpora as additional graph context.

    Descent is transitive to full depth (§4.2 rule 2). RQ-0002 measured
    chains reaching depth 6 in ERPNext, where a single-level check would
    miss 37 of its 62 transitive controllers.

    Cross-repository resolution is the reason `supporting` exists: 18
    ERPNext controllers reach `Document` only through `NestedSet` or
    `WebsiteGenerator`, both defined in `frappe` (RQ-0002 F6). Resolving
    ERPNext alone yields 492 where the true figure is 510 -- a silent 3.5%
    undercount, which is a wrong number rather than an error.

    Membership in `root` is by **name, not by definition**: a class
    declaring `Document` descends from it whether or not `Document`
    itself was supplied. That matters because measuring ERPNext without
    `frappe` must still resolve its 448 direct subclasses rather than
    collapsing to zero.
    """

    _reject_ambiguous_corpora(measured, supporting)

    corpora = (measured, *supporting)
    root_name = _final_segment(root)

    #: Every class name defined anywhere, so an unmatched base can be told
    #: apart from one that simply resolves elsewhere.
    defined_names: set[str] = set()
    #: Qualified symbols defined by the measured corpus specifically --
    #: the only ones that may ever appear in the result.
    measured_symbols: set[str] = set()
    #: Qualified symbol -> its own bare class name.
    symbol_name: dict[str, str] = {}

    for corpus in corpora:
        for record in _records(corpus, EvidenceCategory.CLASS_DEFINITION):
            defined_names.add(record.subject)
            symbol_name[record.symbol] = record.subject
            if corpus is measured:
                measured_symbols.add(record.symbol)

    #: base name (final segment) -> symbols declaring it. The graph is
    #: walked forward from the root rather than backward from each class:
    #: a breadth-first sweep visits every symbol once, terminates on a
    #: cycle by construction rather than by a recursion guard bolted on
    #: afterwards (§4.2 rule 3), and yields chain depth for free.
    declared_by: dict[str, list[str]] = collections.defaultdict(list)
    unresolved: set[str] = set()

    for corpus in corpora:
        for record in _records(corpus, EvidenceCategory.CLASS_BASE_DECLARATION):
            base = _final_segment(record.subject)
            declared_by[base].append(record.symbol)
            # **Scoped to the measured corpus**, for the same reason
            # `descendants` is: a supporting corpus contributes resolution
            # context and nothing else (§5.2). `frappe`'s own external
            # bases -- `ABC`, `Enum`, `Criterion` -- are not ERPNext's
            # residue, and attributing them to ERPNext would make the
            # diagnostic grow simply because more context was supplied.
            #
            # Resolution still consults every corpus: a name counts as
            # unresolved only when nothing *anywhere* defines it. Only the
            # attribution is narrowed, never the lookup.
            if corpus is not measured:
                continue
            if base != root_name and base not in defined_names:
                unresolved.add(record.subject)

    descendants: dict[str, int] = {}
    frontier = sorted(set(declared_by.get(root_name, ())))
    depth = 0

    while frontier:
        newly_reached: set[str] = set()
        for symbol in frontier:
            descendants[symbol] = depth
            # Anything declaring *this* class as a base descends too.
            name = symbol_name.get(symbol)
            if name is not None:
                newly_reached.update(declared_by.get(name, ()))
        # Subtracting what is already resolved is what makes this
        # terminate, and it is the only cycle guard the algorithm needs:
        # a symbol enters the frontier at most once, so a cycle is walked
        # exactly one lap and then has nothing new to offer. It is also
        # what keeps `descendants[symbol]` the *shortest* chain length,
        # since the first sweep to reach a symbol is the shallowest one.
        frontier = sorted(newly_reached - descendants.keys())
        depth += 1

    resolved_in_measured = sorted(symbol for symbol in descendants if symbol in measured_symbols)

    return ClassDescentResult(
        descendants=tuple(resolved_in_measured),
        unresolved_bases=tuple(sorted(unresolved)),
        max_depth=max(descendants.values(), default=0),
    )
