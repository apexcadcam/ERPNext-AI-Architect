# RESEARCH QUALITY CHECKLIST

**Purpose:** The gate between a completed research file and a repository artifact. This checklist exists specifically to keep weak or opinion-based conclusions out of `rules/`, `adr/`, `anti-patterns/`, and any future `Best Practice` collection — see [RESEARCH_FRAMEWORK.md, Question 6](RESEARCH_FRAMEWORK.md#6-how-do-we-decide-the-output-type).

Self-administered — check every box honestly against the [research file](RESEARCH_TEMPLATE.md) before promoting it. **A Rule that would fail its own checklist today should be demoted back to Best Practice or Research immediately if that's ever discovered — being already merged is not a reason to leave it in place.**

---

## Universal Minimum

*Required before ANY output beyond "remains Research only" — Rule, ADR, Anti-Pattern, or Best Practice all require this bar first.*

- [ ] The **Question** is specific, scoped, and falsifiable — not a general topic.
- [ ] **Existing Repository Check** was actually performed and is documented — no duplicate Rule, ADR, Anti-Pattern, or Best Practice already covers this.
- [ ] At least one Tier 1 or Tier 2 source was directly consulted and is cited with a link, version/commit, and date.
- [ ] Every conflicting source found is documented in the **Evidence Summary** — none were quietly dropped because they were inconvenient.
- [ ] **Open Questions** is either empty, or every remaining item is explicitly judged non-blocking for the specific output being proposed.
- [ ] **Final Recommendation** states a single, plain position — not an unresolved "it depends" with no guidance attached.

## Additional Bar — Engineering Rule

*The highest bar in the repository. All Universal Minimum items, plus:*

- [ ] Backed by a concrete Bad Pattern that has actually occurred or is directly demonstrable — a real incident, a reproducible test, or unambiguous source-code proof. Not hypothetical.
- [ ] Backed by a concrete Good Pattern that has been **directly verified to work**, not just read about (Production Experience section is filled in, not left as "should work").
- [ ] Evidence includes at least one Tier 1 source, or a reproducible Production Experience finding with exact steps and version.
- [ ] The claim is general and non-negotiable enough to justify "must" — a one-off preference belongs in Best Practice, not here (see [R009](../rules/R009-yagni-no-speculative-infrastructure.md)).
- [ ] Does not silently contradict an existing Stable rule. If it does, that conflict is named explicitly and the existing rule is flagged for its own review — never overridden quietly.
- [ ] Written in the required Rule template: Principle, Architectural Impact, Bad Pattern, Good Pattern, Risk Level (per [AGENTS.md](../AGENTS.md)).

## Lower Bar — Best Practice

*All Universal Minimum items, and explicitly nothing more. Use this bar deliberately, not as a shortcut around the Rule bar:*

- [ ] The approach works and is recommended, but evidence is Tier 3/4 only, or verified in fewer instances than the Rule bar requires.
- [ ] The file notes what additional evidence would be needed to promote it to a Rule later.

## Bar — Anti-Pattern

*All Universal Minimum items, plus:*

- [ ] The same bad shape has been observed in **two or more** distinct situations or contexts — a single occurrence is a note in a Rule's own Bad Pattern section, not a standalone Anti-Pattern.
- [ ] A verified Good Pattern is not required yet — a clear description of the mistake and why it's tempting is sufficient on its own.

## Bar — ADR

*All Universal Minimum items, plus:*

- [ ] The decision is about **this repository's own structure or process**, not ERPNext/Frappe architecture — if it's the latter, route it through the Rule/Best Practice/Anti-Pattern bars instead.
- [ ] Alternatives that were considered and not chosen are documented, not just the final decision.

## Automatic Rejection Triggers

*Any one of these means the research is marked Rejected (see [RESEARCH_FRAMEWORK.md, Question 7](RESEARCH_FRAMEWORK.md#7-when-should-research-be-rejected)) regardless of how much of the checklist above otherwise passes:*

- [ ] Evidence directly contradicts the original premise and no valid recommendation survives.
- [ ] The topic turns out to be a one-off, not a recurring decision.
- [ ] The topic turns out to be business logic, not architecture — out of scope per [PROJECT_CHARTER.md's Non-Goals](../PROJECT_CHARTER.md#non-goals).
- [ ] Mid-research, an existing Rule/Pattern/ADR is found to already answer the question.

---

**If any Universal Minimum box is unchecked:** the research is not ready for any output — return to the relevant step in the [Research Workflow](RESEARCH_FRAMEWORK.md#research-workflow).

**If Universal Minimum passes but no type-specific bar is met:** the honest outcome is Research-only. Close the file as `Resolved` with the Final Recommendation intact, and revisit later if new evidence arrives (see [RESEARCH_FRAMEWORK.md, Question 8](RESEARCH_FRAMEWORK.md#8-when-should-research-be-updated)).
