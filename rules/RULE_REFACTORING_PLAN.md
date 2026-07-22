# RULE REFACTORING PLAN

**Purpose:** During the R002 refactor, we found that R002 mixed two responsibilities — enforceable policy and the research/incident knowledge behind it — inside one file, contrary to this repository's Knowledge Hierarchy (Rules and Research are meant to be separate artifact types; see [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md)). This document audits the other nine rules (`R001`, `R003`–`R010`) for the same issue and proposes a plan — **no rule other than R002 has been modified.**

## What "the same issue" looks like

Concretely: an `Architectural Impact` (or `Bad Pattern`) section that narrates a *specific, dated, named incident or project* — not just the general reasoning for why the rule matters. General reasoning ("custom code becomes debt we own forever") is fine in a Rule; a specific story ("on the `erp2` bench, we did X and Y happened") is research/production-incident knowledge and belongs outside the Rule, per the same logic applied to R002.

## Audit

| Rule | Risk Level | Mixing found? | Evidence |
|---|---|---|---|
| [R001 — Core Isolation](R001-core-isolation-non-invasive-extension.md) | Critical | **No** | `Architectural Impact` is general reasoning only (`bench update` behavior, `git diff` discoverability). No specific incident, project, or numbers named. |
| R002 — Native-First Discovery | High | **Yes — refactored** | See above. |
| [R003 — Low-Code / Configuration Over Code](R003-low-code-configuration-over-code.md) | Medium | **No** | `Architectural Impact` is general reasoning only (how ERPNext itself is built, upgrade blast radius). No specific incident named. |
| [R004 — Fixture & Metadata Integrity](R004-fixture-and-metadata-integrity.md) | Critical | **Partial** | `Architectural Impact` describes three failure *mechanisms* in real technical detail (`CannotCreateStandardDoctypeError`, fixture-resurrection-on-migrate) — general and reusable, not tied to one dated incident, but denser and more implementation-discussion-like than a Rule needs. |
| [R005 — Idempotent, Upgrade-Safe Deployment](R005-idempotent-upgrade-safe-deployment.md) | High | **Partial** | Same shape as R004: detailed, general mechanism explanation (Frappe Cloud silent-failure behavior, `required_apps` dev/prod divergence) rather than a specific named incident, but more implementation discussion than a lean Rule requires. |
| [R006 — Full Reproducibility](R006-full-reproducibility-fixtures-and-patches.md) | Critical | **Yes** | `Architectural Impact` narrates a specific, named incident: *"on the `erp2` bench, installing a new app and reloading with a plain `SIGHUP`... left the running gunicorn master serving stale code."* |
| [R007 — Thin Hooks, Centralized Service Layer](R007-thin-hooks-centralized-service-layer.md) | High | **Yes** | `Architectural Impact` cites the Commission Manager app's design by name; `Bad Pattern` adds a second embedded incident note: *"found and removed during the `apex_item` → `apex_customization` rebuild."* Two separate pieces of project history embedded directly in policy sections. |
| [R008 — Native Permission System](R008-native-permission-system-over-custom-checks.md) | Medium | **Yes** | `Architectural Impact` cites the Commission Manager's specific `User Permission` design choice as its justification. |
| [R009 — YAGNI](R009-yagni-no-speculative-infrastructure.md) | Medium | **Yes — most severe** | `Architectural Impact` narrates *two* separate incidents in detail: the Commission Manager design-review rejection (with quoted Arabic reasoning) and the `crm_apex` Kanban load test (with a specific dataset size, ~3,501 leads, and latency numbers). |
| [R010 — One DocType, One Responsibility](R010-one-doctype-one-responsibility.md) | High | **Yes** | `Architectural Impact` narrates the `apex_crm` rebuild by name with specific metrics (~13,700 lines of custom JS, a 5,157-line `api.py`). |

## Which rules should be refactored

**Should be refactored (clear narrative/incident mixing):** R006, R007, R008, R009, R010.
**Should be reviewed, lower urgency (dense technical explanation, not narrative):** R004, R005.
**Should be left as-is:** R001, R003 — already policy-only; no narrative to extract.

