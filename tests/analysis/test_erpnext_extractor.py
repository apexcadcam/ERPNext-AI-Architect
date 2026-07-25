"""Tests for `analysis/erpnext/` (Sprint 9, Phase 2). Deterministic
extraction only — no similarity, no recommendation, no knowledge graph,
no pipeline, no Runtime integration; those are later phases' own scope.
Fixtures only: no network, no real ERPNext server, no LLM.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from analysis.contract import BusinessEntity, BusinessProcess, BusinessRule
from analysis.erpnext.extractor import (
    extract_client_script,
    extract_doctype,
    extract_fields,
    extract_module,
    extract_report,
    extract_server_script,
    extract_workflow,
    extract_workspace,
)
from analysis.erpnext.metadata import (
    RawClientScript,
    RawDocType,
    RawField,
    RawModule,
    RawReport,
    RawServerScript,
    RawWorkflow,
    RawWorkflowTransition,
    RawWorkspace,
)

ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "analysis"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "erpnext"


def _load_fixture(name: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return result


# -- Module ---------------------------------------------------------------------------------------


def test_extract_module_from_a_real_fixture() -> None:
    raw = RawModule.model_validate(_load_fixture("module_selling.json"))
    entity = extract_module(raw)
    assert entity.entity_id == "module:Selling"
    assert entity.name == "Selling"
    assert entity.attributes == ("Customer", "Sales Order", "Quotation")
    assert len(entity.supporting_evidence) == 1


def test_extract_module_tolerates_missing_doctypes() -> None:
    entity = extract_module(RawModule(module_name="HR"))
    assert entity.attributes == ()


def test_extract_module_rejects_missing_module_name() -> None:
    with pytest.raises(ValidationError):
        RawModule.model_validate({"app_name": "erpnext"})


def test_extract_module_stable_identifier() -> None:
    first = extract_module(RawModule(module_name="Selling"))
    second = extract_module(RawModule(module_name="Selling"))
    assert first.entity_id == second.entity_id == "module:Selling"


# -- DocType ----------------------------------------------------------------------------------------


def test_extract_doctype_from_a_real_fixture() -> None:
    raw = RawDocType.model_validate(_load_fixture("doctype_customer.json"))
    entity = extract_doctype(raw)
    assert entity.entity_id == "doctype:Customer"
    assert entity.name == "Customer"
    assert entity.description == "A party that buys goods or services from the organization."
    # Declared field order preserved exactly; "tax_id"'s empty label falls
    # back to its fieldname, per extract_fields()'s own documented rule.
    assert entity.attributes == ("Customer Name", "Customer Type", "tax_id")
    assert len(entity.supporting_evidence) == 1
    assert entity.supporting_evidence[0].source_reference == "doctype:Customer"


def test_extract_doctype_tolerates_missing_description_and_fields() -> None:
    entity = extract_doctype(RawDocType(name="Bare DocType"))
    assert entity.description == ""
    assert entity.attributes == ()


def test_extract_doctype_rejects_missing_name() -> None:
    with pytest.raises(ValidationError):
        RawDocType.model_validate({"module": "Selling", "fields": []})


def test_extract_doctype_rejects_a_malformed_field_entry() -> None:
    with pytest.raises(ValidationError):
        RawDocType.model_validate({"name": "Customer", "fields": [{"label": "no fieldname at all"}]})


def test_extract_doctype_ignores_unmodeled_real_erpnext_fields() -> None:
    # The fixture itself already carries "doctype", "autoname", "istable",
    # "issubmittable" -- none modeled by RawDocType -- and parsed without
    # error above; this is the same tolerance, asserted explicitly.
    raw = RawDocType.model_validate(
        {"name": "X", "some_unmodeled_field": "value", "another_one": {"nested": True}}
    )
    assert raw.name == "X"


def test_extract_doctype_is_deterministic_across_repeated_calls() -> None:
    raw = RawDocType.model_validate(_load_fixture("doctype_customer.json"))
    assert extract_doctype(raw) == extract_doctype(raw)


def test_extract_fields_preserves_declared_order_and_falls_back_to_fieldname() -> None:
    fields = (
        RawField(fieldname="z_field", label="Z Field"),
        RawField(fieldname="a_field", label=""),
        RawField(fieldname="m_field", label="M Field"),
    )
    assert extract_fields(fields) == ("Z Field", "a_field", "M Field")


def test_extract_fields_rejects_missing_fieldname() -> None:
    with pytest.raises(ValidationError):
        RawField.model_validate({"label": "No fieldname"})


# -- Workspace --------------------------------------------------------------------------------------


def test_extract_workspace_from_a_real_fixture() -> None:
    raw = RawWorkspace.model_validate(_load_fixture("workspace_selling.json"))
    entity = extract_workspace(raw)
    assert entity.entity_id == "workspace:Selling"
    assert entity.attributes == ("Customer", "Sales Order", "Quotation")


def test_extract_workspace_tolerates_missing_links() -> None:
    entity = extract_workspace(RawWorkspace(name="Empty Workspace"))
    assert entity.attributes == ()


def test_extract_workspace_rejects_missing_name() -> None:
    with pytest.raises(ValidationError):
        RawWorkspace.model_validate({"module": "Selling"})


# -- Report -----------------------------------------------------------------------------------------


def test_extract_report_from_a_real_fixture() -> None:
    raw = RawReport.model_validate(_load_fixture("report_sales_analytics.json"))
    entity = extract_report(raw)
    assert entity.entity_id == "report:Sales Analytics"
    assert entity.description == "Query Report on Sales Invoice"
    assert entity.attributes == ("Customer", "Territory", "Total")


def test_extract_report_tolerates_missing_optional_fields() -> None:
    entity = extract_report(RawReport(name="Bare Report"))
    assert entity.description == ""
    assert entity.attributes == ()


def test_extract_report_rejects_missing_name() -> None:
    with pytest.raises(ValidationError):
        RawReport.model_validate({"ref_doctype": "Sales Invoice"})


# -- Workflow ---------------------------------------------------------------------------------------


def test_extract_workflow_from_a_real_fixture() -> None:
    raw = RawWorkflow.model_validate(_load_fixture("workflow_leave_application.json"))
    process = extract_workflow(raw)
    assert process.process_id == "workflow:Leave Application Workflow"
    assert process.description == "Workflow for Leave Application"
    # Declared state order preserved exactly -- never sorted.
    assert process.steps == ("Open", "Approved", "Rejected")
    # "Leave Approver" appears on all three transitions -- deduplicated,
    # order-preserving.
    assert process.actor_ids == ("Leave Approver",)


def test_extract_workflow_tolerates_missing_states_and_transitions() -> None:
    process = extract_workflow(RawWorkflow(name="Bare Workflow"))
    assert process.steps == ()
    assert process.actor_ids == ()
    assert process.description == ""


def test_extract_workflow_rejects_missing_name() -> None:
    with pytest.raises(ValidationError):
        RawWorkflow.model_validate({"document_type": "Leave Application"})


def test_extract_workflow_rejects_a_transition_with_no_state() -> None:
    with pytest.raises(ValidationError):
        RawWorkflow.model_validate(
            {"name": "X", "transitions": [{"action": "Approve", "allowed": "Manager"}]}
        )


def test_extract_workflow_actor_dedup_preserves_first_seen_order() -> None:
    raw = RawWorkflow(
        name="X",
        transitions=(
            RawWorkflowTransition(state="A", allowed="Manager"),
            RawWorkflowTransition(state="B", allowed="Approver"),
            RawWorkflowTransition(state="C", allowed="Manager"),
        ),
    )
    process = extract_workflow(raw)
    assert process.actor_ids == ("Manager", "Approver")


# -- Client Script ------------------------------------------------------------------------------------


def test_extract_client_script_from_a_real_fixture() -> None:
    raw = RawClientScript.model_validate(_load_fixture("client_script_customer_validation.json"))
    rule = extract_client_script(raw)
    assert rule.rule_id == "client_script:Customer Tax ID Validation"
    assert rule.statement == "Client Script 'Customer Tax ID Validation' on DocType 'Customer' (Form view)"


def test_extract_client_script_tolerates_missing_dt_and_view() -> None:
    rule = extract_client_script(RawClientScript(name="Bare Script"))
    assert rule.statement == "Client Script 'Bare Script' on DocType 'unspecified DocType' (unspecified view)"


def test_extract_client_script_rejects_missing_name() -> None:
    with pytest.raises(ValidationError):
        RawClientScript.model_validate({"dt": "Customer"})


def test_extract_client_script_never_reads_the_script_body() -> None:
    # RawClientScript has no "script" field at all -- the real fixture's
    # own script body is present in the source JSON and is silently
    # ignored (extra="ignore"), never inspected.
    raw = RawClientScript.model_validate(_load_fixture("client_script_customer_validation.json"))
    assert not hasattr(raw, "script")


# -- Server Script ------------------------------------------------------------------------------------


def test_extract_server_script_from_a_real_fixture() -> None:
    raw = RawServerScript.model_validate(_load_fixture("server_script_auto_assign.json"))
    rule = extract_server_script(raw)
    assert rule.rule_id == "server_script:Auto Assign Task Owner"
    assert rule.statement == (
        "Server Script 'Auto Assign Task Owner' (DocType Event) on DocType 'Task', event 'Before Insert'"
    )


def test_extract_server_script_tolerates_missing_optional_fields() -> None:
    rule = extract_server_script(RawServerScript(name="Bare Script"))
    assert rule.statement == (
        "Server Script 'Bare Script' (unspecified type) on DocType "
        "'unspecified DocType', event 'unspecified event'"
    )


def test_extract_server_script_rejects_missing_name() -> None:
    with pytest.raises(ValidationError):
        RawServerScript.model_validate({"script_type": "API"})


def test_extract_server_script_never_reads_the_script_body() -> None:
    raw = RawServerScript.model_validate(_load_fixture("server_script_auto_assign.json"))
    assert not hasattr(raw, "script")


# -- Cross-cutting: serialization, determinism, type correctness --------------------------------------


def test_extracted_entities_and_processes_round_trip_through_json() -> None:
    entity = extract_doctype(RawDocType.model_validate(_load_fixture("doctype_customer.json")))
    assert BusinessEntity.model_validate_json(entity.model_dump_json()) == entity

    process = extract_workflow(RawWorkflow.model_validate(_load_fixture("workflow_leave_application.json")))
    assert BusinessProcess.model_validate_json(process.model_dump_json()) == process

    rule = extract_server_script(
        RawServerScript.model_validate(_load_fixture("server_script_auto_assign.json"))
    )
    assert BusinessRule.model_validate_json(rule.model_dump_json()) == rule


def test_every_extractor_returns_the_correct_contract_type() -> None:
    assert isinstance(extract_module(RawModule(module_name="X")), BusinessEntity)
    assert isinstance(extract_doctype(RawDocType(name="X")), BusinessEntity)
    assert isinstance(extract_workspace(RawWorkspace(name="X")), BusinessEntity)
    assert isinstance(extract_report(RawReport(name="X")), BusinessEntity)
    assert isinstance(extract_workflow(RawWorkflow(name="X")), BusinessProcess)
    assert isinstance(extract_client_script(RawClientScript(name="X")), BusinessRule)
    assert isinstance(extract_server_script(RawServerScript(name="X")), BusinessRule)


# -- Import boundary --------------------------------------------------------------------------------


def _direct_imports(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


_FORBIDDEN = {"intelligence", "planning", "execution", "runtime", "orchestration"}


def test_erpnext_package_imports_none_of_the_forbidden_packages() -> None:
    violations = {
        str(py_file.relative_to(ANALYSIS_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN)
        for py_file in (ANALYSIS_DIR / "erpnext").rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & _FORBIDDEN)
    }
    assert violations == {}


def test_erpnext_package_has_no_network_or_ai_import() -> None:
    forbidden_extra = {"httpx", "requests", "urllib", "aiohttp", "anthropic", "openai"}
    violations = {
        str(py_file.relative_to(ANALYSIS_DIR)): sorted(_direct_imports(py_file) & forbidden_extra)
        for py_file in (ANALYSIS_DIR / "erpnext").rglob("*.py")
        if "__pycache__" not in py_file.parts and (_direct_imports(py_file) & forbidden_extra)
    }
    assert violations == {}


def test_extractor_module_imports_only_its_own_sibling_and_stdlib() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "erpnext" / "extractor.py")
    assert imports <= {"__future__", "analysis"}


def test_metadata_module_imports_only_stdlib_and_pydantic() -> None:
    imports = _direct_imports(ANALYSIS_DIR / "erpnext" / "metadata.py")
    assert imports <= {"__future__", "pydantic"}
