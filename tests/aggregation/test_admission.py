"""Tests for `aggregation.admission` -- the repository admission registry
and its enforcement (ADR-0017).

**What these tests are really protecting.** RQ-0004 measured a repository
that parsed cleanly in four configurations and produced four different
populations, only one of which was correct. The wrong ones did not raise;
they published a smaller, plausible denominator. So the assertions here
are deliberately about *refusal before publication*, not about a
`PatternSet` that turned out wrong afterwards -- by the time an artifact
exists to inspect, the failure this registry exists to prevent has
already happened.
"""

from __future__ import annotations

import pytest

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

from aggregation import admission
from aggregation.admission import (
    REPOSITORY_ADMISSIONS,
    get_repository_admission,
    missing_required_support,
    require_supporting_closure,
)
from aggregation.contract import AggregationRequest, RepositoryAdmission
from aggregation.engine import aggregate_patterns
from aggregation.errors import AggregationError_

_COMMIT = "1d14ba16398db3a220873509565c60f2932bed81"


# -- Fixture builders --------------------------------------------------------------------------------


def _class_records(name: str, base: str, *, repository: CanonicalRepository) -> list[Evidence]:
    """A class definition plus one base declaration, the pair the resolver
    needs to place a class in the graph.
    """

    module = f"{repository.value}.mod"
    return [
        Evidence(
            evidence_id=f"def|{module}.{name}".ljust(64, "0")[:64],
            kind=EvidenceKind.IMPLEMENTATION,
            category=EvidenceCategory.CLASS_DEFINITION,
            symbol=f"{module}.{name}",
            subject=name,
            source=Source(
                repository=repository,
                version="v1",
                commit=_COMMIT,
                relative_path=f"{repository.value}/mod.py",
                line=1,
            ),
            collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
            collected_at="2026-08-01T12:00:00+00:00",
        ),
        Evidence(
            evidence_id=f"base|{module}.{name}|{base}".ljust(64, "0")[:64],
            kind=EvidenceKind.IMPLEMENTATION,
            category=EvidenceCategory.CLASS_BASE_DECLARATION,
            symbol=f"{module}.{name}",
            subject=base,
            source=Source(
                repository=repository,
                version="v1",
                commit=_COMMIT,
                relative_path=f"{repository.value}/mod.py",
                line=1,
            ),
            collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
            collected_at="2026-08-01T12:00:00+00:00",
        ),
    ]


def _hook(class_name: str, hook: str, *, repository: CanonicalRepository) -> Evidence:
    module = f"{repository.value}.mod"
    return Evidence(
        evidence_id=f"hook|{module}.{class_name}.{hook}".ljust(64, "0")[:64],
        kind=EvidenceKind.IMPLEMENTATION,
        category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        symbol=f"{module}.{class_name}.{hook}",
        subject=hook,
        source=Source(
            repository=repository,
            version="v1",
            commit=_COMMIT,
            relative_path=f"{repository.value}/mod.py",
            line=1,
        ),
        collector=CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR,
        collected_at="2026-08-01T12:00:00+00:00",
    )


def _corpus(repository: CanonicalRepository, *records: Evidence) -> EvidenceSet:
    return EvidenceSet(
        evidence_set_id=f"evset-{repository.value}",
        schema_version="2.0",
        repository=repository,
        version="v1",
        commit=_COMMIT,
        extracted_at="2026-08-01T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=records,
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=len(records)
        ),
    )


def _erpnext_corpus() -> EvidenceSet:
    return _corpus(
        CanonicalRepository.ERPNEXT,
        *_class_records("Account", "Document", repository=CanonicalRepository.ERPNEXT),
        _hook("Account", "validate", repository=CanonicalRepository.ERPNEXT),
    )


def _frappe_corpus() -> EvidenceSet:
    return _corpus(
        CanonicalRepository.FRAPPE,
        *_class_records("NestedSet", "Document", repository=CanonicalRepository.FRAPPE),
    )


def _request(measured: EvidenceSet, *supporting: EvidenceSet) -> AggregationRequest:
    return AggregationRequest(
        evidence_set=measured,
        supporting_evidence_sets=supporting,
        min_occurrences=1,
        correlation_id="corr-1",
        requested_by="test-suite",
    )


