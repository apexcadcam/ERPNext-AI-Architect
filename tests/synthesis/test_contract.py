"""Tests for `synthesis.contract` (Requirement Synthesis Engine Specification v1.1 §2, §3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from discovery.contract import RepositoryInventory, RepositoryMetadata, RepositoryStatistics
from synthesis.contract import (
    ApiFact,
    ComponentFact,
    ConfigurationFact,
    DependencyFact,
    EntryPointFact,
    ExtensionPointFact,
    ExtractionMethod,
    ModuleFact,
    RepositoryFacts,
    ServiceFact,
    SynthesisRequest,
    SynthesisStatistics,
    UnresolvedFact,
)


def _inventory() -> RepositoryInventory:
    return RepositoryInventory(
        inventory_id="inv-1",
        repository_root="/repo",
        discovered_at="2026-07-27T10:00:00+00:00",
        correlation_id="corr-1",
        files=(),
        truncated=False,
        excluded_paths=(),
        errors=(),
        statistics=RepositoryStatistics(
            total_files=0,
            total_directories=0,
            total_size_bytes=0,
            files_by_type={},
            largest_file_size=0,
            largest_file_path=None,
        ),
        metadata=RepositoryMetadata(repository_name="repo"),
    )


# -- SynthesisRequest ------------------------------------------------------------------------------


def test_synthesis_request_wraps_a_repository_inventory() -> None:
    request = SynthesisRequest(
        repository_inventory=_inventory(), correlation_id="corr-1", requested_by="test-suite"
    )
    assert request.repository_inventory.inventory_id == "inv-1"


def test_synthesis_request_applies_documented_defaults() -> None:
    request = SynthesisRequest(
        repository_inventory=_inventory(), correlation_id="corr-1", requested_by="test-suite"
    )
    assert request.max_files == 10_000
    assert request.timeout_seconds == 30.0


def test_synthesis_request_is_frozen() -> None:
    request = SynthesisRequest(
        repository_inventory=_inventory(), correlation_id="corr-1", requested_by="test-suite"
    )
    with pytest.raises(ValidationError):
        request.correlation_id = "other"


def test_synthesis_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SynthesisRequest(
            repository_inventory=_inventory(),
            correlation_id="corr-1",
            requested_by="test-suite",
            unknown_field=1,  # type: ignore[call-arg]
        )


# -- ExtractionMethod -------------------------------------------------------------------------------


def test_extraction_method_defines_deterministic_and_reasoning_assisted() -> None:
    assert {member.value for member in ExtractionMethod} == {"deterministic", "reasoning_assisted"}


# -- Fact types --------------------------------------------------------------------------------------


def test_module_fact_round_trips_through_json() -> None:
    fact = ModuleFact(
        name="apex_dashboard",
        relative_path="apex_dashboard",
        module_kind="frappe_app",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )
    restored = ModuleFact.model_validate_json(fact.model_dump_json())
    assert restored == fact


def test_component_fact_requires_non_empty_component_kind() -> None:
    with pytest.raises(ValidationError):
        ComponentFact(
            name="Apex Dashboard Settings",
            relative_path="x.json",
            component_kind="",
            detection_method=ExtractionMethod.DETERMINISTIC,
        )


def test_api_fact_signature_defaults_to_empty_string() -> None:
    fact = ApiFact(
        name="get_desktop_page_override",
        relative_path="overrides.py",
        api_kind="whitelisted_method",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )
    assert fact.signature == ""


def test_service_fact_requires_declared_via() -> None:
    with pytest.raises(ValidationError):
        ServiceFact(
            name="clear_all_dashboard_caches",
            relative_path="hooks.py",
            service_kind="scheduled_task",
            declared_via="",
            detection_method=ExtractionMethod.DETERMINISTIC,
        )


def test_configuration_fact_value_defaults_to_empty_string() -> None:
    fact = ConfigurationFact(
        key="app_name", relative_path="hooks.py", detection_method=ExtractionMethod.DETERMINISTIC
    )
    assert fact.value == ""


def test_dependency_fact_version_constraint_defaults_to_empty_string() -> None:
    fact = DependencyFact(
        name="pydantic",
        relative_path="pyproject.toml",
        dependency_kind="python",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )
    assert fact.version_constraint == ""


def test_extension_point_fact_round_trips() -> None:
    fact = ExtensionPointFact(
        name="frappe.desk.desktop.get_desktop_page",
        relative_path="hooks.py",
        extension_kind="override_whitelisted_method",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )
    restored = ExtensionPointFact.model_validate_json(fact.model_dump_json())
    assert restored == fact


def test_entry_point_fact_round_trips() -> None:
    fact = EntryPointFact(
        name="hooks.py",
        relative_path="hooks.py",
        entry_kind="frappe_app_entry",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )
    restored = EntryPointFact.model_validate_json(fact.model_dump_json())
    assert restored == fact


def test_unresolved_fact_requires_reason() -> None:
    with pytest.raises(ValidationError):
        UnresolvedFact(relative_path="broken.py", reason="")


# -- SynthesisStatistics --------------------------------------------------------------------------


def test_synthesis_statistics_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        SynthesisStatistics(files_examined=-1, files_skipped=0, files_failed=0, facts_extracted=0)


# -- RepositoryFacts --------------------------------------------------------------------------------


def _facts() -> RepositoryFacts:
    return RepositoryFacts(
        facts_id="facts-1",
        source_inventory_id="inv-1",
        repository_root="/repo",
        synthesized_at="2026-07-27T11:00:00+00:00",
        correlation_id="corr-1",
        modules=(),
        components=(),
        apis=(),
        services=(),
        configuration=(),
        dependencies=(),
        extension_points=(),
        entry_points=(),
        unresolved=(),
        truncated=False,
        statistics=SynthesisStatistics(files_examined=0, files_skipped=0, files_failed=0, facts_extracted=0),
    )


def test_repository_facts_round_trips_through_json() -> None:
    facts = _facts()
    restored = RepositoryFacts.model_validate_json(facts.model_dump_json())
    assert restored == facts


def test_repository_facts_is_frozen() -> None:
    facts = _facts()
    with pytest.raises(ValidationError):
        facts.truncated = True


def test_repository_facts_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RepositoryFacts(  # type: ignore[call-arg]
            facts_id="facts-1",
            source_inventory_id="inv-1",
            repository_root="/repo",
            synthesized_at="2026-07-27T11:00:00+00:00",
            correlation_id="corr-1",
            modules=(),
            components=(),
            apis=(),
            services=(),
            configuration=(),
            dependencies=(),
            extension_points=(),
            entry_points=(),
            unresolved=(),
            truncated=False,
            statistics=SynthesisStatistics(
                files_examined=0, files_skipped=0, files_failed=0, facts_extracted=0
            ),
            unexpected="field",
        )