## Why

Same reason R002 was refactored: in each "Yes" case, the enforceable rule and the evidence that justifies it are currently inseparable — an agent or reviewer checking a proposal against, say, R009's `Bad Pattern` has to read through two incident narratives (one containing quoted Arabic commentary) to extract the actual, checkable policy. That's a coherence cost that compounds with the number of rules, and it's the same "research knowledge library disguised as prompts" risk called out in [PROJECT_CHARTER.md's Repository Philosophy](../PROJECT_CHARTER.md#repository-philosophy) — except here it's policy and knowledge blurred together, rather than prompts and rules. R004/R005 are lower urgency because their extra detail is general mechanism explanation (reusable across any project hitting the same failure mode), not a one-time story about *this* project — closer to Rationale than to Notes-worthy history, and arguably fine to trim lightly rather than fully re-architect.

## A systemic blocker worth naming before starting

**None of R001–R010 have a formal originating Research document** — all ten predate this repository's [Research Framework](../research/RESEARCH_FRAMEWORK.md). This is exactly the gap the R002 refactor hit and could only partially resolve: its `Derived From` field currently points to nothing, and its incident narrative was condensed into `Notes` as a stopgap rather than properly relocated, because creating a new Research document was out of scope for that task.

The same will be true for every rule in this plan. A *complete* refactor of R006–R010 (and, lower priority, R004–R005) is really **two steps per rule**, not one:

1. **Mechanical** — apply the same lean structure used for R002 (`Status` / `Risk Level` / `Rule` / `Rationale` / `Scope` / `Bad Pattern` / `Good Pattern` / `Exceptions` / `Derived From` / `Related Research` / `Related Rules` / `Related Anti-Patterns` / `Notes`), condensing each incident into a short `Notes` placeholder flagged as pending retroactive research — exactly what was done for R002.
2. **Retroactive research** — write a proper Research document (via [RESEARCH_TEMPLATE.md](../research/RESEARCH_TEMPLATE.md)) for each incident, so `Derived From` can eventually point to a real file instead of a placeholder. Note these will look different from RQ-0001: the evidence is almost entirely internal `Production Experience`, not external Tier 1–4 sources — most of the template's source-tier sections (ERPNext/Frappe Implementation, Official Documentation, GitHub/Forum/Community Findings) will legitimately be empty or "Not applicable," and that's fine.

Doing only Step 1 across all five "should be refactored" rules gets the repository to full structural consistency with R002 quickly. Step 2 can trail behind at whatever pace is comfortable — the plan below treats them as separately schedulable.

## Priority and effort

| Rule | Priority | Step 1 (mechanical) effort | Step 2 (retroactive research) effort |
|---|---|---|---|
| R009 | **High** — Critical risk*-adjacent (Medium risk, but the most severe mixing of any rule; two incidents, hardest to read as policy today) | Low | Medium (two separate incidents to document) |
| R006 | **High** — Critical risk, one incident | Low | Low–Medium |
| R010 | **High** — High risk, one incident with hard metrics | Low | Low–Medium |
| R007 | **High** — High risk, two embedded incidents (one inside Bad Pattern itself) | Low | Medium |
| R008 | **Medium** — Medium risk, one embedded example, less narrative-heavy than the above four | Low | Low |
| R004 | **Low–Medium** — Critical risk, but mixing is technical explanation, not narrative; lower urgency, still worth a lighter trim for consistency | Low | Low (mostly reusable technical detail, minimal true "incident" content) |
| R005 | **Low–Medium** — same shape as R004 | Low | Low |
| R001, R003 | **None** | — | — |

"Low" effort reflects that every rule file is short (16–45 lines) and already follows one consistent template, so the mechanical restructuring is closer to reformatting than rewriting — the actual work is deciding what counts as Rationale vs. Notes, which the R002 pass above already establishes as a pattern to repeat.

## Explicitly not done in this pass

Per task scope, no rule other than R002 has been edited. This plan only recommends order and effort — refactoring R004–R010 is deferred to future, separately-scoped work.
