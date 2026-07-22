# R002: Native-First Discovery (Research Before You Build)

## Status
Stable

## Risk Level
**High**

## Rule
Before designing any new field, child table, or DocType, you must first **prove that Frappe/ERPNext core does not already solve the problem**. Exhaust the standard doctypes, the "Address & Contact" pattern, existing child tables, and standard reports/dashboards before writing a single line of a custom solution. If a satisfying native mechanism exists, use it — even if it's not a perfect fit — rather than building a parallel structure.

## Rationale
Skipping discovery produces duplicate, competing data models that fragment the same real-world concept across multiple places. A custom structure built without this check becomes future migration debt and an undocumented fork of ERPNext's own data model — invisible to the native tooling, reports, and integrations that only know about the standard structure.

## Scope
Applies at the point any new custom field, child table, or DocType is being *considered* — before implementation begins — in this project or any custom app built on Frappe/ERPNext.

## Bad Pattern
Adding `phone_no_1`, `phone_no_2`, `phone_no_3` custom fields directly to CRM Lead/Customer to capture multiple contact numbers, invented without checking what already renders on the "Address & Contact" section.

## Good Pattern
Use the native `Contact` doctype (linked via Dynamic Link to the parent record) and its built-in `Contact Phone` child table, surfaced through the standard "Address & Contact" widget already present on Customer, Lead, and other party doctypes. If the native model is missing one attribute (e.g. a "primary" flag), extend it with a Custom Field on the *existing* child table — don't rebuild the whole structure from scratch.

## Exceptions
None. The "missing one attribute" allowance in the Good Pattern is a compliant way to satisfy this rule when the native model is an imperfect fit — it is not an exception to it.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** [RQ-0001 — Native-First Discovery](../research/RQ-0001-native-first-discovery.md) — investigates the concrete discovery methodology this rule requires (DocType List/Awesomebar → Customize Form → Workspace/Report → hooks → Workflow → existing API → only then customize); a later, related study, not this rule's origin.

## Related Rules
[R003 — Low-Code / Configuration Over Code](R003-low-code-configuration-over-code.md); [R008 — Native Permission System Over Custom Checks](R008-native-permission-system-over-custom-checks.md)

## Related Anti-Patterns
None yet.
