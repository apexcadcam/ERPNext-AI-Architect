# ENGINEERING RULE SPECIFICATION

**Status:** Foundational
**Authority:** Subordinate to [PROJECT_CHARTER.md](../PROJECT_CHARTER.md) and [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md), which define the `Engineering Rule` artifact type at a high level. This document is the detailed, operational specification for that one artifact type — it formalizes the structure and boundaries first established, ad hoc, by the [R002 refactor](../rules/R002-native-first-discovery.md), and answers what that refactor left implicit.
**Scope:** Applies to every file in [`rules/`](../rules/), present and future. Does not itself refactor or create any rule.

---

## 1. Purpose

**What is an Engineering Rule?** A specific, falsifiable, non-negotiable architectural statement about how to build on Frappe/ERPNext in this repository — backed by evidence, checkable against a concrete proposal in one read. It is the repository's **source of truth** (see [PROJECT_CHARTER.md — Repository Philosophy](../PROJECT_CHARTER.md#repository-philosophy)): if any other artifact disagrees with a Rule, the Rule wins.

**Why it exists:** so that "is this proposal architecturally sound" has one place to check, with one answer, instead of being re-litigated from first principles — by a human or an AI agent — every time it comes up.

**How it differs from its neighbors:**

| vs. | The difference |
|---|---|
| **Research** | Research holds open questions, evidence gathering, and reasoning-in-progress — it is allowed to stay unresolved forever, and its job is to *investigate*. A Rule holds a closed, confident conclusion — it is not allowed to stay ambiguous, and its job is to *enforce*. A Rule cites the Research that produced it; Research is not required to ever produce a Rule (see [RESEARCH_FRAMEWORK.md, Question 6](../research/RESEARCH_FRAMEWORK.md#6-how-do-we-decide-the-output-type)). |
| **ADR** | An ADR records a specific, one-time decision — often about *this repository's own* structure or process — with its context and alternatives, and is valid even if narrow or non-recurring. A Rule is a standing, general policy meant to apply to *every future* situation of its kind. An ADR explains "why we chose X, once"; a Rule states "always do X." |
| **Skill** | A Skill is an executable procedure that *applies* one or more Rules to a recurring task. A Skill is not allowed to introduce judgment a Rule doesn't already contain — see [§4](#4-relationships). A Rule is the judgment; a Skill is the automation of applying it. |

---

## 2. Responsibilities

**What belongs inside a Rule:** the enforceable statement itself, general (not narrative) reasoning for why it matters, when it applies, a concrete Bad/Good Pattern pair, known exceptions, and *links* — never copies, never retellings — to the evidence, research, and related artifacts behind it.

**What must never appear inside a Rule**, and where it actually belongs instead:

| Content type | Belongs in a Rule? | Where it belongs instead |
|---|---|---|
| Production stories & historical incidents (a specific dated event, a named internal project, an implementation-history narrative of how something was built or fixed over time) | No | The Research file's `Production Experience` / `Background` sections. If no Research file exists yet (a Legacy Rule, [§6](#6-legacy-rules)), the Rule's `Evidence` field states only `Origin: Legacy Production Experience` — the incident itself is never retold inside the Rule, in any form or length. |
| Long explanations (multi-paragraph reasoning, mechanism deep-dives) | No | The Research file's `Background` / `Evidence Summary`. The Rule gets only the distilled, general version in `Rationale`. |
| Research evidence, condensed or otherwise (citations, quotes, source tiers, or any shortened retelling of them) | No | The Research file's `References` section. The Rule's `Evidence` field links to the file — it never restates, summarizes, or condenses what's in it. |
| Personal opinions (a preference with no backing evidence) | No | Nowhere, as a Rule input. An unevidenced opinion doesn't qualify — at most it's a `Best Practice` candidate (see [RESEARCH_CHECKLIST.md](../research/RESEARCH_CHECKLIST.md)), not a Rule. |
| Bench-specific / environment-specific details (a specific server name, a specific customer's data shape) | No | Research `Production Experience`, generalized before it reaches the Rule. A Rule states the *general* failure mode, not the specific system it was first observed on. |
| Implementation guides (step-by-step "how to do X") | No | `templates/` (a scaffold) or `skills/` (a packaged procedure). A Rule states policy, not procedure. |

A Rule contains no field for evidence overflow. If nothing more than "this is a Legacy Rule" can honestly be said about where it came from, that is the complete, final statement — not a placeholder for a condensed version of the story.

This table generalizes and tightens the separation first attempted in the [R002 refactor](../rules/R002-native-first-discovery.md). R002 itself has since fallen out of full compliance with this policy — see the Known Drift note in [§3](#3-rule-structure) — and should be treated as a rule pending reconciliation, not a model to copy as-is.

---

## 3. Rule Structure

### Canonical sections

| Section | Required? | Expected size | Purpose |
|---|---|---|---|
| **Status** | Required | One value: `Draft` / `Review` / `Stable` / `Deprecated` (see [ENGINEERING_META_MODEL.md — Rule Lifecycle](../ENGINEERING_META_MODEL.md#rule-lifecycle) for the full lifecycle this collapses from) | Whether the rule is enforceable yet, and where in [§7](#7-future-rules--mandatory-lifecycle) it currently sits. |
| **Risk Level** | Required | One value: `Critical` / `High` / `Medium` | How much damage violating this rule causes — signals review priority. |
| **Rule** | Required | 1–3 sentences | The enforceable statement itself. Must be checkable against a concrete proposal in one read. |
| **Rationale** | Required | 1–3 sentences, general only | Why the rule matters — the *category* of harm, not a story about one time it happened. |
| **Scope** | Required | 1 sentence | When/where the rule applies — the trigger condition for checking it. |
| **Bad Pattern** | Required | 1 short paragraph or short code block | The concrete, recognizable shape of the violation. |
| **Good Pattern** | Required | 1 short paragraph or short code block | The concrete, recognizable shape of compliance. |
| **Exceptions** | Required (may state "None") | 1–2 sentences | Legitimate carve-outs, if any — stated explicitly so silence isn't mistaken for "no exceptions exist." |
| **Evidence** | Required | See structure below | Where this rule's grounding lives. Never the evidence itself — only links to it. |
| **Related Rules** | Required (may state "None") | List of links | Other Rules this one composes with or should be read alongside. |
| **Related Anti-Patterns** | Required (may state "None yet") | List of links | Named recurring bad shapes this rule guards against. |

### The `Evidence` field

`Evidence` replaces what earlier drafts of this specification called `Supporting Research`, and is the only section a Rule uses to point at its grounding — there is no separate overflow section for anything evidence-shaped. It always has exactly two parts:

```
## Evidence
**Origin:** <link to the Research file that produced this rule> — or `Legacy Production Experience` if none exists (see §6).
**Additional:** <link(s) to other relevant Research, each with a one-line note on its role> — or `None`.
```

- **Origin** is required and singular in nature: either the one Research file this rule was drawn from, or, for a rule with no such file, the exact phrase `Legacy Production Experience` and nothing more.
- **Additional** is required to be present but may be empty (`None`) — it holds any number of further Research files relevant to the rule without being its origin, e.g. a later study of the discovery method the rule requires. This is how the field supports multiple evidence sources without needing multiple top-level sections.

**Known drift:** [R002](../rules/R002-native-first-discovery.md), the only rule refactored so far, predates this revision of the specification. It still uses the earlier `Derived From` / `Related Research` field pair instead of `Evidence`, and still carries a `Notes` section holding a condensed incident summary — a pattern this specification no longer permits (see [§2](#2-responsibilities)). Reconciling R002 to this structure, including removing its `Notes` section, is deferred to a future pass and is not performed here.

---

## 4. Relationships

```
Research  →  Engineering Rule  →  Skill  →  Agent
```

- **Research → Engineering Rule:** Research produces evidence and, when it reaches a confident conclusion, a *candidate* recommendation (`Potential Rule Candidates` in [RESEARCH_TEMPLATE.md](../research/RESEARCH_TEMPLATE.md)). The Rule crystallizes that recommendation into a short, enforceable, general statement and links back via `Evidence` — it does not copy the research's reasoning or evidence into itself (see [§2](#2-responsibilities)).
- **Engineering Rule → Skill:** A Skill composes one or more Rules into a repeatable, executable procedure for a specific recurring task. A Skill is only allowed to *apply* Rules — introducing judgment a Rule doesn't already contain breaks traceability and is treated as a defect in the Skill, not a shortcut (see [ENGINEERING_META_MODEL.md — Repository Object Model, invariant 2](../ENGINEERING_META_MODEL.md#repository-object-model)).
- **Skill → Agent:** An Agent composes Skills into a broader persona. Nothing about Rules flows directly to an Agent — an Agent's judgment is only ever as good as the Skills, and transitively the Rules, it's built from.

> **Invariant — information flows only downward.** `Research → Engineering Rule → Skill → Agent` is a one-way pipeline, not a cycle. Knowledge discovered while using a Skill or operating an Agent must never modify a Rule directly, at any distance — no matter how obviously correct the discovered fix seems in the moment. It must re-enter the system as new Research (a new topic or `Observation`) and earn its way back to a Rule change through the full lifecycle in [§7](#7-future-rules--mandatory-lifecycle) again. There is no shortcut from Skill or Agent back to Rule.

---

## 5. Rule Quality Standards

**Complete**, when:
- It passes the `Engineering Rule` bar in [RESEARCH_CHECKLIST.md](../research/RESEARCH_CHECKLIST.md) (the evidence side), **and**
- Every canonical section in [§3](#3-rule-structure) is present and appropriately filled — including `Evidence.Origin` stating `Legacy Production Experience` where applicable, and any other section allowed to say "None," each stated explicitly rather than left blank.

**Too verbose**, when:
- `Rationale`, `Bad Pattern`, or `Good Pattern` run past a short paragraph, or
- Any section contains a narrated story — a specific date, a named internal project, a hard number pulled from one incident (per the [§2](#2-responsibilities) table — that content belongs in Research, not here), or
- `Evidence` contains anything beyond `Origin` and `Additional` links — any retelling of the underlying incident or evidence, however short, is a violation of [§2](#2-responsibilities), not an acceptable summary.

**Too vague**, when:
- The `Rule` statement can't be checked against a real, concrete proposal in a single read — if applying it requires guessing what it actually forbids, it isn't a Rule yet.
- `Bad Pattern` isn't concrete enough to recognize on sight.
- `Rationale` is generic enough that it could be pasted into almost any other rule unchanged — usually a sign it's restating a value ([PROJECT_CHARTER.md — Design Principles](../PROJECT_CHARTER.md#design-principles)) rather than stating a specific, evidenced consequence.

**Rejected**, when:
- It fails the `Engineering Rule` bar in [RESEARCH_CHECKLIST.md](../research/RESEARCH_CHECKLIST.md), or
- It duplicates or silently contradicts an existing `Stable` rule (a conflict must be named explicitly, per [AGENTS.md](../AGENTS.md), not overridden quietly), or
- It's actually ADR-shaped — a one-time, non-recurring decision rather than a standing general policy — or
- It's actually a how-to — belongs in `templates/` or `skills/`, not `rules/`.

---

## 6. Legacy Rules

**Definition:** any rule whose `Evidence.Origin` cannot name a Research file that produced it. This currently includes **every rule in the repository** — R001, R003–R010 outright (per [RULE_REFACTORING_PLAN.md](../rules/RULE_REFACTORING_PLAN.md)), and even the refactored R002, whose origin field correctly has no formal Research file to point to (RQ-0001 is later, related research, not R002's source).

**Identification:** a Legacy Rule's `Evidence` field reads:

```
## Evidence
**Origin:** Legacy Production Experience
**Additional:** <link to any later, related research> — or `None`.
```

`Origin` says exactly this and nothing more — the incident that produced the rule is not retold, condensed, or referenced further inside the Rule itself, per [§2](#2-responsibilities).

**Is retroactive research required?** **No — optional.** Requiring every legacy rule to get a formal Research document before it can be trusted would block using rules that already work, purely for paperwork's sake — directly against this repository's solo-developer, anti-bureaucracy constraint. Retroactive research is *encouraged opportunistically*: when a legacy rule is next touched for any real reason (a review surfaces a question about it, it's being extended, a related bug occurs), that's the moment to write the retroactive Research file — never a blocking prerequisite before then. [RULE_REFACTORING_PLAN.md](../rules/RULE_REFACTORING_PLAN.md) already treats this as separately schedulable, trailing work; this section makes that the standing policy for all legacy rules, not just the ones in that plan.

**How Origin is recorded once retroactive research happens:** update `Evidence.Origin` to link the new Research file in place of `Legacy Production Experience`. No other section of the rule changes — the whole point, established by the R002 refactor, is that formalizing provenance must never alter what the rule actually requires.

---

## 7. Future Rules — Mandatory Lifecycle

```
Research → Review → Accepted Research → Engineering Rule → Rule Review → Approved Rule → Skill
```

Every stage maps onto a mechanism that already exists — this lifecycle introduces no new document types or tooling — and each stage that produces or changes a Rule file states which `Status` ([§3](#3-rule-structure)) the rule carries at that point:

1. **Research** — conducted per [RESEARCH_FRAMEWORK.md](../research/RESEARCH_FRAMEWORK.md), written using [RESEARCH_TEMPLATE.md](../research/RESEARCH_TEMPLATE.md).
2. **Review** — the research file is self-checked against the **Universal Minimum** in [RESEARCH_CHECKLIST.md](../research/RESEARCH_CHECKLIST.md).
3. **Accepted Research** — the research file's `Status` is `Resolved`, the Universal Minimum passes, and `Final Recommendation` / `Potential Rule Candidates` names a specific candidate rule (as [RQ-0001](../research/RQ-0001-native-first-discovery.md) already does).
4. **Engineering Rule** — drafted using the canonical structure in [§3](#3-rule-structure), `Evidence.Origin` linking back to the accepted research. Rule `Status: Draft`.
5. **Rule Review** — a short self-check, distinct from step 2 (which checks *evidence*; this checks the *rule's own form*), against [§5](#5-rule-quality-standards). Rule `Status: Review` for the duration of this check:
   - [ ] Passes the `Engineering Rule` bar in `RESEARCH_CHECKLIST.md`
   - [ ] Every canonical section present, none blank without an explicit "None"
   - [ ] Not too verbose — no narrative, no incident detail, `Evidence` holds only `Origin`/`Additional` links ([§2](#2-responsibilities), [§5](#5-rule-quality-standards))
   - [ ] Not too vague (checkable against a real proposal in one read)
   - [ ] Does not silently duplicate or contradict an existing `Stable` rule
6. **Approved Rule** — `Status` flips to `Stable`, the file is merged into `rules/`.
7. **Skill** — only now may a Skill in [`skills/`](../skills/) reference this rule, per the existing [ROADMAP.md](../ROADMAP.md) Phase 2 gate — nothing in this lifecycle changes that gate, it just defines what "the rule is ready" means at step 6.

A rule that fails step 5 returns to `Status: Draft`, not forward — it does not enter `rules/` until it passes. This is the same shape already implied by [RESEARCH_FRAMEWORK.md's decision sequence](../research/RESEARCH_FRAMEWORK.md#6-how-do-we-decide-the-output-type) and [ENGINEERING_META_MODEL.md's Rule Lifecycle](../ENGINEERING_META_MODEL.md#rule-lifecycle), narrowed here specifically to the Research → Rule → Skill handoff — it does not replace either, it's the concrete, checkable form of the same process.
