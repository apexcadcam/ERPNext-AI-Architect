"""Deterministic ERPNext metadata extraction — Sprint 9, Phase 2.

Converts raw ERPNext metadata (`metadata.py`) into `analysis.contract`
objects (`extractor.py`) — facts only, no inference, no similarity
computation, no classification, no recommendation, no Runtime
integration, no pipeline. See `extractor.py`'s own module docstring for
the concept-by-concept mapping decisions.
"""

from __future__ import annotations

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
    RawReportColumn,
    RawServerScript,
    RawWorkflow,
    RawWorkflowState,
    RawWorkflowTransition,
    RawWorkspace,
    RawWorkspaceLink,
)

__all__ = [
    "RawClientScript",
    "RawDocType",
    "RawField",
    "RawModule",
    "RawReport",
    "RawReportColumn",
    "RawServerScript",
    "RawWorkflow",
    "RawWorkflowState",
    "RawWorkflowTransition",
    "RawWorkspace",
    "RawWorkspaceLink",
    "extract_client_script",
    "extract_doctype",
    "extract_fields",
    "extract_module",
    "extract_report",
    "extract_server_script",
    "extract_workflow",
    "extract_workspace",
]
