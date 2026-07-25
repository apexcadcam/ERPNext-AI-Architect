"""Deterministic ERPNext metadata extraction — Sprint 9, Phase 2.

Implements the approved Sprint 9 brief's Phase 2 objective: "the extractor
gathers facts, it never interprets them." Every function here is a pure,
deterministic mapping from one `analysis.erpnext.metadata` (validated raw
ERPNext metadata) shape to one `analysis.contract` shape — no inference,
no similarity computation, no classification, no recommendation. Calling
the same function twice with equal input produces equal output, always;
no field on any raw or produced type derives from a clock, a random
source, or process-local state.

**Mapping decisions, disclosed rather than left implicit:**

- `DocType`, `Module`, `Workspace`, `Report` → `BusinessEntity`. Each is a
  named thing ERPNext's own metadata declares to exist; none is a
  process, a rule, or an actor. `Fields`/`Workspace links`/`Report
  columns` become `BusinessEntity.attributes` — descriptive facts folded
  into their owning entity, never a standalone top-level object, because
  none of them has independent identity apart from what declares them
  (mirrored exactly by `extract_fields()` returning a plain tuple of
  strings, not a new contract type).
- `Workflow` → `BusinessProcess`. The one concept here that is
  unambiguously a state-transition process — `steps` preserves the
  workflow's own declared state order exactly (re-sorting it would be an
  interpretation this extractor is not permitted to make); `actor_ids`
  cites each transition's `allowed` Role by name, since no `Actor` object
  exists yet for this extractor to construct or resolve one against.
- `Client Script`, `Server Script` → `BusinessRule`. Each encodes
  organization-specific conditional behavior attached to a DocType — the
  closest existing concept to "a stated rule" among Phase 1's contracts.
  `statement` records only the script's own attachment metadata (name,
  DocType, trigger point) — never a summary of what the script's code
  body does, which would be interpretation, not extraction.
- No `BusinessConstraint` or `Actor` instance is produced by this module.
  Neither concept is naturally derivable from the eight supported ERPNext
  metadata kinds without inventing a mapping that isn't there — an
  honest gap, not a silent omission of scope.

Imports nothing beyond `analysis.contract` (a sibling module in this same
package) and the standard library: no `intelligence`, `planning`,
`execution`, `runtime`, or `orchestration`.
"""

from __future__ import annotations

from analysis.contract import BusinessEntity, BusinessProcess, BusinessRule, SupportingEvidence
from analysis.erpnext.metadata import (
    RawClientScript,
    RawDocType,
    RawField,
    RawModule,
    RawReport,
    RawServerScript,
    RawWorkflow,
    RawWorkspace,
)


def _evidence_for(kind: str, name: str, *, module: str = "") -> SupportingEvidence:
    source_reference = f"{kind}:{name}"
    excerpt = f"{kind} '{name}'" + (f" in module '{module}'" if module else "")
    return SupportingEvidence(
        source_reference=source_reference,
        excerpt=excerpt,
        rationale=f"extracted from ERPNext {kind} metadata",
    )


def extract_fields(fields: tuple[RawField, ...]) -> tuple[str, ...]:
    """Fields have no identity apart from their owning DocType — this
    returns the plain attribute-name facts `extract_doctype()` folds into
    its `BusinessEntity.attributes`, in the exact order `fields` declares.
    """

    return tuple(field.label or field.fieldname for field in fields)


def extract_module(raw: RawModule) -> BusinessEntity:
    return BusinessEntity(
        entity_id=f"module:{raw.module_name}",
        name=raw.module_name,
        attributes=raw.doctypes,
        supporting_evidence=(_evidence_for("module", raw.module_name),),
    )


def extract_doctype(raw: RawDocType) -> BusinessEntity:
    return BusinessEntity(
        entity_id=f"doctype:{raw.name}",
        name=raw.name,
        description=raw.description,
        attributes=extract_fields(raw.fields),
        supporting_evidence=(_evidence_for("doctype", raw.name, module=raw.module),),
    )


def extract_workspace(raw: RawWorkspace) -> BusinessEntity:
    return BusinessEntity(
        entity_id=f"workspace:{raw.name}",
        name=raw.name,
        attributes=tuple(link.label for link in raw.links),
        supporting_evidence=(_evidence_for("workspace", raw.name, module=raw.module),),
    )


def extract_report(raw: RawReport) -> BusinessEntity:
    description = (
        f"{raw.report_type} on {raw.ref_doctype}".strip() if (raw.report_type or raw.ref_doctype) else ""
    )
    return BusinessEntity(
        entity_id=f"report:{raw.name}",
        name=raw.name,
        description=description,
        attributes=tuple(column.label for column in raw.columns),
        supporting_evidence=(_evidence_for("report", raw.name),),
    )


def extract_workflow(raw: RawWorkflow) -> BusinessProcess:
    # dict.fromkeys: dedupe while preserving each transition's own first
    # appearance order -- never sorted, sorting would be interpretation.
    actor_ids = tuple(
        dict.fromkeys(transition.allowed for transition in raw.transitions if transition.allowed)
    )
    description = f"Workflow for {raw.document_type}".strip()
    return BusinessProcess(
        process_id=f"workflow:{raw.name}",
        name=raw.name,
        description=description if raw.document_type else "",
        actor_ids=actor_ids,
        steps=tuple(state.state for state in raw.states),
        supporting_evidence=(_evidence_for("workflow", raw.name),),
    )


def extract_client_script(raw: RawClientScript) -> BusinessRule:
    view = raw.view or "unspecified"
    dt = raw.dt or "unspecified DocType"
    return BusinessRule(
        rule_id=f"client_script:{raw.name}",
        statement=f"Client Script '{raw.name}' on DocType '{dt}' ({view} view)",
        supporting_evidence=(_evidence_for("client_script", raw.name),),
    )


def extract_server_script(raw: RawServerScript) -> BusinessRule:
    script_type = raw.script_type or "unspecified type"
    reference_doctype = raw.reference_doctype or "unspecified DocType"
    doctype_event = raw.doctype_event or "unspecified event"
    return BusinessRule(
        rule_id=f"server_script:{raw.name}",
        statement=(
            f"Server Script '{raw.name}' ({script_type}) on DocType "
            f"'{reference_doctype}', event '{doctype_event}'"
        ),
        supporting_evidence=(_evidence_for("server_script", raw.name),),
    )
