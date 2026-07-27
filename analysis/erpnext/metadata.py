"""Raw ERPNext metadata shapes — Sprint 9, Phase 2.

These are **input** types, not this project's own domain vocabulary —
they exist only to give `extractor.py` a validated, typed view onto the
subset of each ERPNext metadata concept's real JSON schema this extractor
actually reads. Unlike every contract in `analysis/contract.py` (this
project's own controlled vocabulary, `extra="forbid"`), every model here
is `extra="ignore"`: a real exported ERPNext DocType/Workflow/Report/etc.
JSON file carries dozens of fields this extractor has no use for (e.g. a
DocType's `autoname`, `sort_field`, `permissions`, ...), and rejecting a
real fixture outright for carrying them would defeat the purpose of these
being *input* parsers for an external, uncontrolled schema. A required
field (e.g. `name`) missing is still rejected clearly — that is a
malformed input, not an unmodeled one.

Every field mirrors Frappe/ERPNext's own real metadata schema, mapped to
the identical `interface_kind` vocabulary `docs/knowledge-pipeline/
KNOWLEDGE_ARTIFACTS.md §2.2` already established for `Knowledge API`
(`doctype-field`, `hook-signature`) — this project's second, independent
extraction path for the same underlying source material, per this
package's own module docstring.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RawField(BaseModel):
    """One entry of a DocType's own `fields` array."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    fieldname: str = Field(min_length=1)
    label: str = ""
    fieldtype: str = ""


class RawDocType(BaseModel):
    """The subset of a DocType's real JSON export this extractor reads."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    module: str = ""
    description: str = ""
    fields: tuple[RawField, ...] = ()


class RawModule(BaseModel):
    """The subset of a Module Def's real JSON export this extractor
    reads. `doctypes`, if supplied, is **not** part of Module Def's own
    schema — Frappe derives module membership from each DocType's own
    `module` field, not the reverse. Recording it here is a convenience
    for callers that already know which DocTypes belong to a module;
    this extractor never infers it.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    module_name: str = Field(min_length=1)
    doctypes: tuple[str, ...] = ()


class RawWorkspaceLink(BaseModel):
    """One entry of a Workspace's own `links` array."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    label: str = Field(min_length=1)
    link_to: str = ""


class RawWorkspace(BaseModel):
    """The subset of a Workspace's real JSON export this extractor reads."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    module: str = ""
    links: tuple[RawWorkspaceLink, ...] = ()


class RawReportColumn(BaseModel):
    """One entry of a Report's own `columns` array."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    label: str = Field(min_length=1)
    fieldname: str = ""


class RawReport(BaseModel):
    """The subset of a Report's real JSON export this extractor reads."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    ref_doctype: str = ""
    report_type: str = ""
    columns: tuple[RawReportColumn, ...] = ()


class RawWorkflowState(BaseModel):
    """One entry of a Workflow's own `states` array."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    state: str = Field(min_length=1)


class RawWorkflowTransition(BaseModel):
    """One entry of a Workflow's own `transitions` array. `allowed` is the
    Role permitted to perform `action` — the closest thing Workflow
    metadata carries to an `Actor` reference; this extractor cites it by
    name only, it does not resolve or construct an `Actor`.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    state: str = Field(min_length=1)
    action: str = ""
    next_state: str = ""
    allowed: str = ""


class RawWorkflow(BaseModel):
    """The subset of a Workflow's real JSON export this extractor reads."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    document_type: str = ""
    states: tuple[RawWorkflowState, ...] = ()
    transitions: tuple[RawWorkflowTransition, ...] = ()


class RawClientScript(BaseModel):
    """The subset of a Client Script's real JSON export this extractor
    reads. The script body itself (`script`, JavaScript) is deliberately
    not modeled here — reading its contents to describe what it *does*
    would be interpretation, not extraction.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    dt: str = ""
    view: str = ""


class RawServerScript(BaseModel):
    """The subset of a Server Script's real JSON export this extractor
    reads. The script body itself (`script`, Python) is deliberately not
    modeled here, for the same reason as `RawClientScript`.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    script_type: str = ""
    reference_doctype: str = ""
    doctype_event: str = ""
