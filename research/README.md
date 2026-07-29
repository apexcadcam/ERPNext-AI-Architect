# research/

## Purpose

Scratchpad for open questions about Frappe/ERPNext behavior, investigated *before* they're confident enough to become an Engineering Rule. The bar here is much lower than `rules/` — half-finished notes, dead ends, and "still not sure" are all fine.

## How to do research here

- **[RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md)** — the process: how to pick a topic, the source-tier ranking, the investigation workflow, and how a finished research file becomes a Rule / ADR / Anti-Pattern / Best Practice (or stays Research-only, or gets rejected).
- **[RESEARCH_TEMPLATE.md](RESEARCH_TEMPLATE.md)** — copy this to start a new research file. Every required section, explained inline.
- **[RESEARCH_CHECKLIST.md](RESEARCH_CHECKLIST.md)** — the gate a research file must pass before it's promoted to a Rule (or, at a lower bar, an ADR/Anti-Pattern/Best Practice).

## What belongs inside

One file per topic or question, started from `RESEARCH_TEMPLATE.md`. Notes, links to source/docs, things tried, things that turned out to be wrong.

## What does NOT belong inside

A finished, confident architectural statement — once a question is answered with enough evidence (checked against `RESEARCH_CHECKLIST.md`), write it up as a Rule in [`rules/`](../rules/) and close the research file (link to the rule it produced rather than duplicating the conclusion).

## Typical lifecycle

Opened when a real question comes up while building something → investigated per `RESEARCH_FRAMEWORK.md` → closed either by producing a Rule/ADR/Anti-Pattern/Best Practice, by staying Research-only, or by being rejected (left in place for the record, not deleted — see `RESEARCH_FRAMEWORK.md`).

---

## Initial Research Queue

Not yet researched. This is a backlog, not findings — each topic below is a candidate question, not an answer.

| Topic | Why it's worth researching | Status |
|---|---|---|
| Contact | How ERPNext models a Contact vs. custom "person" doctypes people are tempted to invent | Not started |
| Dynamic Link | When a Dynamic Link field is the right native tool instead of a hardcoded foreign key | Not started |
| Hooks | Full scope of `hooks.py` extension points and which ones are safe across upgrades | Not started |
| DocTypes | Native DocTypes that are commonly duplicated unnecessarily | Not started |
| Permissions | Role Permission Manager / User Permissions vs. hand-written `has_permission` checks | Not started |
| Workspaces | How Workspaces should be customized without breaking on upgrade | Not started |
| Server Scripts | Where Server Scripts are safe vs. where they become an unmaintainable liability | Not started |
| Fixtures | Scoping fixture exports correctly; what leaks in if you're not careful | Not started |
| Custom Fields | Custom Field vs. Property Setter vs. new DocType — the actual decision boundary | Not started |
| Website | Customizing the ERPNext/Frappe website layer without touching core | Not started |
| Native-First Discovery | The concrete "how" behind [R002](../rules/R002-native-first-discovery.md)'s discovery principle | Resolved → [RQ-0001](RQ-0001-native-first-discovery.md) |
| Controller Lifecycle Hook Population | Which classes a lifecycle hook could appear on, and whether that set is statically derivable — the precondition for the Evidence Platform's one unmeasurable category | Resolved → [RQ-0002](RQ-0002-controller-lifecycle-hook-population.md) |

Add new topics to this table as questions come up. When a topic is investigated, either promote it to a Rule and mark it `Done → R0NN`, or leave a research note in this folder and link it here.
