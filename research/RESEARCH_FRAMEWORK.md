# RESEARCH FRAMEWORK

**Folder:** [research/](.)
**Role:** Defines *how* a question in the [research queue](README.md) turns into a trustworthy output. This document does not answer any ERPNext/Frappe question itself — it defines the process that produces those answers.
**Authority:** Subordinate to [PROJECT_CHARTER.md](../PROJECT_CHARTER.md) and [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md). Where this framework references artifact types (`Rule`, `ADR`, `Anti-Pattern`, `Best Practice`, `Evidence`), the definitions in `ENGINEERING_META_MODEL.md` are authoritative — this document only adds the *procedure* for producing them from Research, it doesn't redefine what they are.

---

## 1. How do we choose a research topic?

A topic enters research for one of three reasons, in order of priority:

1. **It's blocking real work.** A decision has to be made right now (add a field, wire a hook, model a relationship) and no existing `Rule`, `Pattern`, or `ADR` covers it. This always jumps the queue — research the blocking question first, log it in the [research queue](README.md) as already in progress.
2. **It's a repeated pain point.** The same friction or mistake has come up more than once across different work. This is what the [research queue](README.md) backlog is for — topics worth investigating before they block something.
3. **It closes a gap surfaced by review.** A `Review` of a proposal (per [AGENTS.md](../AGENTS.md)'s mandatory procedure) hits a question no existing rule answers.

**What does not qualify:** a topic with no near-term application, researched purely because it might be useful someday. This mirrors [R009 — YAGNI](../rules/R009-yagni-no-speculative-infrastructure.md): speculative research is still speculative infrastructure, just in document form instead of code.

## 2. How do we know research is complete?

Research is complete — ready for a decision, not necessarily ready to become a Rule — when:

- The [Research Quality Checklist](RESEARCH_CHECKLIST.md)'s **universal minimum** section passes in full, and
- Either a Tier 1 source directly and unambiguously answers the question, **or** the question has been investigated down through Tier 3 with no direct answer found, in which case "complete" means *conclusively unresolved* rather than *answered* — that's still a valid, complete research outcome (see [When should research be rejected?](#7-when-should-research-be-rejected)).

Completeness is about the *investigation* being thorough, not about the *answer* being convenient. A research file with a well-documented "we don't have a good answer yet" in its Open Questions section is complete; a research file with a confident answer built on a single unverified blog post is not.

## 3. Which sources are considered authoritative?

See [Research Sources](#research-sources) below for the full tier system.

## 4. How should evidence be collected?

Every piece of evidence gathered during research must be recorded with enough detail to be re-verified later without repeating the investigation from scratch:

- **What tier** it belongs to (see below).
- **What claim** it supports or refutes.
- **The exact source**: a direct link, plus the version/commit/date that was actually consulted (ERPNext and Frappe both move — "the docs say X" is meaningless without knowing which version's docs).
- **The exact excerpt or finding** — a quote, a code snippet reference (file + line + commit), or a description of what was directly observed when testing.

This is the same discipline the [Evidence artifact](../ENGINEERING_META_MODEL.md#2-evidence-ev) already requires; a research file's `References` section (see the [template](RESEARCH_TEMPLATE.md)) is where that record lives day to day, before anything is promoted.

Where possible, prefer **direct verification** over reading about behavior: reproduce it on a real or scratch bench rather than trusting a description of what should happen. A claim that has been personally reproduced is stronger than the same claim read secondhand, regardless of which tier the secondhand source belongs to.

## 5. How do we compare conflicting opinions?

1. **Higher tier wins by default.** A Tier 1 source outranks a Tier 3 source when they disagree.
2. **Reproducible direct verification is the tie-breaker, even against Tier 1.** Documentation can be outdated or wrong. If a Tier 1 or Tier 2 source claims one behavior and a reproducible, documented test on a real bench shows another, the direct verification wins — but the contradiction itself must be written up explicitly (which version, exact steps, exact result), not just asserted.
3. **Same-tier conflicts that can't be resolved stay open.** If two Tier 2 sources genuinely disagree and no higher-tier source or direct test resolves it, do not force a decision. Record both positions in the Evidence Summary and list it as an Open Question. A confident-sounding Rule built on a coin flip between two equally-weighted, conflicting sources is worse than an honest "unresolved."
4. **Never silently drop the losing side.** Every conflict considered must remain visible in the research file, even after resolution — this is the same value [AGENTS.md](../AGENTS.md) already applies to Rule conflicts: state it explicitly, don't quietly pick the convenient answer.

## 6. How do we decide the output type?

Once research reaches completeness, route the outcome through this decision sequence:

```
Is the decision about THIS REPOSITORY's own structure or process
(not ERPNext/Frappe architecture)?
  → YES: write an ADR.
  → NO: continue.

Is there a concrete, reproducible Bad Pattern this prevents,
backed by Tier 1/2 evidence or a real Production Experience finding,
AND is the claim general/non-negotiable enough to justify "must"?
  → YES, and it passes the Engineering Rule bar in the
    Research Quality Checklist: write an Engineering Rule.
  → Close, but evidence is only Tier 3/4, or verified once,
    or not yet general enough: write a Best Practice instead.

Has the same bad shape been observed in two or more distinct
situations, even without a fully verified Good Pattern yet?
  → YES: write an Anti-Pattern (can coexist with a Best Practice
    or precede a future Rule once the Good Pattern is verified).

Did the investigation NOT reach a single, confident, actionable
conclusion (genuine unresolved conflict, insufficient evidence,
or the honest answer is "it depends on context with no general rule")?
  → Remains Research only. Close the file with status Resolved
    (Reference) rather than forcing a Rule/Pattern/ADR that
    doesn't deserve the confidence.
```

A single research effort can legitimately produce more than one output — e.g., an Anti-Pattern documenting the mistake plus a Best Practice recommending the alternative, with a note that it should be revisited for Rule status once the alternative has been used more than once in practice.

## 7. When should research be rejected?

Mark a research file **Rejected** (not deleted) when any of the following apply:

- The evidence directly contradicts the original premise and no valid recommendation survives (e.g., "we assumed ERPNext had no native answer" turned out to be false).
- The topic turns out to be a one-off, not a recurring decision — fails the same YAGNI bar research topics are screened against on entry (see [Question 1](#1-how-do-we-choose-a-research-topic)).
- The topic turns out to be a business-logic decision, not an architectural one — out of scope per [PROJECT_CHARTER.md's Non-Goals](../PROJECT_CHARTER.md#non-goals).
- Mid-research, it's discovered the question is already answered by an existing `Rule`, `Pattern`, or `ADR` — close as a duplicate and link to the existing artifact instead.

Rejected research is kept, not deleted, specifically so the same question is never accidentally re-researched from zero. The file states *why* it was rejected as clearly as an approved file states its recommendation.

## 8. When should research be updated?

Reopen a **Resolved** or even a **Rejected** research file when:

- New Tier 1/2 evidence emerges that contradicts it (a new ERPNext/Frappe major version, an official doc change).
- A Rule that traces back to it is deprecated (see the [Rule Lifecycle](../ENGINEERING_META_MODEL.md#rule-lifecycle)) — the research that produced it should be re-examined, not just the rule silently removed.
- A real Production Experience finding (an incident, a failed upgrade) directly contradicts the prior conclusion.

Updates are appended, not silently overwritten: add a dated changelog line at the top of the file noting what changed and why, so the history of *why the answer changed* is preserved — the same discipline [ARCHITECTURE_REVIEW.md](../ARCHITECTURE_REVIEW.md) already recommends for this repository's other living documents.

---

## Research Sources

A two-axis model: **Source Tier** ranks where to look and how much default authority a source carries on its own. **Direct Empirical Verification** is a separate, cross-cutting axis — not a place in the ranking, but a practice that can strengthen (or override) any tier, per [Question 5](#5-how-do-we-compare-conflicting-opinions).

This reconciles with, and does not contradict, the [Evidence Model](../ENGINEERING_META_MODEL.md#evidence-model) in `ENGINEERING_META_MODEL.md`: Source Tier orders where research *looks first*; Evidence Type/Strength (defined there) grades how much a specific *finding* can be trusted once it's found. A `Production Incident` is the highest-strength evidence type in that model for good reason — it's proof of consequence, not description of intent — even though "personal production experience" is not a documentation tier to consult first.

**Tier 1 — Ground Truth**
The framework's own intended behavior, in its own words and code.
- ERPNext core source code (cite exact version/commit)
- Frappe Framework core source code (cite exact version/commit)
- Official Frappe Framework documentation
- Official ERPNext documentation
- Official release notes / changelogs

**Tier 2 — Maintainer-Vetted**
Not the framework itself, but decisions the framework's own maintainers have made and accepted.
- Merged GitHub Pull Requests against `frappe/frappe` or `frappe/erpnext`
- GitHub Issues with an explicit maintainer response or confirmation

**Tier 3 — Community Corroboration**
Practitioner consensus — useful for corroboration and for surfacing patterns Tier 1/2 doesn't discuss, never sufficient alone for a Rule.
- Frappe Forum (discuss.frappe.io) threads, especially marked-solution or heavily-confirmed ones
- Well-known community-maintained apps (observed real usage patterns)
- Official Frappe/ERPNext conference talks

**Tier 4 — Unverified / Anecdotal**
Signal that a lead might exist, not evidence that it's true. Useful only to point research toward something worth checking against a higher tier.
- Generic blog posts, Reddit, unverified forum posts
- **AI-generated suggestions** (from this repository's own agents or any other AI tool) — explicitly named here because this is an AI-assisted repository: a model's unverified claim about ERPNext/Frappe behavior is Tier 4 by default until checked against Tier 1–3, never treated as evidence on its own.

**Cross-cutting — Direct Empirical Verification**
Reproducing the behavior yourself (a real or scratch bench test) or a real production incident/experience. Can be gathered at any point in the investigation. Narrow by nature (often n = 1) — strong enough to be the tie-breaker against a contradicting higher tier (see [Question 5](#5-how-do-we-compare-conflicting-opinions)), but the [Research Quality Checklist](RESEARCH_CHECKLIST.md) requires it to be reproducible and documented, not recalled from memory, before it can carry that weight.

---

## Research Workflow

```
0. Check the repository first
   Search rules/, adr/, anti-patterns/ for an existing answer.
   Found one? Link it, close the topic. Don't research what's
   already documented.
                    │
                    ▼
1. Define the question
   State it as one specific, falsifiable question — not a topic.
   ("Does a Dynamic Link field enforce referential integrity on
   delete?" not "how does Dynamic Link work?")
                    │
                    ▼
2. Tier 1 investigation
   ERPNext core → Frappe core → official documentation.
                    │
                    ▼
3. Tier 2 investigation
   Merged PRs → maintainer-confirmed GitHub Issues.
   (Skip if Tier 1 already gives a clear, unambiguous answer.)
                    │
                    ▼
4. Tier 3 investigation
   Forum → community apps → conference talks.
   Only to corroborate Tier 1/2, or when Tier 1/2 is silent.
                    │
                    ▼
5. Tier 4 signal sweep (optional)
   Blogs, Reddit, AI suggestions — only to surface leads.
   Nothing found here is cited as evidence on its own;
   it's a prompt to go verify against a higher tier.
                    │
                    ▼
6. Direct empirical verification
   Reproduce on a real or scratch bench where feasible.
   Note any relevant real production experience already observed.
                    │
                    ▼
7. Evidence review & conflict resolution
   Apply the tier ranking + empirical tie-breaker (Question 5).
   Log anything still unresolved as an Open Question.
                    │
                    ▼
8. Decision
   Route through the Question 6 decision sequence, gated by the
   Research Quality Checklist.
                    │
                    ▼
9. Repository output
   Write the resulting Rule / ADR / Anti-Pattern / Best Practice
   (or close as Research-only / Rejected). Update the research
   file's Status and the research queue entry in README.md.
```

Steps 2–6 are investigation order, not a strict gate — it's fine to jump to Tier 3 first if a forum thread is what originally raised the question, as long as the conclusion is still ultimately checked against Tier 1/2 before Step 7. Step 0 and Step 8 are never skipped.

---

## Research Deliverables

Every research file follows [RESEARCH_TEMPLATE.md](RESEARCH_TEMPLATE.md). See that file for the full section-by-section format and explanation of what belongs in each section.

## Research Quality Checklist

See [RESEARCH_CHECKLIST.md](RESEARCH_CHECKLIST.md) for the gate a research file must pass before it can be promoted to an Engineering Rule (or, at a lower bar, an ADR, Anti-Pattern, or Best Practice).