# -- Registry completeness ---------------------------------------------------------------------------


def test_every_canonical_repository_has_exactly_one_admission_entry() -> None:
    """The invariant that makes admission safe to add to incrementally.

    A `CanonicalRepository` member without an entry is a repository the
    platform believes it may measure while nothing says what its
    measurement requires -- which is precisely the state ADR-0017 exists
    to forbid, and precisely the state a commit that added an enum member
    before its closure would create. Asserted here so that ordering
    mistake fails at the registry rather than in a published artifact.
    """

    registered = [entry.repository for entry in REPOSITORY_ADMISSIONS]
    assert sorted(item.value for item in registered) == sorted(member.value for member in CanonicalRepository)
    assert len(registered) == len(set(registered)), "a repository is registered more than once"


def test_no_registered_closure_contains_its_own_repository() -> None:
    for entry in REPOSITORY_ADMISSIONS:
        assert entry.repository not in entry.required_supporting


def test_every_registered_closure_names_only_canonical_repositories() -> None:
    for entry in REPOSITORY_ADMISSIONS:
        for required in entry.required_supporting:
            assert isinstance(required, CanonicalRepository)


def test_every_entry_cites_the_research_that_established_it() -> None:
    # ADR-0017 §9: every admitted repository costs a research question.
    # An entry with no citation makes that cost notional.
    for entry in REPOSITORY_ADMISSIONS:
        assert entry.established_by.startswith("RQ-")
        assert len(entry.justification) > 40


def test_the_registry_is_ordered_by_enum_declaration_order() -> None:
    # Matches `POPULATION_BASES`, so iteration order is stable and a
    # reader can find an entry where they expect it.
    declaration_order = [member.value for member in CanonicalRepository]
    registered_order = [entry.repository.value for entry in REPOSITORY_ADMISSIONS]
    assert registered_order == [name for name in declaration_order if name in registered_order]


# -- The two registered closures ---------------------------------------------------------------------


def test_frappe_has_an_empty_closure() -> None:
    entry = get_repository_admission(CanonicalRepository.FRAPPE)
    assert entry is not None
    assert entry.required_supporting == frozenset()


def test_erpnext_requires_frappe() -> None:
    entry = get_repository_admission(CanonicalRepository.ERPNEXT)
    assert entry is not None
    assert entry.required_supporting == frozenset({CanonicalRepository.FRAPPE})


def test_the_lookup_is_generic_rather_than_a_branch() -> None:
    # Every member resolves through the same call, exactly as
    # `get_population_basis` does. No repository is special-cased.
    for member in CanonicalRepository:
        assert get_repository_admission(member) is not None


def test_an_unregistered_repository_is_denied_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default-deny, the same contract `get_population_basis` has.

    Unreachable while the completeness test above passes, which is why it
    is forced here: the dangerous reading of a missing entry is "no
    requirements", and that would make an unresearched repository look
    like the safest one in the registry.
    """

    monkeypatch.setattr(admission, "REPOSITORY_ADMISSIONS", ())

    assert get_repository_admission(CanonicalRepository.FRAPPE) is None
    with pytest.raises(AggregationError_, match="no admission entry"):
        require_supporting_closure(CanonicalRepository.FRAPPE, frozenset())


def test_an_unregistered_repository_has_no_requirements_to_be_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The query and the policy answer different questions, deliberately.

    `missing_required_support` reports what the registry demands and does
    not have; an unregistered repository demands nothing, so the honest
    answer is empty. That must never be mistaken for "admissible" --
    `require_supporting_closure` is the one place default-deny lives, and
    the test above proves it refuses the same repository.
    """

    monkeypatch.setattr(admission, "REPOSITORY_ADMISSIONS", ())

    assert missing_required_support(CanonicalRepository.ERPNEXT, frozenset()) == ()


# -- missing_required_support: exact, partial, extra, empty -------------------------------------------


def test_an_empty_closure_is_satisfied_by_nothing_at_all() -> None:
    assert missing_required_support(CanonicalRepository.FRAPPE, frozenset()) == ()


