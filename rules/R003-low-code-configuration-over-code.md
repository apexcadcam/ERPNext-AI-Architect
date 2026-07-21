# R003: Low-Code Maximalism (Configuration Over Code)

## Principle
Solve problems with configuration before you solve them with code. Frappe ships a stack of no-code/low-code primitives — Property Setter, Custom Field, Client Script, Server Script, Workflow, Print Format Builder, Report Builder, Notification, Assignment Rule — that must be tried and ruled out before a custom Python module, whitelisted API, or custom page is written. Custom code is the last resort, not the default starting point.

## Architectural Impact
ERPNext itself is built low-code-first: doctypes, workflows, and permissions are metadata, not hardcoded logic. Every line of bespoke Python/JS we add is a line *we* now own for the app's entire lifetime — through every future core upgrade, every Frappe version bump, every bug report. Configuration, by contrast, lives as fixtures/metadata: it's portable, diff-able, and doesn't rot when `frappe` internals change underneath it. Fewer custom lines means a smaller upgrade blast radius and a smaller surface for us to debug at 2am.

## Bad Pattern
Writing a custom whitelisted `@frappe.whitelist()` Python endpoint plus a custom page with hand-rolled JS to move a document through approval states — reimplementing what the **Workflow** doctype already does natively, including permission-aware state transitions and email alerts.

## Good Pattern
Model the approval flow as a **Workflow** (states + transitions + role-based actions). Use **Client Script** with `depends_on` / `fetch_from` / `set_query` for field show/hide and filtering instead of a custom form controller. Reserve custom server code for logic that genuinely cannot be expressed as configuration — e.g. a non-trivial calculation or third-party integration.

## Risk Level
**Medium**
