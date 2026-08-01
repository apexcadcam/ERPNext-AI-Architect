"""Tests for `evidence.contract` (Evidence Extraction Engine Architecture Specification v1.1 §6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceExtractionError,
    EvidenceExtractionRequest,
    EvidenceKind,
    EvidenceSet,
    EvidenceStatistics,
    Source,
)

# -- Fixture builders --------------------------------------------------------------------------------


def _source(**overrides: object) -> Source:
    defaults: dict[str, object] = {
        "repository": CanonicalRepository.FRAPPE,
        "version": "v15.103.1",
        "commit": "61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        "relative_path": "frappe/model/document.py",
        "line": 421,
    }
    defaults.update(overrides)
    return Source(**defaults)  # type: ignore[arg-type]


def _evidence(**overrides: object) -> Evidence:
    defaults: dict[str, object] = {
        "evidence_id": "a" * 64,
        "kind": EvidenceKind.IMPLEMENTATION,
        "category": EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "symbol": "frappe.model.document.Document.validate",
        "subject": "validate",
        "source": _source(),
        "collector": CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR,
        "collected_at": "2026-07-27T12:00:00+00:00",
    }
    defaults.update(overrides)
    return Evidence(**defaults)  # type: ignore[arg-type]


# -- CanonicalRepository / EvidenceKind / EvidenceCategory / CollectorName ----------------------------


def test_canonical_repository_defines_exactly_the_admitted_repositories() -> None:
    # Renamed from "the two documented values" when ADR-0017 admitted a
    # third. The assertion is closed on purpose: a member added without a
    # deliberate edit here is a repository nobody decided to admit, and
    # `tests/aggregation/test_admission.py` separately requires each one to
    # carry a researched supporting-corpus closure.
    assert {member.value for member in CanonicalRepository} == {"frappe", "erpnext", "hrms"}


def test_evidence_kind_defines_exactly_the_documented_value() -> None:
    assert {member.value for member in EvidenceKind} == {"implementation"}


def test_evidence_category_defines_exactly_the_four_documented_values() -> None:
    # Two v1 signal categories, plus Sprint 22's two structural ones.
    assert {member.value for member in EvidenceCategory} == {
        "controller_lifecycle_hook",
        "whitelisted_api_decoration",
        "class_definition",
        "class_base_declaration",
    }


def test_the_structural_categories_are_a_pair() -> None:
    # Inheritance Resolution §2.1. They are only meaningful together: the
    # definition records are the node set, the base declarations are the
    # edge set. If either were ever removed, a class with no declared
    # bases would stop being representable -- which is exactly the blind
    # spot that made the lifecycle-hook population underivable.
    values = {member.value for member in EvidenceCategory}
    assert ("class_definition" in values) == ("class_base_declaration" in values)


def test_collector_name_defines_exactly_the_three_documented_values() -> None:
    # One new collector, not two: a single AST pass emits both structural
    # categories (§2.4).
    assert {member.value for member in CollectorName} == {
        "controller_lifecycle_hook_collector",
        "whitelisted_api_decoration_collector",
        "class_definition_collector",
    }


# -- The structural categories (Sprint 22, Inheritance Resolution §2) -----------------------------------


def test_a_class_definition_is_representable() -> None:
    evidence = _evidence(
        category=EvidenceCategory.CLASS_DEFINITION,
        symbol="erpnext.controllers.accounts_controller.AccountsController",
        subject="AccountsController",
        collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
    )
    assert evidence.category is EvidenceCategory.CLASS_DEFINITION
    assert evidence.subject == "AccountsController"


def test_a_class_that_declares_no_base_is_still_fully_representable() -> None:
    # The invariant the two-category split exists to guarantee. A class
    # with no bases produces a definition record and no edge records, and
    # is therefore still present in the corpus -- unlike a design where
    # only "X declares base B" is recorded, under which it would vanish.
    evidence = _evidence(
        category=EvidenceCategory.CLASS_DEFINITION,
        symbol="erpnext.utilities.transaction_base.Plain",
        subject="Plain",
        collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
    )
    assert evidence.symbol.endswith(".Plain")


def test_a_base_declaration_records_the_base_name_as_written() -> None:
    # Raw fact, not a resolved reference (ADR-0015). Both spellings occur
    # in the real trees and both must survive into the corpus unchanged;
    # reconciling them is the resolver's job, downstream.
    bare = _evidence(
        category=EvidenceCategory.CLASS_BASE_DECLARATION,
        symbol="erpnext.selling.doctype.customer.customer.Customer",
        subject="Document",
        collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
    )
    dotted = _evidence(
        category=EvidenceCategory.CLASS_BASE_DECLARATION,
        symbol="erpnext.selling.doctype.customer.customer.Customer",
        subject="frappe.model.document.Document",
        collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
    )
    assert bare.subject == "Document"
    assert dotted.subject == "frappe.model.document.Document"


def test_a_class_with_two_bases_is_two_separate_records() -> None:
    # Atomicity (§5): one record per observed fact, exactly as a function
    # with three decorators produces three records.
    symbol = "erpnext.selling.doctype.customer.customer.Customer"
    records = [
        _evidence(
            category=EvidenceCategory.CLASS_BASE_DECLARATION,
            symbol=symbol,
            subject=base,
            collector=CollectorName.CLASS_DEFINITION_COLLECTOR,
        )
        for base in ("Document", "NestedSet")
    ]
    assert [record.subject for record in records] == ["Document", "NestedSet"]


def test_the_structural_categories_round_trip_through_json() -> None:
    for category in (EvidenceCategory.CLASS_DEFINITION, EvidenceCategory.CLASS_BASE_DECLARATION):
        evidence = _evidence(category=category, collector=CollectorName.CLASS_DEFINITION_COLLECTOR)
        assert Evidence.model_validate_json(evidence.model_dump_json()) == evidence


def test_evidence_carries_no_inheritance_inference_field() -> None:
    # ADR-0015: the collector records facts; descent is computed
    # downstream and never asserted in the artifact. If any of these ever
    # appears, an inference has been frozen into a record that claims to
    # state a fact.
    fields = set(Evidence.model_fields)
    for forbidden in (
        "is_document_subclass",
        "resolved_base",
        "resolved_bases",
        "base_classes",
        "depth",
        "is_abstract",
        "doctype",
        "ancestry",
    ):
        assert forbidden not in fields


# -- Source --------------------------------------------------------------------------------------------


def test_source_round_trips_through_json() -> None:
    source = _source()
    restored = Source.model_validate_json(source.model_dump_json())
    assert restored == source


def test_source_is_frozen() -> None:
    source = _source()
    with pytest.raises(ValidationError):
        source.line = 1


def test_source_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Source(
            repository=CanonicalRepository.FRAPPE,
            version="v15.103.1",
            commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
            relative_path="frappe/model/document.py",
            line=421,
            unexpected="field",  # type: ignore[call-arg]
        )


def test_source_rejects_empty_version() -> None:
    with pytest.raises(ValidationError):
        _source(version="")


def test_source_rejects_empty_relative_path() -> None:
    with pytest.raises(ValidationError):
        _source(relative_path="")


def test_source_rejects_a_commit_that_is_not_hex() -> None:
    with pytest.raises(ValidationError):
        _source(commit="not-a-hex-hash")


def test_source_rejects_a_commit_shorter_than_seven_characters() -> None:
    with pytest.raises(ValidationError):
        _source(commit="abc123")


def test_source_accepts_a_seven_character_abbreviated_commit() -> None:
    source = _source(commit="61ab7e2")
    assert source.commit == "61ab7e2"


def test_source_rejects_a_line_below_one() -> None:
    with pytest.raises(ValidationError):
        _source(line=0)


# -- Evidence ------------------------------------------------------------------------------------------


def test_evidence_round_trips_through_json() -> None:
    evidence = _evidence()
    restored = Evidence.model_validate_json(evidence.model_dump_json())
    assert restored == evidence


def test_evidence_is_frozen() -> None:
    evidence = _evidence()
    with pytest.raises(ValidationError):
        evidence.subject = "other"


def test_evidence_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="a" * 64,
            kind=EvidenceKind.IMPLEMENTATION,
            category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
            symbol="frappe.model.document.Document.validate",
            subject="validate",
            source=_source(),
            collector=CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR,
            collected_at="2026-07-27T12:00:00+00:00",
            unexpected="field",  # type: ignore[call-arg]
        )


def test_evidence_rejects_an_empty_evidence_id() -> None:
    with pytest.raises(ValidationError):
        _evidence(evidence_id="")


def test_evidence_rejects_an_empty_symbol() -> None:
    with pytest.raises(ValidationError):
        _evidence(symbol="")


def test_evidence_rejects_an_empty_subject() -> None:
    with pytest.raises(ValidationError):
        _evidence(subject="")


def test_evidence_has_no_confidence_field() -> None:
    # Critical Design Principle (spec §5): confidence is Pattern
    # Aggregation's own, later, separate computation -- Evidence never
    # claims one about itself.
    assert "confidence" not in Evidence.model_fields


# -- EvidenceExtractionRequest ---------------------------------------------------------------------


def _request(**overrides: object) -> EvidenceExtractionRequest:
    defaults: dict[str, object] = {
        "repository": CanonicalRepository.FRAPPE,
        "source_root": "/home/gaber/frappe-bench/apps/frappe",
        "version": "v15.103.1",
        "commit": "61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        "correlation_id": "corr-1",
        "requested_by": "test-suite",
        "max_files": 10_000,
        "timeout_seconds": 60.0,
    }
    defaults.update(overrides)
    return EvidenceExtractionRequest(**defaults)  # type: ignore[arg-type]


def test_evidence_extraction_request_round_trips_through_json() -> None:
    request = _request()
    restored = EvidenceExtractionRequest.model_validate_json(request.model_dump_json())
    assert restored == request


def test_evidence_extraction_request_is_frozen() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        request.max_files = 1


def test_evidence_extraction_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceExtractionRequest(
            repository=CanonicalRepository.FRAPPE,
            source_root="/home/gaber/frappe-bench/apps/frappe",
            version="v15.103.1",
            commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
            correlation_id="corr-1",
            requested_by="test-suite",
            max_files=10_000,
            timeout_seconds=60.0,
            unexpected="field",  # type: ignore[call-arg]
        )


def test_evidence_extraction_request_rejects_max_files_below_one() -> None:
    with pytest.raises(ValidationError):
        _request(max_files=0)


def test_evidence_extraction_request_rejects_a_non_positive_timeout() -> None:
    with pytest.raises(ValidationError):
        _request(timeout_seconds=0.0)


# -- EvidenceStatistics ------------------------------------------------------------------------------


def test_evidence_statistics_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        EvidenceStatistics(files_examined=-1, files_skipped=0, files_failed=0, evidence_extracted=0)


def test_evidence_statistics_round_trips_through_json() -> None:
    statistics = EvidenceStatistics(files_examined=10, files_skipped=1, files_failed=0, evidence_extracted=25)
    restored = EvidenceStatistics.model_validate_json(statistics.model_dump_json())
    assert restored == statistics


# -- EvidenceExtractionError --------------------------------------------------------------------------


def test_evidence_extraction_error_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        EvidenceExtractionError(relative_path="frappe/broken.py", reason="")


def test_evidence_extraction_error_round_trips_through_json() -> None:
    error = EvidenceExtractionError(relative_path="frappe/broken.py", reason="SyntaxError: invalid syntax")
    restored = EvidenceExtractionError.model_validate_json(error.model_dump_json())
    assert restored == error


# -- EvidenceSet -----------------------------------------------------------------------------------


def _evidence_set(**overrides: object) -> EvidenceSet:
    defaults: dict[str, object] = {
        "evidence_set_id": "set-1",
        "schema_version": "1.0",
        "repository": CanonicalRepository.FRAPPE,
        "version": "v15.103.1",
        "commit": "61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        "extracted_at": "2026-07-27T12:00:00+00:00",
        "correlation_id": "corr-1",
        "evidence": (_evidence(),),
        "errors": (),
        "truncated": False,
        "statistics": EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=1
        ),
    }
    defaults.update(overrides)
    return EvidenceSet(**defaults)  # type: ignore[arg-type]


def test_evidence_set_round_trips_through_json() -> None:
    evidence_set = _evidence_set()
    restored = EvidenceSet.model_validate_json(evidence_set.model_dump_json())
    assert restored == evidence_set


def test_evidence_set_is_frozen() -> None:
    evidence_set = _evidence_set()
    with pytest.raises(ValidationError):
        evidence_set.truncated = True


def test_evidence_set_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceSet(
            evidence_set_id="set-1",
            schema_version="1.0",
            repository=CanonicalRepository.FRAPPE,
            version="v15.103.1",
            commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
            extracted_at="2026-07-27T12:00:00+00:00",
            correlation_id="corr-1",
            evidence=(),
            errors=(),
            truncated=False,
            statistics=EvidenceStatistics(
                files_examined=0, files_skipped=0, files_failed=0, evidence_extracted=0
            ),
            unexpected="field",  # type: ignore[call-arg]
        )


def test_evidence_set_accepts_zero_evidence() -> None:
    evidence_set = _evidence_set(
        evidence=(),
        statistics=EvidenceStatistics(
            files_examined=0, files_skipped=0, files_failed=0, evidence_extracted=0
        ),
    )
    assert evidence_set.evidence == ()


def test_evidence_set_rejects_an_empty_schema_version() -> None:
    with pytest.raises(ValidationError):
        _evidence_set(schema_version="")