def test_an_exact_closure_is_satisfied() -> None:
    supplied = frozenset({CanonicalRepository.FRAPPE})
    assert missing_required_support(CanonicalRepository.ERPNEXT, supplied) == ()


def test_a_missing_closure_reports_precisely_what_is_absent() -> None:
    assert missing_required_support(CanonicalRepository.ERPNEXT, frozenset()) == (CanonicalRepository.FRAPPE,)


def test_extra_context_beyond_the_closure_is_not_a_gap() -> None:
    # The registered closure is a minimum, never a maximum (ADR-0017 §2).
    supplied = frozenset({CanonicalRepository.ERPNEXT})
    assert missing_required_support(CanonicalRepository.FRAPPE, supplied) == ()


def test_missing_support_is_reported_deterministically() -> None:
    # Sorted by repository value, so an error message is reproducible and
    # a test can assert on it without ordering luck.
    assert missing_required_support(CanonicalRepository.ERPNEXT, frozenset()) == tuple(
        sorted(missing_required_support(CanonicalRepository.ERPNEXT, frozenset()), key=lambda r: r.value)
    )


# -- require_supporting_closure ------------------------------------------------------------------------


def test_frappe_alone_is_accepted() -> None:
    require_supporting_closure(CanonicalRepository.FRAPPE, frozenset())


def test_frappe_with_extra_context_is_accepted() -> None:
    require_supporting_closure(CanonicalRepository.FRAPPE, frozenset({CanonicalRepository.ERPNEXT}))


def test_erpnext_with_frappe_is_accepted() -> None:
    require_supporting_closure(CanonicalRepository.ERPNEXT, frozenset({CanonicalRepository.FRAPPE}))


def test_erpnext_alone_is_refused() -> None:
    with pytest.raises(AggregationError_) as raised:
        require_supporting_closure(CanonicalRepository.ERPNEXT, frozenset())

    assert "erpnext" in str(raised.value)


def test_the_refusal_names_the_missing_repository() -> None:
    # Not merely "some exception was raised": a caller has to know what to
    # add, and ADR-0017 §5 makes naming it the platform's obligation --
    # the platform refuses, and never supplies the corpus itself.
    with pytest.raises(AggregationError_) as raised:
        require_supporting_closure(CanonicalRepository.ERPNEXT, frozenset())

    message = str(raised.value)
    assert "frappe" in message
    assert "never adds them for you" in message


def test_the_refusal_is_this_packages_own_error_type() -> None:
    # A domain refusal about what may be published, not a malformed
    # request -- so it is not a pydantic ValidationError, and callers that
    # already catch AggregationError_ need no new except clause.
    with pytest.raises(AggregationError_):
        require_supporting_closure(CanonicalRepository.ERPNEXT, frozenset())


