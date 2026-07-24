"""Tests for the Filesystem Connector (Sprint 3, Phase 4; `invoke()` added
Sprint 5, Phase 1) — the architectural reference implementation of a
concrete Connector, exercised directly against the Connector Contract
(`integration.contract`) and Lifecycle (`integration.lifecycle`) it is
built on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from integration.connectors.filesystem.connector import FilesystemConnector, create
from integration.contract import ConnectorManifest, ConnectorOperation, ConnectorRequest
from integration.errors import ConnectorLifecycleError
from integration.lifecycle import ConnectorLifecycle


def _manifest(root: Path) -> ConnectorManifest:
    return ConnectorManifest(
        connector_id="filesystem",
        display_name="Filesystem",
        maintained_by="test-suite",
        target_system_type="filesystem",
        version="0.1.0",
        endpoint_kind="local_path",
        endpoint_reference=str(root),
        operations=(
            ConnectorOperation(name="filesystem.read_text", kind="read", idempotent=True),
            ConnectorOperation(name="filesystem.write_text", kind="write", idempotent=False),
            ConnectorOperation(name="filesystem.exists", kind="read", idempotent=True),
            ConnectorOperation(name="filesystem.list_directory", kind="read", idempotent=True),
        ),
        entry_point="connector:create",
    )


@pytest.fixture
def connected(tmp_path: Path) -> FilesystemConnector:
    connector = FilesystemConnector(_manifest(tmp_path))
    connector.connect()
    return connector


# -- Contract / capability discovery ------------------------------------------------


def test_create_factory_returns_a_connector_lifecycle_instance(tmp_path: Path) -> None:
    instance = create(_manifest(tmp_path))
    assert isinstance(instance, ConnectorLifecycle)
    assert isinstance(instance, FilesystemConnector)


def test_provided_capabilities_are_the_four_declared_operations(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    assert manifest.provided_capabilities == frozenset(
        {
            "filesystem.read_text",
            "filesystem.write_text",
            "filesystem.exists",
            "filesystem.list_directory",
        }
    )


def test_no_erp_specific_or_planner_capability_leaks_in(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    assert not any("erpnext" in capability for capability in manifest.provided_capabilities)
    assert not any("plan" in capability for capability in manifest.provided_capabilities)


# -- §6.1 declaration 8: destructive-operation metadata ------------------------------


def test_write_text_operation_requires_confirmation_via_the_existing_default(tmp_path: Path) -> None:
    # write_text is declared kind="write", idempotent=False with *no*
    # requires_confirmation_override — it must be gated by the Connector
    # Contract's own computed default (integration/contract.py), not a
    # connector-specific bypass.
    manifest = _manifest(tmp_path)
    write_op = next(op for op in manifest.operations if op.name == "filesystem.write_text")

    assert write_op.requires_confirmation_override is None
    assert write_op.requires_confirmation is True


def test_read_operations_never_require_confirmation(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    read_ops = [op for op in manifest.operations if op.name != "filesystem.write_text"]

    assert all(op.requires_confirmation is False for op in read_ops)


# -- Lifecycle -----------------------------------------------------------------------


def test_connect_succeeds_against_an_existing_directory(tmp_path: Path) -> None:
    connector = FilesystemConnector(_manifest(tmp_path))
    connector.connect()
    assert connector.health_check().healthy is True


def test_connect_against_a_missing_root_raises(tmp_path: Path) -> None:
    connector = FilesystemConnector(_manifest(tmp_path / "does_not_exist"))
    with pytest.raises(ConnectorLifecycleError):
        connector.connect()


def test_health_check_before_connect_reports_unhealthy(tmp_path: Path) -> None:
    connector = FilesystemConnector(_manifest(tmp_path))
    health = connector.health_check()
    assert health.healthy is False


def test_disconnect_resets_connection_state(connected: FilesystemConnector) -> None:
    connected.disconnect()
    assert connected.health_check().healthy is False


def test_operation_before_connect_raises(tmp_path: Path) -> None:
    connector = FilesystemConnector(_manifest(tmp_path))
    with pytest.raises(ConnectorLifecycleError):
        connector.exists("anything.txt")


# -- read_text -------------------------------------------------------------------------


def test_read_text_returns_file_contents(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "greeting.txt").write_text("hello", encoding="utf-8")
    assert connected.read_text("greeting.txt") == "hello"


def test_read_text_missing_file_raises(connected: FilesystemConnector) -> None:
    with pytest.raises(FileNotFoundError):
        connected.read_text("nope.txt")


def test_read_text_on_a_directory_raises(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "adir").mkdir()
    with pytest.raises(FileNotFoundError):
        connected.read_text("adir")


# -- write_text ----------------------------------------------------------------------


def test_write_text_creates_a_new_file(connected: FilesystemConnector, tmp_path: Path) -> None:
    connected.write_text("new.txt", "content")
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"


def test_write_text_overwrites_an_existing_file(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("old", encoding="utf-8")
    connected.write_text("existing.txt", "new")
    assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "new"


def test_write_text_creates_missing_parent_directories(
    connected: FilesystemConnector, tmp_path: Path
) -> None:
    connected.write_text("nested/dir/file.txt", "content")
    assert (tmp_path / "nested" / "dir" / "file.txt").read_text(encoding="utf-8") == "content"


# -- exists --------------------------------------------------------------------------


def test_exists_true_for_a_present_file(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "here.txt").write_text("x", encoding="utf-8")
    assert connected.exists("here.txt") is True


def test_exists_false_for_an_absent_path(connected: FilesystemConnector) -> None:
    assert connected.exists("nowhere.txt") is False


# -- list_directory ------------------------------------------------------------------


def test_list_directory_returns_sorted_entry_names(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    (tmp_path / "a.txt").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()

    assert connected.list_directory(".") == ("a.txt", "b.txt", "sub")


def test_list_directory_on_a_file_raises(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "afile.txt").write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        connected.list_directory("afile.txt")


def test_list_directory_on_a_missing_path_raises(connected: FilesystemConnector) -> None:
    with pytest.raises(NotADirectoryError):
        connected.list_directory("nope")


# -- Invalid / escaping paths ----------------------------------------------------------


def test_read_text_rejects_a_path_that_escapes_the_root(connected: FilesystemConnector) -> None:
    with pytest.raises(ValueError, match="escapes"):
        connected.read_text("../outside.txt")


def test_write_text_rejects_a_path_that_escapes_the_root(connected: FilesystemConnector) -> None:
    with pytest.raises(ValueError, match="escapes"):
        connected.write_text("../outside.txt", "content")


def test_exists_rejects_a_path_that_escapes_the_root(connected: FilesystemConnector) -> None:
    with pytest.raises(ValueError, match="escapes"):
        connected.exists("../../etc/passwd")


def test_list_directory_rejects_a_path_that_escapes_the_root(connected: FilesystemConnector) -> None:
    with pytest.raises(ValueError, match="escapes"):
        connected.list_directory("..")


def test_the_root_itself_is_a_valid_path_not_an_escape(
    connected: FilesystemConnector, tmp_path: Path
) -> None:
    (tmp_path / "child.txt").write_text("", encoding="utf-8")
    assert connected.list_directory(".") == ("child.txt",)


# -- invoke() (Sprint 5, Phase 1) -------------------------------------------------------


def _request(operation: str, **parameters: object) -> ConnectorRequest:
    return ConnectorRequest(
        operation=operation, parameters=parameters, correlation_id="corr-1", requested_by="test-suite"
    )


def test_invoke_read_text_success(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "greeting.txt").write_text("hello", encoding="utf-8")

    response = connected.invoke(_request("filesystem.read_text", path="greeting.txt"))

    assert response.status == "success"
    assert response.result == {"content": "hello"}
    assert response.correlation_id == "corr-1"


def test_invoke_write_text_success(connected: FilesystemConnector, tmp_path: Path) -> None:
    response = connected.invoke(_request("filesystem.write_text", path="new.txt", content="hi"))

    assert response.status == "success"
    assert response.result == {}
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hi"


def test_invoke_exists_success_true(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "here.txt").write_text("x", encoding="utf-8")

    response = connected.invoke(_request("filesystem.exists", path="here.txt"))

    assert response.status == "success"
    assert response.result == {"exists": True}


def test_invoke_exists_success_false(connected: FilesystemConnector) -> None:
    response = connected.invoke(_request("filesystem.exists", path="nowhere.txt"))

    assert response.status == "success"
    assert response.result == {"exists": False}


def test_invoke_list_directory_success(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    (tmp_path / "a.txt").write_text("", encoding="utf-8")

    response = connected.invoke(_request("filesystem.list_directory", path="."))

    assert response.status == "success"
    assert response.result == {"entries": ("a.txt", "b.txt")}


def test_invoke_list_directory_defaults_path_to_root(connected: FilesystemConnector, tmp_path: Path) -> None:
    (tmp_path / "only.txt").write_text("", encoding="utf-8")

    response = connected.invoke(_request("filesystem.list_directory"))

    assert response.status == "success"
    assert response.result == {"entries": ("only.txt",)}


def test_invoke_unknown_operation_returns_failure_not_raise(connected: FilesystemConnector) -> None:
    response = connected.invoke(_request("filesystem.delete_everything"))

    assert response.status == "failure"
    assert "unknown operation" in response.diagnostics


def test_invoke_missing_file_returns_failure_not_raise(connected: FilesystemConnector) -> None:
    response = connected.invoke(_request("filesystem.read_text", path="nope.txt"))

    assert response.status == "failure"
    assert response.diagnostics


def test_invoke_missing_required_parameter_returns_failure_not_raise(connected: FilesystemConnector) -> None:
    response = connected.invoke(_request("filesystem.read_text"))  # no "path"

    assert response.status == "failure"
    assert response.diagnostics


def test_invoke_path_escape_returns_failure_not_raise(connected: FilesystemConnector) -> None:
    response = connected.invoke(_request("filesystem.read_text", path="../outside.txt"))

    assert response.status == "failure"
    assert "escapes" in response.diagnostics


def test_invoke_before_connect_raises_connector_lifecycle_error(tmp_path: Path) -> None:
    connector = FilesystemConnector(_manifest(tmp_path))
    with pytest.raises(ConnectorLifecycleError):
        connector.invoke(_request("filesystem.read_text", path="x.txt"))


def test_invoke_response_always_carries_the_requests_correlation_id(connected: FilesystemConnector) -> None:
    request = ConnectorRequest(
        operation="filesystem.exists",
        parameters={"path": "x"},
        correlation_id="a-specific-correlation-id",
        requested_by="test-suite",
    )
    response = connected.invoke(request)

    assert response.correlation_id == "a-specific-correlation-id"
