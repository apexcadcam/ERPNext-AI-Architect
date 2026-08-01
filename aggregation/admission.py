"""The repository admission registry, as an executable registry.

Implements [ADR-0017](../adr/ADR-0017-canonical-repository-admission.md).
This module is **pure declaration plus one lookup**: it states, per
canonical repository, which supporting corpora that repository's measured
populations require, and refuses an aggregation that supplies fewer. It
resolves nothing, counts nothing, and measures nothing.

**The problem it exists to prevent, stated once.** A repository can be
fully parseable and still not be safely measurable. RQ-0004 measured
HRMS in four configurations: the collectors ran clean on all 613 files
in every one, and the lifecycle population came out 143, 145, 150 or
153 depending purely on which corpora were supplied for inheritance
resolution. Only the last is correct. Under the other three, Sprint 22's
occurrence filter drops real controllers from the numerator and publishes
a lower, plausible, **wrong** support figure rather than raising -- so
the failure is silent, and a convention that must be remembered protects
nothing when forgetting it produces a number instead of an error.

The same is already true of `erpnext`, which resolves 492 alone where the
true figure is 510 (RQ-0002 F6). That was a documented caution; it is now
a refusal.

**Why a new module rather than an existing registry.** Every registry
this package already has -- `POPULATION_BASES`, `POPULATION_RESOLVERS`,
`OCCURRENCE_FILTERS`, `STRUCTURAL_CATEGORIES` -- is keyed by
`EvidenceCategory` or is a scalar. None is keyed by repository, plugin
manifests describe modules rather than repositories, `runtime/config` is
domain-agnostic by `RUNTIME_ARCHITECTURE.md §1`, and
`CanonicalRepository` carries identity only. There was no owner, so
ADR-0017 §4 authorised one -- **modelled on the Capability Matrix rather
than invented**: `aggregation.population` declares, per category, what
that category's measurement requires; this declares, per repository, what
*its* measurement requires. `get_repository_admission` is the exact
counterpart of `get_population_basis`, default-deny included.

**This is not a repository plugin system.** No lifecycle, no discovery,
no capabilities, no code per repository, and no version -- the corpus
that satisfies a requirement on a given run is recorded in
`ResolutionProvenance`, not fixed here.

**No engine gains a repository-specific branch** (ADR-0017 §4). The
closure is *data* in this module; every consumer performs a generic
lookup. `tests/aggregation/test_architecture_boundaries.py` asserts that
no other file under `aggregation/` so much as names a
`CanonicalRepository` member, so `if repository is CanonicalRepository.X`
cannot reappear inside the engine.
"""

from __future__ import annotations

from evidence.contract import CanonicalRepository

from aggregation.contract import RepositoryAdmission
from aggregation.errors import AggregationError_

#: ADR-0017's admission registry, verbatim.
#:
#: Ordered by `CanonicalRepository` declaration order for stable
#: iteration, matching `POPULATION_BASES`. A repository absent from this
#: tuple is **not admitted** -- see `get_repository_admission`'s
#: default-deny contract below.
#:
#: Every closure here was established by *measuring the ancestry graph*,
#: never by reading `required_apps` or an import list. ADR-0017 rejected
#: inferring closure from packaging metadata as unproven: metadata is a
#: declaration about installation, not a statement about which classes a
#: population needs.
REPOSITORY_ADMISSIONS: tuple[RepositoryAdmission, ...] = (
    RepositoryAdmission(
        repository=CanonicalRepository.FRAPPE,
        required_supporting=frozenset(),
        justification=(
            "frappe defines the population root itself: every class in its controller population "
            "reaches frappe.model.document.Document through frappe-defined bases alone. Its "
            "committed corpus is aggregated with strategy 'single_corpus' and publishes a "
            "275-class population; no supplied corpus changes that number. The empty closure is a "
            "measured result, not an unanswered question."
        ),
        established_by="RQ-0002",
    ),
    RepositoryAdmission(
        repository=CanonicalRepository.ERPNEXT,
        required_supporting=frozenset({CanonicalRepository.FRAPPE}),
        justification=(
            "18 erpnext controllers reach Document only through NestedSet or WebsiteGenerator, "
            "both defined in frappe. Resolved alone, erpnext yields 492 where the true population "
            "is 510 -- a 3.5% undercount that is a wrong number rather than an error, and one "
            "that then filters valid occurrences out of every numerator drawn from it."
        ),
        established_by="RQ-0002 F6",
    ),
    RepositoryAdmission(
        repository=CanonicalRepository.HRMS,
        required_supporting=frozenset({CanonicalRepository.FRAPPE, CanonicalRepository.ERPNEXT}),
        justification=(
            "Both corpora are required for correctness, not for better coverage: neither one "
            "alone resolves the population. Measured across all four configurations, hrms yields "
            "143 controllers alone, 145 with frappe, 150 with erpnext, and 153 with both -- and "
            "the shortfall is not evenly spread, because at least one chain leaves hrms, passes "
            "through an erpnext base, and reaches Document only through a frappe one. Supplying "
            "a single supporting corpus therefore cannot be a partial improvement on the way to "
            "a correct number; it is a different wrong number. Under every incomplete "
            "configuration real hook-bearing controllers -- 6, then 4, then 2 -- fall outside the "
            "population and are silently dropped from the numerator rather than raising."
        ),
        established_by="RQ-0004 F3",
    ),
)