def test_admission_cannot_consult_unresolved_bases_even_by_accident() -> None:
    """ADR-0017 §6 rejects `unresolved_bases_count == 0` as an admission
    rule -- `frappe`'s own residue is 40 legitimate stdlib and third-party
    bases, so a zero rule would disqualify the framework itself.

    Asserted structurally rather than by reading the code: this module
    imports nothing from `aggregation.inheritance`, and both public
    functions take a repository and a set of repository names and nothing
    else. There is no descent result in scope to inspect, so the rejected
    rule is unwritable here rather than merely unwritten.
    """

    import ast
    import inspect
    from pathlib import Path

    imported = {
        node.module
        for node in ast.walk(ast.parse(Path(inspect.getfile(admission)).read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "aggregation.inheritance" not in imported

    for function in (require_supporting_closure, missing_required_support):
        assert list(inspect.signature(function).parameters) == ["repository", "supplied"]


# -- Enforcement inside the engine, before anything is published ---------------------------------------


def test_aggregating_erpnext_without_frappe_is_refused() -> None:
    with pytest.raises(AggregationError_) as raised:
        aggregate_patterns(_request(_erpnext_corpus()))

    assert "frappe" in str(raised.value)


def test_aggregating_erpnext_with_frappe_succeeds() -> None:
    result = aggregate_patterns(_request(_erpnext_corpus(), _frappe_corpus()))

    assert result.repository is CanonicalRepository.ERPNEXT
    assert result.resolution_provenance is not None
    assert [ref.repository for ref in result.resolution_provenance.supporting_corpora] == [
        CanonicalRepository.FRAPPE
    ]


def test_aggregating_frappe_alone_succeeds() -> None:
    frappe = _corpus(
        CanonicalRepository.FRAPPE,
        *_class_records("NestedSet", "Document", repository=CanonicalRepository.FRAPPE),
        _hook("NestedSet", "validate", repository=CanonicalRepository.FRAPPE),
    )
    result = aggregate_patterns(_request(frappe))

    assert result.repository is CanonicalRepository.FRAPPE


def test_the_refusal_happens_before_any_resolution_is_attempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The assertion that makes 492 unpublishable rather than merely wrong.

    A check that ran *after* resolution would still raise, but a
    `ClassDescentResult` built from an incomplete corpus would already
    exist, and every later refactor would be free to log it, cache it, or
    return it. Replacing `resolve_descent` with a function that fails on
    sight proves the engine never reaches it.
    """

    def _must_not_be_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("resolve_descent ran despite an unmet supporting-corpus closure")

    monkeypatch.setattr("aggregation.engine.resolve_descent", _must_not_be_called)

    with pytest.raises(AggregationError_, match="requires supporting corpora"):
        aggregate_patterns(_request(_erpnext_corpus()))


def test_nothing_is_published_when_admission_refuses() -> None:
    # `aggregate_patterns` is the only place a `PatternSet` is constructed,
    # so a refusal here means no artifact exists to be persisted, reported
    # or read back.
    with pytest.raises(AggregationError_):
        aggregate_patterns(_request(_erpnext_corpus()))


# -- The two rules admission deliberately does not restate ---------------------------------------------


def test_self_support_is_still_refused_by_the_existing_validator() -> None:
    # ADR-0017 §5 marks this "existing, not restated". Restating it in the
    # registry would give one rule two places to disagree with itself.
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="it is the subject"):
        _request(_erpnext_corpus(), _erpnext_corpus())


def test_a_duplicate_supporting_repository_is_still_refused_by_the_existing_validator() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="more than once"):
        _request(_erpnext_corpus(), _frappe_corpus(), _frappe_corpus())


def test_admission_itself_checks_neither_duplicates_nor_self_support() -> None:
    # Supplying the measured repository as its own support cannot reach
    # this function -- the request refuses first -- so admission treats the
    # supplied set as given and only asks whether the closure is met.
    require_supporting_closure(
        CanonicalRepository.ERPNEXT,
        frozenset({CanonicalRepository.FRAPPE, CanonicalRepository.ERPNEXT}),
    )


# -- Contract shape ------------------------------------------------------------------------------------


def test_a_repository_admission_is_frozen() -> None:
    entry = REPOSITORY_ADMISSIONS[0]
    with pytest.raises(ValueError):
        entry.repository = CanonicalRepository.ERPNEXT


def test_a_repository_admission_forbids_unknown_fields() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RepositoryAdmission(
            repository=CanonicalRepository.FRAPPE,
            required_supporting=frozenset(),
            justification="j",
            established_by="RQ-0002",
            repository_role="framework",  # type: ignore[call-arg]
        )


def test_a_repository_may_not_require_itself() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="lists itself"):
        RepositoryAdmission(
            repository=CanonicalRepository.ERPNEXT,
            required_supporting=frozenset({CanonicalRepository.ERPNEXT}),
            justification="a self-referential closure is a malformed record",
            established_by="RQ-0002",
        )


def test_a_repository_admission_carries_no_version_or_role() -> None:
    # ADR-0017 §2: pinning versions would make the registry a corpus
    # manifest. ADR-0017 §8: no `repository_role`, because no measurement
    # needs one.
    field_names = set(RepositoryAdmission.model_fields)
    assert field_names == {"repository", "required_supporting", "justification", "established_by"}
    for forbidden in ("version", "commit", "repository_role", "role", "capabilities", "status"):
        assert forbidden not in field_names
