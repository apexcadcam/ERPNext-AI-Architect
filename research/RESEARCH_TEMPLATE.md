# RESEARCH TEMPLATE

Copy this file to start new research (e.g., `research/dynamic-link-referential-integrity.md`). Every section below includes, in *italics*, what it's for and how to fill it in — delete the italic guidance as you fill each section in, or leave it if a section doesn't apply yet.

Follow the process in [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md) while filling this out — this file is the *record*, not the *procedure*.

---

# Title

*A short, specific name for the question — not the topic. "Dynamic Link Referential Integrity on Delete," not "Dynamic Link."*

## Status

*One of: `Open` (in progress) / `Resolved` (produced an output) / `Rejected` (see Framework Q7) / `Superseded` (see Framework Q8, link to the replacement). Update this line in place as status changes; add a one-line dated changelog entry directly below it whenever status or conclusion changes.*

- Date opened:
- Date closed:
- Status:

## Question

*The single, specific, falsifiable question this file answers. If you can't state it as one sentence with a clear yes/no or specific answer, it's still a topic, not a research question — narrow it further before continuing.*

## Background

*Why this question came up. What real work triggered it (Framework Q1: blocking work / repeated pain / review gap). Link to the relevant queue entry in [README.md](README.md) if it came from the backlog.*

## Existing Repository Check

*What was searched in `rules/`, `adr/`, `anti-patterns/`, and other research files before starting (Workflow Step 0). Confirms this isn't duplicate work. If something related but not identical was found, link it here.*

## ERPNext Implementation

*Tier 1 findings from ERPNext core source specifically — cite exact file path, line/function, and commit or version tag.*

## Frappe Implementation

*Tier 1 findings from Frappe Framework core source specifically — same citation discipline. Kept separate from ERPNext Implementation because the two layers can behave differently, and conflating them hides that.*

## Official Documentation

*Tier 1 findings from official Frappe/ERPNext documentation. Kept separate from the source-code sections above specifically so a doc-vs-source contradiction is visible rather than silently merged into one summary.*

## GitHub Findings

*Tier 2 findings — merged PRs and maintainer-confirmed Issues. Link directly, note the merge/confirmation status.*

## Forum Findings

*Tier 3 findings from the Frappe Forum. Note whether a thread has a marked solution or maintainer reply, which strengthens it within Tier 3.*

## Community Findings

*Tier 3 findings from community apps, conference talks, or other practitioner sources. Tier 4 leads (blogs, Reddit, AI suggestions) that were only used to point toward something verified elsewhere can be mentioned here too, clearly labeled as Tier 4 in origin.*

## Production Experience

*Direct empirical verification (Cross-cutting axis in the Framework): what was actually reproduced on a real or scratch bench, with exact steps and results — or a real incident/production observation directly relevant to the question. State the version tested against.*

## Evidence Summary

*The conflict-resolution step (Framework Q5) distilled: what do the sources agree on, where do they conflict, and which source won and why. Every conflict considered must appear here even after it's resolved — don't quietly drop the losing side.*

## Open Questions

*Anything still unresolved after investigation. If this section is non-empty, re-check against [RESEARCH_CHECKLIST.md](RESEARCH_CHECKLIST.md) before treating this research as ready for a Rule — an open question here doesn't block closing the file as Resolved (Reference) with an honest "unresolved" outcome, but it does block promotion to a Rule.*

## Final Recommendation

*The actual, plainly stated answer or position this research arrived at. One clear recommendation — not "it depends" without guidance. If the honest answer really is "it depends," say specifically on what.*

## Potential Rule Candidates

*If this research points toward one or more Engineering Rules, ADRs, Anti-Patterns, or Best Practices, draft the one-line candidate statement(s) here (not the full artifact — just the seed). Run each candidate against [RESEARCH_CHECKLIST.md](RESEARCH_CHECKLIST.md) before writing the real artifact.*

## Related Topics

*Links to other research files, existing Rules, ADRs, Anti-Patterns, or Best Practices this touches — helps prevent future duplicate research and shows how this question connects to the rest of the knowledge base.*

## References

*The full, re-verifiable citation list for everything cited above: direct link, version/commit/date accessed, and tier. This is the section that makes the research re-checkable later without repeating the investigation — see Framework Q4.*