def get_repository_admission(repository: CanonicalRepository) -> RepositoryAdmission | None:
    """Returns the registry row for `repository`, or `None` if it has none.

    **Default-deny, exactly as `get_population_basis` is.** `None` means
    "not admitted" -- never "proceed without a closure". A future
    `CanonicalRepository` member added without a registry entry therefore
    refuses rather than silently measuring itself with no context, which
    is the failure mode ADR-0017 exists to prevent. A conformance test
    asserts every enum member has exactly one entry, so `None` is
    unreachable today; it is kept because the alternative -- assuming an
    empty closure for an unregistered repository -- would make the most
    dangerous case look like the safest one.
    """

    for admission in REPOSITORY_ADMISSIONS:
        if admission.repository is repository:
            return admission
    return None


def missing_required_support(
    repository: CanonicalRepository, supplied: frozenset[CanonicalRepository]
) -> tuple[CanonicalRepository, ...]:
    """Which registered requirements `supplied` does not satisfy, sorted.

    Returns empty when the closure is met, **including when more than the
    closure was supplied**: the registered set is a minimum, so a superset
    satisfies it (ADR-0017 §2). Extra context is permitted, recorded in
    `ResolutionProvenance`, and judged there rather than capped here --
    no artificial maximum is invented.

    Pure, total, and raises nothing, so callers that want to *report* a
    gap rather than refuse one need not catch an exception to do it.
    Sorted by repository value for a deterministic message.

    **An unregistered repository has no *requirements*, which is not the
    same as being admissible.** This function answers only "what does the
    registry demand that is absent", so for a repository the registry does
    not describe the honest answer is "nothing is demanded" -- there is no
    requirement to be missing. Whether the repository may be measured at
    all is a separate question, and `require_supporting_closure` refuses
    it. Splitting the two keeps this one a query rather than a policy, and
    keeps the default-deny decision in exactly one place.
    """

    admission = get_repository_admission(repository)
    if admission is None:
        return ()
    return tuple(sorted(admission.required_supporting - supplied, key=lambda item: item.value))


def require_supporting_closure(
    repository: CanonicalRepository, supplied: frozenset[CanonicalRepository]
) -> None:
    """Refuse to proceed unless `repository`'s registered closure is met.

    **The platform refuses; it never auto-injects** (ADR-0017 §5). A
    caller who omits required context is told exactly what to add and
    re-runs the command. Supplying the corpora automatically was rejected
    because it would make an artifact's inputs implicit, and the entire
    reason `ResolutionProvenance` exists is that 510 and 492 are both
    defensible ERPNext populations distinguishable *only* by what was
    supplied. Convenience is not worth making provenance describe a
    decision the platform took silently.

    **Nothing here consults `unresolved_bases_count`, and that is
    deliberate** (ADR-0017 §6). A residue of unresolved base names is
    normal -- `frappe`'s own is 40 legitimate stdlib and third-party
    bases -- so requiring it to reach zero would disqualify the framework
    itself. The requirement is semantic completeness of the relevant
    population, established by research, not the elimination of every
    unresolved name.

    Raises this package's own `AggregationError_` rather than a
    `ValueError` from a contract validator: an unmet closure is a domain
    refusal about *what may be published*, not a malformed request. The
    request is well-formed; the measurement it asks for is not one this
    platform can make correctly. Callers already catch this type, and the
    CLI already maps it to an exit code.

    Duplicate corpora and self-support are **not** checked here.
    `AggregationRequest` and `resolve_descent` already refuse both, and
    restating a rule in a third place gives it three chances to disagree
    with itself.
    """

    if get_repository_admission(repository) is None:
        raise AggregationError_(
            f"'{repository.value}' has no admission entry; a repository is measurable only once "
            f"its supporting-corpus closure has been established by research (ADR-0017)"
        )

    missing = missing_required_support(repository, supplied)
    if missing:
        names = ", ".join(item.value for item in missing)
        raise AggregationError_(
            f"aggregating '{repository.value}' requires supporting corpora that were not "
            f"supplied: {names}. Its population cannot be resolved completely without them, and "
            f"an incomplete population publishes a plausible wrong number rather than an error "
            f"(ADR-0017). Supply them as resolution context; the platform never adds them for you"
        )
