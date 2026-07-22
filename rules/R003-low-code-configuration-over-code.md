# R003: Low-Code Maximalism (Configuration Over Code)

## Status
Stable

## Risk Level
**Medium**

## Rule
Solve problems with configuration before you solve them with code. Frappe ships a stack of no-code/low-code primitives — Property Setter, Custom Field, Client Script, Server Script, Workflow, Print Format Builder, Report Builder, Notification, Assignment Rule — that must be tried and ruled out before a custom Python module, whitelisted API, or custom page is written. Custom code is the last resort, not the default starting point.

## Rationale
ERPNext itself is built low-code-first: doctypes, workflows, and permissions are metadata, not hardcoded logic. Every line of bespoke Python/JS added is a line owned for the app's entire lifetime — through every future core upgrade and bug report — while configuration lives as fixtures/metadata: portable, diff-able, and resistant to rot when `frappe` internals change underneath it. Fewer custom lines means a smaller upgrade blast radius and a smaller surface to debug.

## Scope
Applies before writing any custom Python/JS logic, at the point a new feature or behavior is being designed.

## Bad Pattern
Writing a custom whitelisted `@frappe.whitelist()` Python endpoint plus a custom page with hand-rolled JS to move a document through approval states — reimplementing what the **Workflow** doctype already does natively, including permission-aware state transitions and email alerts.

## Good Pattern
Model the approval flow as a **Workflow** (states + transitions + role-based actions). Use **Client Script** with `depends_on` / `fetch_from` / `set_query` for field show/hide and filtering instead of a custom form controller. Reserve custom server code for logic that genuinely cannot be expressed as configuration — e.g. a non-trivial calculation or third-party integration.

## Exceptions
Custom code is justified once configuration primitives are ruled out — e.g., a non-trivial calculation or third-party integration (see Good Pattern).

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R001 — Core Isolation & Non-Invasive Extension](R001-core-isolation-non-invasive-extension.md); [R007 — Thin Hooks, Centralized Service Layer](R007-thin-hooks-centralized-service-layer.md)

## Related Anti-Patterns
None yet.
