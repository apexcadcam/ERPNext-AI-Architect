"""Population resolvers -- the computation the Capability Matrix declares
possible.

Implements Pattern Aggregation Engine Architecture Specification v1.0 §8.
One pure function per Evidence category the matrix marks `AGGREGATED`,
each returning `(population, description)`. `aggregation.population`
declares *what is possible*; this module computes *what is true*.

**Distinct symbols, never records.** This is the single most important
rule in the module. A function carrying `@frappe.whitelist()` plus two
other decorators produces three Evidence records but is **one** member of
the population. Counting records instead of symbols would inflate every
denominator and silently deflate every `support` -- the exact failure
this engine exists to avoid.

That this is even computable cheaply is a direct consequence of Sprint
20's atomic-Evidence decision: because decorators were never bundled into
a combined `subject`, each record names exactly one decorator against one
`symbol`, so distinct-symbol counting is a set operation rather than a
parse.

No arithmetic beyond counting lives here. Grouping, thresholds, ratios,
and skip decisions are `aggregation.engine`'s own scope (Commit 5).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from evidence.contract import Evidence, EvidenceCategory, EvidenceSet

from aggregation.inheritance import ClassDescentResult

#: The subjects that mark a symbol as a member of the whitelisted-API
#: population. Both forms occur in the real canonical reference:
#: `frappe.whitelist` is the common attribute call, and bare `whitelist`
#: appears where the name is imported directly -- confirmed twice in real
#: frappe v15.103.1 (e.g. `frappe/__init__.py`'s own `rename_doc`).
#:
#: Membership is defined by carrying one of these, so a record whose
#: subject is any *other* decorator (`frappe.read_only`, `rate_limit`,
#: `staticmethod`, ...) does not by itself put a symbol in the
#: population -- it only counts toward a `Pattern`'s numerator once the
#: symbol is already a member.
WHITELIST_FAMILY_SUBJECTS: frozenset[str] = frozenset({"frappe.whitelist", "whitelist"})

_WHITELISTED_API_POPULATION_DESCRIPTION = (
    "distinct symbols carrying a whitelist-family decorator (frappe.whitelist or whitelist)"
)

#: The root of the controller population: every Frappe DocType controller
#: is a `Document` subclass, directly or through any number of
#: intermediate bases. Registered here rather than inlined in the engine
#: so that the one framework-specific name in the aggregation package
#: sits beside the resolver that uses it, and the engine stays free of
#: repository-specific knowledge.
CONTROLLER_POPULATION_ROOT = "Document"

_CONTROLLER_POPULATION_DESCRIPTION = (
    "distinct classes descending from frappe.model.document.Document, resolved transitively"
)


@dataclass(frozen=True)
class PopulationContext:
    """Everything a resolver may need beyond its own category's records.

    Introduced because the controller population is not derivable from
    the lifecycle-hook records alone -- it is a property of the class
    graph, which those records do not describe. The whitelist resolver
    ignores it entirely, which is the point: a resolver takes what it
    needs and no more.

    `descent` is resolved **once per request, by the engine**, and shared.
    Resolving it here instead would mean each resolver rebuilding the same
    graph, and -- worse -- the population reported in a `Pattern` and the
    residue reported in `ResolutionProvenance` coming from two separate
    computations that could disagree.
    """

    measured: EvidenceSet
    supporting: tuple[EvidenceSet, ...]
    descent: ClassDescentResult


#: A resolver takes the records of one Evidence category, plus the shared
#: context, and returns that category's population with a human-readable
#: description of what was counted. The description travels onto
#: `Pattern.population_description` so a measured number is never orphaned
#: from its meaning.
Resolver = Callable[[Sequence[Evidence], PopulationContext], tuple[int, str]]


def resolve_whitelisted_api_population(
    records: Sequence[Evidence], context: PopulationContext
) -> tuple[int, str]:
    """§8's resolver for `WHITELISTED_API_DECORATION`.

    Counts **distinct `symbol`s** among records whose `subject` is a
    whitelist-family marker -- carrying one is exactly what makes a
    function part of this population.

    Returns `(0, description)` for empty or wholly non-whitelist input
    rather than raising: a zero population is a legitimate observation
    that the engine turns into a recorded `SkippedAggregation` (§10), and
    `Pattern.population`'s own `ge=1` constraint makes it impossible for
    that zero to reach a published measurement.
    """

    symbols = {record.symbol for record in records if record.subject in WHITELIST_FAMILY_SUBJECTS}
    return len(symbols), _WHITELISTED_API_POPULATION_DESCRIPTION


def resolve_controller_lifecycle_hook_population(
    records: Sequence[Evidence], context: PopulationContext
) -> tuple[int, str]:
    """The population Sprint 22 exists to supply.

    **Ignores `records` entirely, and that is the whole point.** The
    lifecycle-hook records are the numerator: they exist only where a
    hook was found, so counting them would count classes that *have* a
    hook, not classes that *could*. The denominator lives in the class
    graph, which `context.descent` has already resolved -- measured-corpus
    classes only, so a supporting corpus can complete a chain without
    joining the population it completes (Inheritance Resolution §5.2).

    This is exactly the gap that made the category unmeasurable through
    `v1.3.0`: the numerator existed and the denominator did not.
    """

    return len(context.descent.descendants), _CONTROLLER_POPULATION_DESCRIPTION


#: §8's dispatch table. Must stay synchronized with
#: `aggregation.population.POPULATION_BASES`: every category the matrix
#: marks `AGGREGATED` needs a resolver here, and no category it marks
#: `SKIPPED_*` may have one. `tests/aggregation/test_resolvers.py`
#: cross-checks both directions against the registry, so the two cannot
#: drift apart.
POPULATION_RESOLVERS: dict[EvidenceCategory, Resolver] = {
    EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK: resolve_controller_lifecycle_hook_population,
    EvidenceCategory.WHITELISTED_API_DECORATION: resolve_whitelisted_api_population,
}
