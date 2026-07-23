"""Tests for the Connector Contract (SPRINT3_ARCHITECTURE_PACKAGE.md §6.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from integration import ConnectorManifest, ConnectorManifestError, ConnectorOperation, load_connector_manifest


def _minimal_manifest_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "connector_id": "erpnext",
        "display_name": "ERPNext",
        "maintained_by": "integration-layer",
        "target_system_type": "erpnext-site",
        "version": "0.1.0",
        "endpoint_kind": "url",
        "endpoint_reference": "https://example.invalid",
        "entry_point": "connector:create",
    }
    defaults.update(overrides)
    return defaults


# -- Identity / structural validation (declaration 1) -------------------------


def test_a_minimal_manifest_constructs() -> None:
    manifest = ConnectorManifest(**_minimal_manifest_kwargs())  # type: ignore[arg-type]
    assert manifest.connector_id == "erpnext"
    assert manifest.operations == ()


def test_target_system_type_is_open_ended_not_an_enum() -> None:
    # §6.1: "one of [these], or a newly-registered kind the moment one is
    # needed" — never a closed set the schema itself enforces.
    manifest = ConnectorManifest(**_minimal_manifest_kwargs(target_system_type="a-brand-new-kind"))  # type: ignore[arg-type]
    assert manifest.target_system_type == "a-brand-new-kind"


def test_missing_required_field_raises() -> None:
    kwargs = _minimal_manifest_kwargs()
    del kwargs["endpoint_reference"]
    with pytest.raises(ValidationError):
        ConnectorManifest(**kwargs)  # type: ignore[arg-type]


def test_manifest_is_frozen() -> None:
    manifest = ConnectorManifest(**_minimal_manifest_kwargs())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        manifest.connector_id = "other"


# -- Authentication (declaration 2) --------------------------------------------


def test_credential_reference_is_never_required_for_an_unauthenticated_connector() -> None:
    manifest = ConnectorManifest(**_minimal_manifest_kwargs(auth_required=False))  # type: ignore[arg-type]
    assert manifest.credential_reference is None


def test_credential_reference_carries_a_pointer_never_a_literal_value() -> None:
    manifest = ConnectorManifest(
        **_minimal_manifest_kwargs(
            auth_required=True, auth_method="api_key", credential_reference="env://API_KEY"
        )  # type: ignore[arg-type]
    )
    assert manifest.credential_reference == "env://API_KEY"


# -- Operation Catalog (declaration 4) + Request/Response Shape (5) -----------


def test_operation_catalog_entries_construct() -> None:
    manifest = ConnectorManifest(
        **_minimal_manifest_kwargs(  # type: ignore[arg-type]
            operations=(
                ConnectorOperation(name="erpnext.read_record", kind="read", idempotent=True),
                ConnectorOperation(name="erpnext.write_record", kind="write", idempotent=False),
            )
        )
    )
    assert {operation.name for operation in manifest.operations} == {
        "erpnext.read_record",
        "erpnext.write_record",
    }


def test_duplicate_operation_names_within_one_manifest_raise() -> None:
    with pytest.raises(ValidationError, match="duplicate operation names"):
        ConnectorManifest(
            **_minimal_manifest_kwargs(  # type: ignore[arg-type]
                operations=(
                    ConnectorOperation(name="read_record", kind="read", idempotent=True),
                    ConnectorOperation(name="read_record", kind="read", idempotent=True),
                )
            )
        )


def test_provided_capabilities_reflects_operation_names() -> None:
    manifest = ConnectorManifest(
        **_minimal_manifest_kwargs(  # type: ignore[arg-type]
            operations=(
                ConnectorOperation(name="erpnext.read_record", kind="read", idempotent=True),
                ConnectorOperation(name="erpnext.write_record", kind="write", idempotent=False),
            )
        )
    )
    assert manifest.provided_capabilities == frozenset({"erpnext.read_record", "erpnext.write_record"})


def test_a_connector_with_no_operations_provides_no_capabilities() -> None:
    manifest = ConnectorManifest(**_minimal_manifest_kwargs())  # type: ignore[arg-type]
    assert manifest.provided_capabilities == frozenset()


# -- Destructive-Operation Gating (declaration 8) ------------------------------


def test_write_non_idempotent_defaults_to_requiring_confirmation() -> None:
    operation = ConnectorOperation(name="delete_record", kind="write", idempotent=False)
    assert operation.requires_confirmation is True


def test_write_idempotent_does_not_default_to_requiring_confirmation() -> None:
    operation = ConnectorOperation(name="upsert_record", kind="write", idempotent=True)
    assert operation.requires_confirmation is False


def test_read_operations_never_default_to_requiring_confirmation() -> None:
    operation = ConnectorOperation(name="read_record", kind="read", idempotent=False)
    assert operation.requires_confirmation is False


def test_explicit_override_wins_over_the_computed_default() -> None:
    forced_off = ConnectorOperation(
        name="delete_record", kind="write", idempotent=False, requires_confirmation_override=False
    )
    forced_on = ConnectorOperation(
        name="read_record", kind="read", idempotent=True, requires_confirmation_override=True
    )
    assert forced_off.requires_confirmation is False
    assert forced_on.requires_confirmation is True


# -- Retries (declaration 7) — structural only, no invocation in Phase 3 ------


def test_retry_fields_default_to_a_single_attempt() -> None:
    manifest = ConnectorManifest(**_minimal_manifest_kwargs())  # type: ignore[arg-type]
    assert manifest.max_attempts == 1
    assert manifest.retryable_status_codes == ()


def test_max_attempts_must_be_at_least_one() -> None:
    with pytest.raises(ValidationError):
        ConnectorManifest(**_minimal_manifest_kwargs(max_attempts=0))  # type: ignore[arg-type]


# -- entry_point (dynamic-loading convention) ----------------------------------


def test_entry_point_without_a_colon_raises() -> None:
    with pytest.raises(ValidationError, match="module_name:factory_function"):
        ConnectorManifest(**_minimal_manifest_kwargs(entry_point="connector"))  # type: ignore[arg-type]


def test_entry_module_and_factory_name_split_on_the_colon() -> None:
    manifest = ConnectorManifest(**_minimal_manifest_kwargs(entry_point="connector:create"))  # type: ignore[arg-type]
    assert manifest.entry_module_name == "connector"
    assert manifest.entry_factory_name == "create"


# -- load_connector_manifest() (file loading) ----------------------------------


def test_load_connector_manifest_reads_a_valid_yaml_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "connector.yaml"
    manifest_path.write_text(yaml.safe_dump(_minimal_manifest_kwargs()))

    manifest = load_connector_manifest(manifest_path)

    assert manifest.connector_id == "erpnext"


def test_load_connector_manifest_missing_file_raises() -> None:
    with pytest.raises(ConnectorManifestError):
        load_connector_manifest(Path("/nonexistent/connector.yaml"))


def test_load_connector_manifest_malformed_yaml_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / "connector.yaml"
    manifest_path.write_text("not: valid: yaml: [unterminated")

    with pytest.raises(ConnectorManifestError):
        load_connector_manifest(manifest_path)


def test_load_connector_manifest_non_mapping_yaml_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / "connector.yaml"
    manifest_path.write_text(yaml.safe_dump(["a", "list", "not", "a", "mapping"]))

    with pytest.raises(ConnectorManifestError):
        load_connector_manifest(manifest_path)


def test_load_connector_manifest_missing_required_field_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / "connector.yaml"
    kwargs = _minimal_manifest_kwargs()
    del kwargs["endpoint_reference"]
    manifest_path.write_text(yaml.safe_dump(kwargs))

    with pytest.raises(ConnectorManifestError):
        load_connector_manifest(manifest_path)
