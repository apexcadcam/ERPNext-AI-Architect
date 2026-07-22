# Native First Discovery

## Status

- Date opened: 2026-07-22
- Date closed: 2026-07-22
- Status: `Resolved` (Reference — see [Final Recommendation](#final-recommendation); no new Rule produced this phase per task scope)

**Changelog**
- 2026-07-22 — Initial research completed (RQ-0001).

## Question

How should an ERPNext developer determine whether a requested feature already exists in Frappe/ERPNext core before writing custom code — and what is the concrete, repeatable sequence of checks that constitutes "native-first discovery" in practice?

Sub-questions investigated: where to search first; how to discover existing DocTypes, workflows, hooks, reports/Workspaces/Pages/Web Views, and Custom Fields; how to discover existing APIs; when customization is actually justified; and what mistakes commonly cause unnecessary customization.

## Background

This question was not triggered by new work — it was assigned directly as the first validation research for the framework itself (per the Repository Research Architect task). It is, however, exactly the kind of question [Question 1 of RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md#1-how-do-we-choose-a-research-topic) treats as highest priority: it's a repeated pain point, evidenced by the fact that this repository already contains a Rule — [R002](../rules/R002-native-first-discovery.md) — written directly in response to a real incident of skipping this discovery process.

## Existing Repository Check

**[R002 — Native-First Discovery (Research Before You Build)](../rules/R002-native-first-discovery.md) already exists and directly overlaps with this question.** R002 states the *principle* ("you must first prove that Frappe/ERPNext core does not already solve the problem") and documents one real incident (custom `phone_no_1`/`phone_no_2` fields duplicating the native `Contact` → `Contact Phone` child table already wired into the "Address & Contact" widget). It does **not**, however, define *how* to perform that proof — no concrete search sequence, no list of the specific UI/CLI/code mechanisms a developer should actually check.

This research is therefore **not a duplicate** under [RESEARCH_FRAMEWORK.md Question 7](RESEARCH_FRAMEWORK.md#7-when-should-research-be-rejected) — it operationalizes an existing Rule's principle rather than re-deriving it. This distinction is carried into the [Final Recommendation](#final-recommendation): the output of this research is framed as strengthening R002, not replacing or duplicating it.

Also checked and found relevant but narrower in scope (logged under [Related Topics](#related-topics), not duplicates): [R003 — Low-Code / Configuration Over Code](../rules/R003-low-code-configuration-over-code.md), [R008 — Native Permission System Over Custom Checks](../rules/R008-native-permission-system-over-custom-checks.md).

## ERPNext Implementation

Investigated directly against the ERPNext source installed in this bench (`apps/erpnext`, confirmed version below) rather than secondhand — this is Tier 1 evidence, empirically verified in Step 6 of the [Research Workflow](RESEARCH_FRAMEWORK.md#research-workflow).

- **Version confirmed:** `__version__ = "15.102.0"` (`apps/erpnext/erpnext/__init__.py`).
- **Scale of the native surface a developer would otherwise duplicate:** `find . -path "*/doctype/*.json" | grep -v test_ | wc -l` inside `apps/erpnext` returns **592** DocType definitions — this is the concrete, measured reason "search first" matters: the native surface area is large enough that duplication is easy to fall into by accident, not just carelessness.
- **Existing discovery surfaces confirmed present in ERPNext specifically:**
  - `report/` folders exist per module (e.g. `erpnext/crm/report/sales_pipeline_analytics/sales_pipeline_analytics.json`) — confirms Query/Script Reports are a pre-built discovery target before writing a custom report.
  - `workspace/` folders exist per module (e.g. `erpnext/crm/workspace/crm/crm.json`) — confirms Workspaces are a native, inspectable UI layer before building a custom Page.
  - The `Contact Phone` child table cited in R002's Good Pattern was independently confirmed present under `apps/frappe/frappe/contacts/doctype/contact_phone/` (see [Frappe Implementation](#frappe-implementation) — Contact itself is a Frappe-core doctype, not ERPNext-specific, which R002 does not make explicit).

## Frappe Implementation

- **Version confirmed:** `__version__ = "15.103.1"`, commit `61ab7e2b2409b293ffd3c8f72d730fa89b201332` (2026-03-24) (`apps/frappe/frappe/__init__.py`, `git log -1`).
- **Global Search / Awesomebar** (`frappe/desk/search.py`, `frappe/utils/global_search.py`, backing doctypes `Global Search DocType` / `Global Search Settings`): the framework's built-in mechanism for finding both *records* and, critically for this question, *DocTypes themselves* — confirmed via `search_widget()` / `search_link()`, both `@frappe.whitelist()`-exposed in `frappe/desk/search.py:36-80`.
- **`frappe.get_hooks()`** (`frappe/__init__.py:1616`): the programmatic way to inspect what hooks (`doc_events`, `scheduler_events`, etc.) are *already* registered by any installed app before adding a new one — directly relevant to the "how should existing hooks be located" sub-question. Its docstring confirms it reads `app/hooks.py` across all installed apps, filterable by `app_name`.
- **`Customize Form`** (`frappe/custom/doctype/customize_form/`, `frappe/custom/doctype/customize_form_field/`): the native UI/data layer specifically built to let a developer inspect a DocType's current fields (standard and already-customized) before adding more, and to add customizations as `Property Setter`/`Custom Field` records rather than editing the DocType definition — directly implements the "configuration over code" default this repository already commits to in [R003](../rules/R003-low-code-configuration-over-code.md).
- **`Workflow` doctype** (`frappe/workflow/doctype/workflow/workflow.json`): confirms Frappe ships a native, configurable state-machine layer — relevant to "how should existing workflows be inspected" (check `/app/workflow` list before hand-rolling status-transition logic in a controller).
- **Generic REST/RPC API surface** (`frappe/client.py`): whitelisted methods `get_list`, `get_value`, `set_value`, etc. provide a generic, already-built API for most CRUD needs. Combined with a repo-wide count of **186** files containing `@frappe.whitelist()` in Frappe core alone (`grep -rl "@frappe.whitelist" --include="*.py" frappe | wc -l`), this is strong evidence that a large, searchable, existing API surface should be checked (via `frappe.client`, or `grep`/IDE search for a relevant whitelisted method) before writing a new custom endpoint.

## Official Documentation

- **[Customizing DocTypes](https://docs.frappe.io/framework/user/en/basics/doctypes/customize)** (docs.frappe.io, accessed 2026-07-22): confirms Customize Form is the documented, sanctioned discovery-and-extension path — "When you change any properties of the DocType via Customize Form, it will not change the underlying DocType but add new custom objects to override those properties," and that changes apply automatically wherever `frappe.get_meta` is used. This directly corroborates the Frappe Implementation finding above from the documentation side, not just the source side.
- **[Global Search](https://docs.frappe.io/erpnext/user/manual/en/Global-search)** (docs.frappe.io, accessed 2026-07-22): confirms the Awesomebar/global search UI is the documented entry point for finding both existing records and, via DocType List navigation, existing DocTypes themselves.
- **[DocType](https://docs.erpnext.com/docs/user/manual/en/doctype)** (docs.erpnext.com, accessed 2026-07-22): general reference confirming DocType List is reachable and browsable as a first-class discovery surface, corroborating the source-level finding that all installed DocTypes (standard, app-provided, and custom) are listed together.

No official documentation page was found that consolidates all of the above into a single "search before you build" methodology — this gap is carried forward into [Open Questions](#open-questions) and shapes the [Final Recommendation](#final-recommendation).

## GitHub Findings

- **[frappe/erpnext#23981 — "A field with the name 'auto_repeat' already exists in doctype Sales Invoice"](https://github.com/frappe/erpnext/issues/23981)** (opened 2020-11-23; Tier 2). Root cause per the issue: ERPNext's own `fetch_to_customize` / `create_auto_repeat_custom_field_if_requried` flow attempted to create a Custom Field named `auto_repeat` without first checking whether a field of that name already existed on the target DocType, producing a collision error. A related issue, **[#22398](https://github.com/frappe/erpnext/issues/22398)**, reports the same collision pattern on a different DocType (Sales Order), suggesting a recurring shape rather than a one-off.
  - **Confirmation status:** a maintainer resolution/response was not visible in the fetched content for #23981 — this citation is used as evidence that the failure mode (field-name collision from insufficient existence-checking) is real and has occurred inside ERPNext core's own code, not as evidence that it was formally acknowledged as an architectural lesson by maintainers. Flagged as an item to re-verify (`gh issue view 23981`) before this citation is used to support anything stronger than "this failure mode is real."
  - **Relevance:** this is a different recurring shape than R002's own incident (R002 = building a parallel structure the framework already solved; this = colliding with an existing/soon-to-exist native field by skipping a pre-check) — see [Potential Rule Candidates](#potential-rule-candidates).

## Forum Findings

Multiple discuss.frappe.io threads were surfaced on doctype/custom-field mechanics (e.g., "Custom Doctype is not a child table," "New doctype in existing module or in custom app?"), but **no thread was found that directly discusses a discovery methodology or "check first" discipline** as its own topic — forum content in this area is overwhelmingly how-to/troubleshooting for a specific mechanic, not architectural guidance on when to search versus build. This is treated as a genuine finding, not a search failure: it corroborates the gap noted at the end of [Official Documentation](#official-documentation) — this methodology does not appear to be formally consolidated anywhere in the Frappe/ERPNext ecosystem's own writing.

## Community Findings

No community app or conference talk source was identified during this pass that materially adds to the Tier 1/2 findings above. Not exhaustively searched — see [Open Questions](#open-questions).

## Production Experience

The clearest production-experience evidence available is already recorded in this repository: **R002's own documented incident** — custom `phone_no_1`/`phone_no_2`/`phone_no_3` fields (plus a "Smart Contact Details" layer) built on CRM records, discovered only afterward to duplicate the native `Contact` → `Contact Phone` child table already surfaced through the standard "Address & Contact" widget. This research treats that incident as its primary Cross-cutting-axis evidence (per [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md#research-sources)) rather than re-collecting a new one, since it's the exact failure mode this question investigates and is already fully documented with root cause.

No additional new production incident was identified or reproduced during this research pass.

## Evidence Summary

No direct contradictions were found between sources — Tier 1 (source + docs), Tier 2 (GitHub), and the existing repository Rule all agree on the same underlying discipline. The actual finding of this research is a **gap in consolidation, not a conflict**: the discovery methodology is real and well-supported, but it is scattered across several independent Frappe/ERPNext primitives (Awesomebar/DocType List, Customize Form, `frappe.get_meta`/`get_hooks`, Workspace/Report folders, Workflow doctype, `frappe.client`) rather than documented anywhere — official or community — as a single ordered checklist. R002 is, as far as this research found, the closest thing to a consolidated statement of the discipline that exists anywhere, and even R002 states the principle without the mechanics.

Synthesizing the confirmed primitives into one ordered sequence (used as this research's answer to "where should a developer search first," in priority order):

1. **DocType List / Awesomebar** — does a DocType already modeling this concept exist at all (native, or from an already-installed app)?
2. **Customize Form on the relevant DocType(s)** — does the field/section/behavior already exist, standard or previously customized, before adding a new Custom Field?
3. **Workspace / Report folders for the relevant module** — does a native Workspace, Query Report, or Script Report already expose this view?
4. **`frappe.get_hooks()` / installed apps' `hooks.py`** — is an event already wired (by core or another installed app) that would conflict with or duplicate a new hook?
5. **Workflow doctype (`/app/workflow`)** — does a configurable state machine already cover this approval/status-transition need instead of custom controller logic?
6. **`frappe.client` generic API / existing whitelisted methods** — does `get_list`/`get_value`/`set_value` or an existing whitelisted method already cover this need before writing a new endpoint?
7. Only once 1–6 come up genuinely empty: customization is justified, and per R002's Good Pattern, the smallest sufficient extension (a Custom Field/Property Setter on the existing structure) is preferred over a new parallel DocType.

## Open Questions

- No official Tier 1 source consolidates this methodology end-to-end — is that a gap this repository should fill (see [Final Recommendation](#final-recommendation)), or is it reasonable that ERPNext/Frappe leaves this as tribal/architectural knowledge? *(Non-blocking for this research's own conclusion — it doesn't change the recommended sequence, only who else might benefit from it.)*
- GitHub issue #23981's maintainer-confirmation status needs re-verification via `gh issue view 23981` before being cited as anything stronger than "a real, reported occurrence." *(Non-blocking — the citation is already used at the appropriately cautious weight in this document.)*
- Whether Frappe/`bench` CLI exposes a dedicated discovery command (e.g., something equivalent to "list all doctypes matching X" from the command line) was not conclusively determined — `grep` of `frappe/commands/*.py` for doctype-related commands did not surface an obvious match, but this was not exhaustively checked against the full `bench` command reference. *(Non-blocking for the Final Recommendation, which does not depend on a CLI-specific mechanism — Awesomebar/DocType List already covers this need.)*
- Community/conference-talk sources (Tier 3) were not exhaustively searched. *(Non-blocking — Tier 1/2 evidence was sufficient to reach a confident recommendation per the [Research Quality Checklist](RESEARCH_CHECKLIST.md)'s Universal Minimum.)*

## Final Recommendation

Native-first discovery is not a single action but a **7-step ordered checklist** (given in full in [Evidence Summary](#evidence-summary)), each step backed by a specific, confirmed Frappe/ERPNext mechanism: DocType List/Awesomebar → Customize Form → Workspace/Report folders → `get_hooks()`/installed hooks.py → Workflow doctype → `frappe.client`/existing whitelisted methods → only then, minimal extension of an existing structure.

This research does **not** recommend a new standalone Engineering Rule. [R002](../rules/R002-native-first-discovery.md) already holds the correct, Rule-grade principle ("prove core doesn't solve it first") backed by a real incident. What was missing — and what this research supplies — is the operational "how." The correct output is to **strengthen R002** (or a companion `Checklist`/`Decision Tree` artifact under `application/` per [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md)) with this concrete sequence, rather than minting a new Rule that would overlap with R002's Principle section. See [Potential Rule Candidates](#potential-rule-candidates) for the specific seeds — none of which are created in this document, per this task's explicit scope.

## Potential Rule Candidates

*Seeds only — not created, not to be created until a later phase per this task's constraints. Each is checked against [RESEARCH_CHECKLIST.md](RESEARCH_CHECKLIST.md)'s Universal Minimum and passes it; none has been run through the Rule-specific bar, which is deliberately left for the later phase.*

1. **Amend R002, don't replace it** — add the 7-step discovery sequence from this research to R002's Architectural Impact / Good Pattern as the concrete "how," closing the gap this research identified. (Not a new artifact — a proposed edit to an existing one.)
2. **Candidate Checklist** — "Native-First Discovery Checklist," a direct, review-time-usable version of the 7-step sequence above, for use during a `Review` per [AGENTS.md](../AGENTS.md)'s mandatory procedure, before any new DocType/Custom Field/hook/endpoint is approved.
3. **Candidate Anti-Pattern** — "Custom field/DocType created without checking for an existing or reserved native name," distinct from R002's own Bad Pattern (parallel structure duplication): this one is about *collision*, not *duplication*, evidenced by GitHub #23981/#22398. Worth a standalone Anti-Pattern once (per [RESEARCH_CHECKLIST.md](RESEARCH_CHECKLIST.md)'s Anti-Pattern bar) a second independent occurrence inside this project's own work is observed — the GitHub issues alone establish the shape recurs in the wild, but not yet inside this codebase specifically.

## Related Topics

- [R002 — Native-First Discovery (Research Before You Build)](../rules/R002-native-first-discovery.md) — the existing Rule this research operationalizes.
- [R003 — Low-Code / Configuration Over Code](../rules/R003-low-code-configuration-over-code.md) — overlaps at Customize Form / Property Setter; R003 governs *what to prefer once you're customizing*, this research governs *what to check before you decide to customize at all*.
- [R008 — Native Permission System Over Custom Checks](../rules/R008-native-permission-system-over-custom-checks.md) — same "native-first" family, applied specifically to permissions; not covered by the 7-step sequence above and could warrant its own discovery-methodology research (e.g., "how to discover existing Role/User Permission coverage before writing `has_permission` code").
- Possible future research: a dedicated deep-dive on Workflow discoverability, and on API discoverability specifically (the `frappe.client` / `@frappe.whitelist()` surface was only sampled here, not exhaustively mapped).

## References

| # | Source | Tier | Link | Version / Commit | Accessed |
|---|---|---|---|---|---|
| 1 | ERPNext core source (`__init__.py`, DocType JSONs) | 1 | local: `apps/erpnext` | `15.102.0` | 2026-07-22 |
| 2 | Frappe core source (`desk/search.py`, `__init__.py`, `client.py`, `custom/doctype/customize_form`, `workflow/doctype/workflow`) | 1 | local: `apps/frappe` | `15.103.1`, commit `61ab7e2b2409b293ffd3c8f72d730fa89b201332` (2026-03-24) | 2026-07-22 |
| 3 | Customizing DocTypes | 1 | https://docs.frappe.io/framework/user/en/basics/doctypes/customize | — | 2026-07-22 |
| 4 | Global Search | 1 | https://docs.frappe.io/erpnext/user/manual/en/Global-search | — | 2026-07-22 |
| 5 | DocType (ERPNext manual) | 1 | https://docs.erpnext.com/docs/user/manual/en/doctype | — | 2026-07-22 |
| 6 | GitHub Issue — auto_repeat field collision | 2 (confirmation status unverified — see Open Questions) | https://github.com/frappe/erpnext/issues/23981 | — | 2026-07-22 |
| 7 | GitHub Issue — related field collision | 2 (confirmation status unverified) | https://github.com/frappe/erpnext/issues/22398 | — | 2026-07-22 |
| 8 | This repository's own R002 (Production Experience source) | Cross-cutting (Direct/Production) | [rules/R002-native-first-discovery.md](../rules/R002-native-first-discovery.md) | — | 2026-07-22 |
