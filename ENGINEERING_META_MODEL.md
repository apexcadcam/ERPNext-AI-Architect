# ENGINEERING META-MODEL
## ERPNext AI Architect — Architectural Specification

**Status:** Foundational — Constitutional
**Document type:** Meta-Model Specification
**Authority:** This document defines the engineering knowledge model that every artifact in this repository — present and future — must obey. It is subordinate only to [PROJECT_CHARTER.md](PROJECT_CHARTER.md), which defines *why* this repository exists. This document defines *what kinds of things* may exist in it, *what each thing means*, and *how they relate to one another*.

This document contains no ERPNext code, no implementation guidance, no prompts, and no business-logic examples. It defines a knowledge model, not a solution.

---

# Purpose of the Meta-Model

## Why it exists

A repository that accumulates Rules, Skills, Agents, and Templates without a shared definition of what those words *mean* will eventually accumulate contradictions: two rules that say the same thing in incompatible language, a "skill" that is secretly an untested rule, an "example" that quietly became load-bearing documentation nobody dares delete. This happens not because contributors are careless, but because nothing forced them to agree, in advance, on the vocabulary.

The Meta-Model exists to make that agreement explicit and permanent. It is the layer above the knowledge itself — it does not say *what* is true about Frappe/ERPNext architecture, it says *what kind of statement* a piece of knowledge is, *how it was produced*, *what it is allowed to claim*, and *what it must connect to*. Rules describe good architecture. The Meta-Model describes what a Rule *is*.

## Why the repository needs a common language

This repository is meant to outlive any single contributor, any single AI vendor, and any single ERPNext version. Knowledge that survives that long cannot depend on shared context that lives only in someone's head. A common, enforced vocabulary is what lets:

- A new contributor tell, from a document's ID prefix alone, exactly what kind of claim it makes and how much trust it has earned.
- An AI agent programmatically distinguish an unverified `Observation` from a `Production Tested` `Engineering Rule` without reading either in full.
- Two artifacts authored years apart, by different people using different AI tools, to compose correctly because they were built against the same object model.

Without a common language, the repository degrades into exactly the thing [PROJECT_CHARTER.md](PROJECT_CHARTER.md) explicitly rejects: a prompt collection — a pile of documents whose authority is whatever the reader assumes it to be.

## Why every artifact should have one clear definition

Ambiguity compounds. If "Pattern" and "Best Practice" and "Standard" are used interchangeably by different authors, then every downstream Skill or Agent generated from them inherits that ambiguity, and every AI agent consuming them has to *guess* how much authority a given document carries. A single, non-overlapping definition per artifact type is what makes the [Knowledge Hierarchy](#knowledge-hierarchy) and the [Repository Object Model](#repository-object-model) possible at all — hierarchies and relationship graphs are only meaningful between things that are individually well-defined.

---

# Knowledge Artifact Catalog

Every artifact type below is defined by the same seven fields: **Definition**, **Purpose**, **When to Create**, **When NOT to Create**, **Example**, **Relationship with Other Artifacts**, and **Lifecycle**. Each artifact has a reserved ID prefix (formalized in [Naming Standards](#naming-standards)).

Examples given below are illustrative of the *artifact type*, not implementation guidance — they describe what such a document would be about, not its content.

### 1. Observation (`OBS`)

- **Definition:** A single, dated, unprocessed statement of something noticed during real work — a behavior, a friction point, a recurring question, a surprising outcome. Not yet judged to be true, general, or actionable.
- **Purpose:** Captures raw signal before it is lost. The entry point of the entire knowledge pipeline.
- **When to create:** The moment something strikes an engineer or agent as odd, repeated, risky, or noteworthy — even once, even without proof yet.
- **When NOT to create:** When the same underlying fact is already recorded as an `Observation`, `Evidence` record, or `Lesson Learned` — link to the existing one instead of duplicating it.
- **Example:** "Three unrelated custom apps each independently added a near-identical child table for tracking shipment status."
- **Relationship with other artifacts:** Raw input to `Evidence` and `Production Incident`. Multiple `Observation`s may later be aggregated into one `Lesson Learned`.
- **Lifecycle:** Logged → Linked (to Evidence/Incident) → Superseded-or-Archived once absorbed into a higher artifact.

### 2. Evidence (`EV`)

- **Definition:** A structured, sourced fact that supports or refutes a claim — distinct from an `Observation` in that it is verifiable and attributable to a concrete source (see [Evidence Model](#evidence-model)).
- **Purpose:** The load-bearing justification every `Engineering Rule` and `Architecture Decision Record` must cite. Without evidence, a claim is an opinion.
- **When to create:** When a claim needs to be defensible beyond one person's memory — a documented core-source-code behavior, a linked GitHub issue, a reproducible benchmark.
- **When NOT to create:** For claims that are self-evidently true from framework documentation already referenced directly — don't wrap a doc link in ceremony it doesn't need.
- **Example:** A citation of the Frappe core source showing that a given hook fires before database commit, gathered while investigating a data-consistency `Observation`.
- **Relationship with other artifacts:** Promotes an `Observation` toward a `Lesson Learned`; is the required backing for every `Engineering Rule` and most `ADR`s; may itself cite a `Knowledge Source`.
- **Lifecycle:** Collected → Attached (to Rule/ADR/Lesson) → Re-verified on major framework versions → Stale-flagged if the underlying source changes.

### 3. Production Incident (`INC`)

- **Definition:** A factual record of something that broke in a real, running system — an upgrade failure, data corruption, an outage, a security exposure — including timeline, root cause, and impact.
- **Purpose:** The highest-weight evidence type this repository has: proof, not theory, that a Bad Pattern has a real cost. See the [Evidence Model](#evidence-model).
- **When to create:** Immediately after any real incident traceable to an architectural decision (or its absence), regardless of whether a rule already covers it.
- **When NOT to create:** For near-misses caught in code review before shipping — those are `Observation`s, not incidents, until they actually occur.
- **Example:** A record that a hand-edited core file was silently reverted by `bench update`, producing three days of unexplained validation failures in production.
- **Relationship with other artifacts:** A specialized, high-authority `Evidence` type. Frequently the direct trigger for a new or revised `Engineering Rule`, and often cited in the rule's `Architectural Impact` section.
- **Lifecycle:** Reported → Root-caused → Linked to Rule/ADR (new or existing) → Closed → Archived (never deleted — incident history is permanent evidence).

### 4. Lesson Learned (`LL`)

- **Definition:** A synthesized statement of what should change in future behavior, derived from one or more `Observation`s, `Evidence` records, or `Production Incident`s.
- **Purpose:** The bridge between raw experience and generalizable knowledge — the first artifact that makes a *claim* rather than merely a *fact*.
- **When to create:** Once enough `Observation`/`Evidence`/`Incident` weight exists to state, with confidence, "we should do X differently going forward."
- **When NOT to create:** From a single unconfirmed `Observation` with no supporting evidence — premature generalization is how bad rules get written.
- **Example:** "Fixture exports that are not module-scoped tend to leak unrelated site state into version control, discovered across several incidents."
- **Relationship with other artifacts:** Synthesizes `Observation`, `Evidence`, and `Production Incident`; is the direct precursor to an `Engineering Principle` and often an `Architecture Decision Record`.
- **Lifecycle:** Captured → Reviewed → Promoted (to Principle/Rule) or Archived (if it fails review).

### 5. Engineering Principle (`PRN`)

- **Definition:** A general, durable statement of architectural values — broader and less prescriptive than a `Rule`. States *what matters and why*, not a checkable procedure.
- **Purpose:** Gives `Engineering Rule`s a shared foundation to justify themselves against, and gives judgment calls a north star when no rule directly applies.
- **When to create:** When a `Lesson Learned` (or several) reveals a value that will recur across many unrelated rules — not just one procedure.
- **When NOT to create:** When the statement is directly checkable and procedural — that belongs in an `Engineering Rule`, not a `Principle`.
- **Example:** "Prefer configuration over code, and code over core modification" — a value several concrete rules each enforce differently.
- **Relationship with other artifacts:** Generalized from one or more `Lesson Learned` entries; parent justification for one or more `Engineering Rule`s; referenced by `Standard`s and `Best Practice`s.
- **Lifecycle:** Proposed → Adopted → Stable → (rarely) Superseded by a revised principle.

### 6. Engineering Rule (`ER`)

- **Definition:** A specific, falsifiable, non-negotiable architectural statement, backed by evidence, expressed as Principle → Architectural Impact → Bad Pattern → Good Pattern → Risk Level (the format already established in `rules/`).
- **Purpose:** The **source of truth** of this repository (see [Repository Philosophy in PROJECT_CHARTER.md](PROJECT_CHARTER.md#repository-philosophy)). The one artifact type every Skill and Agent must trace back to.
- **When to create:** When a `Lesson Learned`, backed by real `Evidence`, is specific enough to check a concrete proposal against, and important enough to be non-negotiable.
- **When NOT to create:** For preferences without evidence, for one-off project decisions (use `ADR` instead), or for anything not yet validated in real use (use `Best Practice` or keep it a `Lesson Learned` until it earns Rule status).
- **Example:** [R001 — Core Isolation & Non-Invasive Extension](rules/R001-core-isolation-non-invasive-extension.md).
- **Relationship with other artifacts:** Derived from `Engineering Principle` and `Lesson Learned`; backed by `Evidence`/`Production Incident`; generates `Skill`s; referenced by `Decision Tree`s, `Checklist`s, `Pattern`s, and `Anti-Pattern`s; may be formalized by an `ADR` when adopted.
- **Lifecycle:** See the full [Rule Lifecycle](#rule-lifecycle).

### 7. Architecture Decision Record — ADR (`ADR`)

- **Definition:** A dated record of a specific architectural decision, the context that produced it, the alternatives considered, and the consequences accepted — in the standard ADR sense, scoped to *a decision*, not a general truth.
- **Purpose:** Preserves *why* a decision was made at a point in time, even if later reversed — a Rule says what to always do; an ADR says what was decided, once, and why.
- **When to create:** At the moment a non-obvious architectural choice is made that future readers will otherwise have to reverse-engineer from a diff.
- **When NOT to create:** For decisions already fully covered by an existing `Engineering Rule` with no new context — link to the rule instead of restating it.
- **Example:** A record of the decision to formalize the `R0NN` filename prefix as the canonical rule identifier rather than migrating existing files to a new scheme (see [Naming Standards](#naming-standards)).
- **Relationship with other artifacts:** Can formalize the adoption of a `Rule` or `Principle`; can record rejection of a proposed `Pattern`; is the required output of an `Architecture Review`.
- **Lifecycle:** Proposed → Accepted / Rejected → Superseded (by a later ADR, never edited in place).

### 8. Pattern (`PAT`)

- **Definition:** A named, reusable solution shape to a recurring problem, shown to work in practice — narrower and more concrete than a `Rule`, closer to "how," further from "must."
- **Purpose:** Gives engineers and agents a recognizable, reusable shape to reach for, without the full non-negotiable weight of a `Rule`.
- **When to create:** When the same good solution shape has been used successfully more than once and is worth naming for reuse.
- **When NOT to create:** For a one-off solution used exactly once with no evidence it generalizes — that's an `Example`, not a `Pattern`.
- **Example:** A named shape for exposing a computed, read-only field via a server script rather than a stored field — used across several unrelated modules.
- **Relationship with other artifacts:** Frequently the "Good Pattern" referenced inside an `Engineering Rule`; illustrated concretely by a `Template`; contrasted by an `Anti-Pattern`.
- **Lifecycle:** Identified → Documented → Validated (repeated use) → Deprecated (if a better pattern supersedes it).

### 9. Anti-Pattern (`AP`)

- **Definition:** A named, recognizable *bad* solution shape — the mirror of `Pattern` — documented specifically because it recurs and is tempting.
- **Purpose:** Lets a Rule's "Bad Pattern" be recognized and named across multiple rules and multiple contexts, instead of being re-described from scratch each time.
- **When to create:** When a mistake has been seen more than once, in more than one project, in recognizably the same shape.
- **When NOT to create:** For a mistake seen exactly once with no evidence it recurs — that belongs in a `Production Incident` record, not a named `Anti-Pattern`.
- **Example:** Hand-editing a vendored app file to add a validation — the named anti-pattern behind [R001](rules/R001-core-isolation-non-invasive-extension.md).
- **Relationship with other artifacts:** Usually the concrete "Bad Pattern" section of one or more `Engineering Rule`s; may be cited by multiple rules if the same mistake violates several principles at once.
- **Lifecycle:** Identified → Documented → Referenced (by Rules) → retired only if the underlying framework makes the mistake structurally impossible.

### 10. Standard (`STD`)

- **Definition:** A mandatory, repository-wide convention that is procedural rather than architectural — formatting, structure, required metadata, naming — as opposed to a `Rule`, which governs *design* decisions.
- **Purpose:** Keeps the repository itself internally consistent and machine-parseable, independent of any ERPNext-specific judgment.
- **When to create:** When a convention needs to be uniform across *all* artifacts of a type for tooling or consistency reasons (e.g., ID formatting, required frontmatter fields).
- **When NOT to create:** For an architectural preference about ERPNext customization — that's an `Engineering Rule`, not a `Standard`.
- **Example:** The ID and frontmatter format defined in [Naming Standards](#naming-standards) is itself a `Standard`.
- **Relationship with other artifacts:** Governs the *form* of every other artifact type; referenced by `Checklist`s used during `Review`.
- **Lifecycle:** Draft → Ratified → Stable → Revised (versioned, never silently changed) → Deprecated.

### 11. Best Practice (`BP`)

- **Definition:** A recommended, non-mandatory approach, weaker than an `Engineering Rule` — worth following by default, but not yet backed by enough evidence or consequence to be non-negotiable.
- **Purpose:** Gives a home to good advice that hasn't yet earned Rule status, without either inflating the Rule set prematurely or discarding the advice.
- **When to create:** When something works well and is worth recommending, but lacks the `Production Incident`-grade evidence a `Rule` requires.
- **When NOT to create:** Once evidence accumulates to Rule-grade — at that point, promote it and retire the `Best Practice` entry rather than maintaining both.
- **Example:** A recommendation to prefer descriptive fixture filenames over auto-generated ones for easier code review, without yet having an incident proving the cost of not doing so.
- **Relationship with other artifacts:** A candidate `Engineering Rule` in waiting; may cite the same `Evidence` a Rule would, at lower confidence; referenced by `Checklist`s.
- **Lifecycle:** Suggested → Adopted informally → Established (repeated positive use) → Promoted to Rule, or Superseded.

### 12. Decision Tree (`DT`)

- **Definition:** A structured, branching set of questions that routes a real situation to the correct `Rule`, `Pattern`, or `Skill` — an applied, navigable index over the knowledge base, not new knowledge itself.
- **Purpose:** Solves the "which of ten rules applies to my situation" problem for both humans and agents, quickly and deterministically.
- **When to create:** When multiple rules or patterns could plausibly apply to the same class of task, and choosing wrong is costly.
- **When NOT to create:** When only one rule ever applies to a given situation — a direct reference is simpler and needs no tree.
- **Example:** A tree that routes "I need to add a new field" through checks for existing native fields, then Custom Field, then Property Setter, before ever reaching "new DocType."
- **Relationship with other artifacts:** Built entirely from existing `Engineering Rule`s and `Pattern`s; consumed directly by `Skill`s and `Checklist`s; never introduces judgment a `Rule` didn't already establish.
- **Lifecycle:** Drafted → Validated against real cases → Active → Revised as the underlying rule set changes.

### 13. Checklist (`CHK`)

- **Definition:** A finite, ordered set of verifiable check items derived directly from one or more `Rule`s, `Standard`s, or `Best Practice`s, meant to be executed at a specific gate (e.g., before merge, before release).
- **Purpose:** Converts prose knowledge into a mechanical, low-judgment verification step suitable for a `Review` or an `Agent`.
- **When to create:** When a recurring gate (code review, release, migration) needs a repeatable, auditable pass/fail procedure.
- **When NOT to create:** When the check requires open-ended architectural judgment rather than a yes/no verification — that belongs in a `Review`, not a `Checklist`.
- **Example:** A pre-merge checklist verifying every new fixture is module-tagged, per [R004](rules/R004-fixture-and-metadata-integrity.md).
- **Relationship with other artifacts:** Derived from `Rule`/`Standard`/`Best Practice`; used inside `Review` and `Architecture Review`; frequently embedded inside a `Skill`.
- **Lifecycle:** Drafted → Validated → Active → Revised when the source rules change.

### 14. Skill (`SK`)

- **Definition:** A packaged, invocable procedure that composes one or more `Rule`s, `Pattern`s, `Decision Tree`s, and `Checklist`s into a repeatable capability an agent or engineer can execute for a defined task.
- **Purpose:** The first artifact layer that is *actionable* rather than purely referential — the generation target the [Knowledge Hierarchy](#knowledge-hierarchy) points to from Rules.
- **When to create:** When a specific, recurring task (e.g., "add a custom field the upgrade-safe way") is repeatedly performed and its governing rules are stable enough to package.
- **When NOT to create:** Before the underlying `Rule`s are stable — a Skill built on a shifting Rule is a maintenance trap, and never as a container for judgment the Rules don't already contain.
- **Example:** A packaged procedure for adding a field that walks through native-field discovery, then Custom Field, then Property Setter, in order, per the relevant `Decision Tree`.
- **Relationship with other artifacts:** Generated from `Rule`(s), `Pattern`(s), `Decision Tree`(s), `Checklist`(s); composed into `Agent`s; may invoke `MCP` `Tool`s during execution.
- **Lifecycle:** Generated (from Rules) → Tested against real cases → Active → Deprecated when its source rules are deprecated.

### 15. Agent (`AG`)

- **Definition:** A composition of one or more `Skill`s into a persona capable of carrying out broader, more autonomous work, plus the operating instructions for how those skills are sequenced and applied.
- **Purpose:** The highest-level generated artifact — where the knowledge base becomes a delegate capable of independent action, still fully traceable to the `Rule`s beneath it.
- **When to create:** When a class of work reliably requires composing multiple existing `Skill`s together, repeatedly, in a way worth naming and reusing.
- **When NOT to create:** As a place to add judgment, preferences, or shortcuts not already present in its constituent Skills — an Agent that "knows something extra" has broken traceability.
- **Example:** An agent persona responsible for reviewing a proposed DocType design against every relevant Skill before implementation begins.
- **Relationship with other artifacts:** Generated from `Skill`s; may call `MCP` `Tool`s to execute mechanical steps; its output should be auditable against the `Rule`s its Skills derive from.
- **Lifecycle:** Composed → Tested → Active → Retired (skills superseded or task no longer relevant).

### 16. Prompt (`PMT`)

- **Definition:** A specific instruction or phrasing used to invoke a `Skill` or `Agent` in a particular AI system — the only artifact type in this catalog that is explicitly *not* a durable source of knowledge.
- **Purpose:** Provides the minimal, model-specific glue needed to invoke durable knowledge in a given tool. Exists so vendor-specific phrasing never leaks into `Rule`s, `Skill`s, or `Agent`s themselves.
- **When to create:** Only as a thin invocation wrapper around an already-existing `Skill` or `Agent`, scoped to one AI system's calling convention.
- **When NOT to create:** As a standalone container for architectural judgment. If a prompt contains a claim not traceable to a `Rule`, that claim is undocumented knowledge masquerading as phrasing — write the `Rule` first. See [Repository Philosophy](PROJECT_CHARTER.md#repository-philosophy).
- **Example:** The specific system-prompt phrasing used to register a `Skill` inside one particular agent runtime.
- **Relationship with other artifacts:** Strictly downstream of `Skill`/`Agent`; never a source for any other artifact; expected to be the least durable, most disposable artifact in the repository.
- **Lifecycle:** Drafted → Embedded (in a specific tool integration) → Deprecated whenever the tool's calling convention changes — replacement is expected to be frequent and low-cost.

### 17. Template (`TMP`)

- **Definition:** A concrete, reusable implementation scaffold that demonstrates compliance with one or more `Rule`s or `Pattern`s — a starting point, not a finished solution.
- **Purpose:** Shortens the distance between "I understand the Rule" and "I have working scaffolding that already follows it."
- **When to create:** When a `Pattern` or `Rule` is applied often enough that re-deriving its scaffolding each time is wasted effort.
- **When NOT to create:** For a one-time, project-specific implementation with no reuse value — that belongs in that project, not this repository.
- **Example:** A scaffold for a new custom app's `hooks.py`, pre-structured to keep hook functions thin per [R007](rules/R007-thin-hooks-centralized-service-layer.md).
- **Relationship with other artifacts:** Implementation example of a `Rule`/`Pattern`; may be referenced by a `Skill` as its output scaffold; explained further by an `Example`.
- **Lifecycle:** Created → Used → Revised as the source Rule/Pattern evolves → Deprecated when superseded.

### 18. Example (`EX`)

- **Definition:** A concrete illustration of a `Rule`, `Pattern`, or `Template` applied to a specific, realistic scenario, for learning purposes only.
- **Purpose:** Builds intuition. Carries no independent authority — see [Repository Philosophy](PROJECT_CHARTER.md#repository-philosophy).
- **When to create:** When a `Rule` or `Pattern` is abstract enough that a worked scenario meaningfully speeds up understanding.
- **When NOT to create:** As a substitute for writing the `Rule` itself, or when the `Rule`'s own Bad Pattern / Good Pattern sections already make the point clearly.
- **Example:** A walk-through of applying the field-addition `Decision Tree` to one realistic (but non-production) scenario.
- **Relationship with other artifacts:** Illustrates `Rule`/`Pattern`/`Template`; explicitly non-authoritative — if it drifts from the Rule it illustrates, the Example is wrong, not the Rule.
- **Lifecycle:** Written → Reviewed → Stale-flagged when its source drifts → Updated or removed (removal is low-cost and expected).

### 19. Reference (`REF`)

- **Definition:** A pointer to external, authoritative material — official documentation, framework source, a specification — that this repository relies on but does not own.
- **Purpose:** Keeps this repository from duplicating content that already has a canonical home, while preserving a durable link to it.
- **When to create:** Whenever a `Rule`, `Evidence` record, or `Skill` depends on external material worth naming explicitly rather than linking inline every time.
- **When NOT to create:** For material that changes so fast that a static reference would mislead more than help — link inline with a date-stamped caveat instead.
- **Example:** A reference entry pointing to the Frappe Framework's official hooks documentation, cited by multiple rules.
- **Relationship with other artifacts:** Cited by `Evidence`, `Engineering Rule`, `Skill`; a specialized case of `Knowledge Source` scoped to a single document rather than an entire external body of knowledge.
- **Lifecycle:** Logged → Verified → Periodically re-verified → Stale-flagged on link rot or version drift.

### 20. MCP (`MCP`)

- **Definition:** The specification of a Model Context Protocol server: what capabilities it exposes and to which `Agent`s, and nothing about *when* or *why* to use them.
- **Purpose:** Defines the mechanical execution boundary of the system — MCP only executes `Tool`s; it holds no architectural judgment of its own, per [PROJECT_CHARTER.md](PROJECT_CHARTER.md#knowledge-hierarchy).
- **When to create:** When a capability genuinely needs to be executed against a live system (a bench, a git repo, an API) rather than merely reasoned about.
- **When NOT to create:** As a place to encode judgment about *whether* an action should be taken — that decision belongs in the `Skill` or `Agent` calling the MCP, never inside the MCP definition itself.
- **Example:** A server specification exposing a capability to run a read-only bench command, consumed by an Agent's Skill.
- **Relationship with other artifacts:** Executes one or more `Tool`s; is invoked by `Agent`s (and, transitively, `Skill`s); never generates or modifies `Rule`s, `Skill`s, or `Agent`s.
- **Lifecycle:** Defined → Implemented → Registered (to Agents) → Deprecated as capabilities change.

### 21. Tool (`TL`)

- **Definition:** A single, individually invocable capability exposed by an `MCP` server — the atomic unit of mechanical execution.
- **Purpose:** The smallest unit of "doing" in the system, as opposed to "knowing" or "deciding."
- **When to create:** When a specific mechanical action needs to be individually callable, auditable, and permission-scoped.
- **When NOT to create:** As a bundle of multiple unrelated actions — keep Tools atomic; compose them at the `Skill`/`Agent` layer.
- **Example:** A single tool that reads the current value of a specific site configuration key, with no side effects.
- **Relationship with other artifacts:** Owned by an `MCP` definition; invoked by `Skill`s/`Agent`s; never a source of architectural judgment.
- **Lifecycle:** Defined → Implemented → Registered → Deprecated/Removed.

### 22. Workflow (`WF`)

- **Definition:** A description of a multi-step process that spans multiple artifacts, tools, or people/agents over time — broader than a single `Skill`, and not necessarily fully automatable.
- **Purpose:** Documents how work actually moves through the repository or through a project (e.g., how a new Rule gets proposed, reviewed, and merged), independent of any one tool.
- **When to create:** When a process involves multiple steps, gates, or handoffs that aren't captured by any single Skill, Checklist, or Review alone.
- **When NOT to create:** For a single-step action already fully captured by one `Skill` or `Tool` — don't wrap a single action in workflow ceremony.
- **Example:** The end-to-end process by which a `Lesson Learned` becomes a merged `Engineering Rule`, spanning Research, Evidence Collection, Draft, and Architecture Review.
- **Relationship with other artifacts:** Frequently *describes* the [Rule Lifecycle](#rule-lifecycle) or similar processes; may reference `Checklist`s and `Review`s as its gates; distinct from a `Skill` in that it is not necessarily agent-executable end to end.
- **Lifecycle:** Modeled → Adopted → Active → Revised as the underlying process changes.

### 23. Research (`RS`)

- **Definition:** An open-ended, time-boxed investigation into a question the repository does not yet have an answer to — the formal container for work that precedes `Evidence` or a `Lesson Learned`.
- **Purpose:** Gives exploratory work a home and a record, separate from the confident, evidence-backed claims of a `Rule` or `Lesson Learned`.
- **When to create:** When a real question needs investigation before any claim can be made — "does X actually cause Y" — and the answer isn't yet known.
- **When NOT to create:** For questions already answered by existing `Evidence` or `Reference` material — check the knowledge base before opening new Research.
- **Example:** An open investigation into whether a specific ERPNext core query pattern causes the performance issue several `Observation`s independently flagged.
- **Relationship with other artifacts:** Consumes `Observation`s and `Knowledge Source`s as starting points; produces `Evidence` and, eventually, `Lesson Learned` as its output.
- **Lifecycle:** Opened → In Progress → Concluded (produces Evidence/Lesson Learned) → Archived.

### 24. Knowledge Source (`KS`)

- **Definition:** A registered external body of knowledge this repository draws on as a category — a documentation site, a source repository, a community forum — as distinct from `Reference`, which points to one specific document within such a source.
- **Purpose:** Tracks *where* the repository's knowledge ultimately comes from, at the level of a whole source, for provenance and staleness tracking.
- **When to create:** When a new category of external authority is relied upon repeatedly enough to be worth registering once, rather than re-describing per citation.
- **When NOT to create:** For a single one-off citation — use `Reference` for that; reserve `Knowledge Source` for sources cited repeatedly.
- **Example:** Registering "Frappe Framework GitHub repository, `develop` branch" as a standing knowledge source that multiple `Evidence` records cite against specific commits.
- **Relationship with other artifacts:** Parent of many `Reference` entries; cited by `Evidence` and `Research`.
- **Lifecycle:** Registered → Actively cited → Reviewed periodically for continued relevance → Retired if the source itself is discontinued.

### 25. Migration Guide (`MIG`)

- **Definition:** A document describing what changes for existing knowledge, rules, or implementations when a specific external dependency (an ERPNext/Frappe version, an AI platform capability) changes.
- **Purpose:** Isolates version-transition knowledge from the timeless `Rule`s themselves, so Rules don't accumulate version-conditional clutter.
- **When to create:** When a new major version (ERPNext/Frappe, or a structural change to this repository's own model) requires existing artifacts to be reviewed, revised, or reinterpreted.
- **When NOT to create:** For routine minor-version changes with no architectural impact — not every version bump needs a guide.
- **Example:** A guide describing which existing `Rule`s need review when a new major ERPNext version changes fixture import behavior.
- **Relationship with other artifacts:** References affected `Rule`s, `Pattern`s, `Skill`s directly; often produced as the output of a `Research` effort; may trigger new `ADR`s.
- **Lifecycle:** Drafted (tied to a version event) → Active during the transition window → Archived once the transition is complete and superseded knowledge is fully absorbed into updated Rules.

### 26. Review (`RV`)

- **Definition:** A record of a specific evaluation of a proposal (code, design, a new artifact) against existing `Rule`s, `Standard`s, and `Checklist`s.
- **Purpose:** The point-in-time evidence that the knowledge base was actually applied to a real decision, not just published and ignored.
- **When to create:** Each time a proposal is formally checked against the repository's rules before proceeding — the mechanism by which [AGENTS.md](AGENTS.md)'s mandatory procedure produces an artifact.
- **When NOT to create:** For informal, undocumented back-and-forth with no proposal at stake — Reviews record decisions, not casual discussion.
- **Example:** A record that a proposed DocType design was checked against the relevant `Checklist` and required one redesign before passing.
- **Relationship with other artifacts:** Applies `Rule`s/`Standard`s/`Checklist`s to a specific proposal; may surface a new `Observation` or `Lesson Learned` if the review reveals a gap in the rules themselves.
- **Lifecycle:** Requested → Conducted → Findings filed → Closed.

### 27. Architecture Review (`ARV`)

- **Definition:** A `Review` scoped specifically to a structural or repository-level decision — not a single proposal, but a design direction — typically producing an `ADR`.
- **Purpose:** The formal gate through which a candidate `Engineering Rule` or major structural change is accepted, per the [Rule Lifecycle](#rule-lifecycle).
- **When to create:** Whenever a `Rule` moves from Draft toward Approved, or whenever a change affects the Meta-Model or repository structure itself.
- **When NOT to create:** For routine proposal reviews already covered by the ordinary `Review` artifact — reserve this for structural-level decisions.
- **Example:** The architecture review that approves a drafted `Engineering Rule` and moves it to Stable status.
- **Relationship with other artifacts:** Gate between Draft and Approved in the [Rule Lifecycle](#rule-lifecycle); typically produces an `ADR`; may reference multiple `Review`s as supporting evidence.
- **Lifecycle:** Requested → Conducted → Decision recorded (as an ADR) → Closed.

### 28. Release Note (`RN`)

- **Definition:** A dated summary of what changed in the repository's own knowledge base — new/revised/deprecated Rules, Skills, Agents — analogous to software release notes, but for knowledge.
- **Purpose:** Lets consumers of this repository (human or AI) understand what changed since they last synced, without diffing every file.
- **When to create:** At each meaningful batch of changes to the knowledge base worth communicating as a unit.
- **When NOT to create:** For a single trivial typo fix with no semantic change.
- **Example:** A note summarizing that five new rules (R006–R010) were added, sourced from recent production incidents.
- **Relationship with other artifacts:** Summarizes changes across `Rule`, `Skill`, `Agent`, and other artifacts; references the underlying `ADR`s or `Architecture Review`s that authorized each change.
- **Lifecycle:** Drafted → Published → Archived (superseded by the next Release Note, never deleted).

### 29. Deprecation Notice (`DEP`)

- **Definition:** A formal, dated statement that a specific artifact (most often a `Rule`, `Pattern`, or `Skill`) is no longer recommended, including the reason and its replacement if any.
- **Purpose:** Makes obsolescence explicit and traceable, instead of letting outdated knowledge quietly rot in place and mislead future readers.
- **When to create:** The moment an artifact is superseded, contradicted by new `Evidence`, or made irrelevant by a framework change — never delete an artifact silently.
- **When NOT to create:** For an artifact simply being revised/clarified — a `Deprecation Notice` marks replacement or removal, not routine editing.
- **Example:** A notice deprecating a superseded pattern once a new ERPNext core feature makes the workaround it addressed unnecessary.
- **Relationship with other artifacts:** Attached to the artifact it deprecates; points to its replacement (`Rule`, `Pattern`, or `Skill`) if one exists; typically produced as the terminal step of the [Rule Lifecycle](#rule-lifecycle).
- **Lifecycle:** Issued → Active (grace period, if applicable) → Enforced (artifact fully retired) → Archived alongside the artifact it deprecated.

### 30. Rule Metadata Record (`RM`)

- **Definition:** A machine-authored, structured sidecar to exactly one `Engineering Rule`, holding retrieval-oriented fields the canonical Rule deliberately does not carry — category, tags, keywords, RFC 2119 requirement extraction, dependency/conflict graph edges, AI retrieval hints — per [docs/ai-retrieval/RULE_METADATA_SPECIFICATION.md](docs/ai-retrieval/RULE_METADATA_SPECIFICATION.md). Added by [ADR-0001](adr/ADR-0001-ai-retrieval-metadata-layer.md).
- **Purpose:** Lets an AI agent find, rank, and relate `Engineering Rule`s at a scale (hundreds of rules) where reading every rule file serially no longer works, without touching the frozen canonical Rule format.
- **When to create:** Whenever a new `Engineering Rule` reaches `Status: Stable` (or earlier, opportunistically) — every rule should eventually have exactly one `RM` record.
- **When NOT to create:** As a place to restate or paraphrase the canonical Rule's `Rule`, `Rationale`, `Bad Pattern`, or `Good Pattern` prose — an `RM` field either points into the canonical file or adds genuinely new structure; it never duplicates its content.
- **Example:** [rules/metadata/R001.rm.yaml](rules/metadata/R001.rm.yaml).
- **Relationship with other artifacts:** Derived from, and strictly subordinate to, exactly one `Engineering Rule` — if the two ever disagree, the `Engineering Rule` wins and the `RM` record is stale, not the reverse. Aggregated into the `Rule Retrieval Index`.
- **Lifecycle:** Generated → Validated → Synced → Stale (when the source Rule changes) → Regenerated. See [docs/ai-retrieval/RULE_METADATA_LIFECYCLE.md](docs/ai-retrieval/RULE_METADATA_LIFECYCLE.md).

### 31. Rule Retrieval Index (`RIX`)

- **Definition:** A single generated build artifact compiled from every `Rule Metadata Record`, providing the fast-path lookup structures (by category, by tag, by dependency edge, by conflict edge) an AI agent queries instead of reading every `Engineering Rule` file. Added by [ADR-0001](adr/ADR-0001-ai-retrieval-metadata-layer.md).
- **Purpose:** The concrete artifact the [Retrieval Strategy](docs/ai-retrieval/RULE_INDEX_SPEC.md) operates against — turns N individually-readable Rule files into one queryable structure.
- **When to create:** Regenerated whenever any `Rule Metadata Record` changes; never hand-edited.
- **When NOT to create:** As a place to add judgment not already present in the `RM` records it aggregates — the index is a pure, deterministic compilation, never a source of new claims.
- **Example:** [rules/index/RULE_INDEX.yaml](rules/index/RULE_INDEX.yaml).
- **Relationship with other artifacts:** Compiled entirely from `Rule Metadata Record`s; consumed by `Agent`s and `Skill`s during the retrieval phase described in [RULE_INDEX_SPEC.md](docs/ai-retrieval/RULE_INDEX_SPEC.md).
- **Lifecycle:** Compiled → Published → Recompiled (on any `RM` change) → superseded in place (a build artifact, not a versioned document — its history lives in git, not in an ID sequence).

### 32. Knowledge Document (`KD`)

- **Definition:** A single unit of content acquired from a `Knowledge Source`, carried through cleaning, normalization, and deduplication — an internally-stored, processed copy, distinct from `Reference` (`REF`), which only points at an external document without storing a processed copy of it. Added by [ADR-0002](adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md).
- **Purpose:** The pipeline's staging unit — the thing [KNOWLEDGE_EXTRACTION_SPEC.md](docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md) actually extracts from, after acquisition but before any claim has been asserted as knowledge.
- **When to create:** Every time the [Knowledge Acquisition Pipeline](docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md) pulls one page, file, thread, issue, or transcript from a `Knowledge Source`.
- **When NOT to create:** As a place to assert a fact or claim — a `KD` is raw-but-processed material, never itself a knowledge claim. That's what extraction produces from it.
- **Example:** A cleaned, normalized copy of one page from `docs.frappe.io/erpnext/v15`, deduplicated against prior crawls of the same page.
- **Relationship with other artifacts:** Acquired from a `Knowledge Source`; consumed by extraction to produce `Knowledge API`, `Pattern`, `Best Practice`, `Example`, `Workflow`, or `Engineering Rule` candidates.
- **Lifecycle:** Acquired → Cleaned → Normalized → Deduplicated → Validated → Extracted-from → Archived (retained for audit/provenance, per [KNOWLEDGE_PIPELINE.md](docs/knowledge-pipeline/KNOWLEDGE_PIPELINE.md)).

### 33. Knowledge API (`KA`)

- **Definition:** Structured API-surface knowledge — a DocType field schema, a whitelisted method signature, a hook registration contract — extracted specifically because it has a formal, checkable shape distinct from prose. Added by [ADR-0002](adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md).
- **Purpose:** Gives the pipeline a precise, machine-checkable artifact type for "what can be called, with what shape" — the kind of fact a `Pattern` or `Example` would otherwise have to restate informally every time it's referenced.
- **When to create:** When extraction encounters a DocType definition, a `@frappe.whitelist()` method, or an equivalent formal interface in official source code or documentation.
- **When NOT to create:** For narrative usage guidance — that's a `Pattern` or `Example` referencing the `KA`, not the `KA` itself.
- **Example:** The field schema of the standard `Contact` DocType, as extracted from `frappe/erpnext`'s source (see [R002](rules/R002-native-first-discovery.md)'s Good Pattern, which references exactly this doctype).
- **Relationship with other artifacts:** Extracted from a `Knowledge Document` sourced from official code/docs; referenced by `Pattern`, `Example`, and `Engineering Rule` candidates that depend on knowing an interface's exact shape.
- **Lifecycle:** Extracted → Validated → Version-scoped → Stale-flagged on source change → Re-extracted.

### 34. Knowledge Conflict (`KC`)

- **Definition:** A detected disagreement between two or more raw source claims, at the pre-rule pipeline level — distinct from the `conflicts` field [ADR-0001](adr/ADR-0001-ai-retrieval-metadata-layer.md) added to `Rule Metadata Record`, which is rule-to-rule only. Added by [ADR-0002](adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md).
- **Purpose:** Makes disagreement a first-class, queryable artifact instead of letting contradictory extracted claims silently coexist in the graph — see [KNOWLEDGE_CONFLICT_RESOLUTION.md](docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md).
- **When to create:** Whenever validation detects two claims that cannot both be true for the same scope (same version, same context) and precedence rules don't cleanly resolve it.
- **When NOT to create:** When precedence rules do resolve it deterministically (e.g., code vs. stale docs) — record the resolution on the losing claim's provenance instead of minting a standing `KC`.
- **Example:** A conflict between a forum reply describing one migration behavior and the actual `frappe/frappe` source showing different behavior as of a specific version.
- **Relationship with other artifacts:** References the conflicting `Knowledge Document`/extracted-artifact pair; resolved conflicts point to their resolution; unresolved conflicts block the affected claims from reaching `Stable`-equivalent confidence and are queued for human review.
- **Lifecycle:** Detected → Triaged → Resolved (deterministically or by human review) → Closed, retained for audit — never deleted.

### 35. Knowledge Graph Node (`KG`)

- **Definition:** A graph-index wrapper around any other artifact instance, carrying its typed relationship edges (`depends_on`, `implements`, `extends`, `replaces`, `conflicts_with`, `related_to`, `deprecated_by`, `supersedes`, `references`) — generalizes `Rule Retrieval Index`'s (`RIX`, entry 31) graph-shaped fields (`dependency_graph`, `conflict_graph`) from `Engineering Rule` alone to every artifact type. Added by [ADR-0002](adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md).
- **Purpose:** The traversable structure [RETRIEVAL_STRATEGY.md](docs/knowledge-pipeline/RETRIEVAL_STRATEGY.md) walks to expand dependencies and build reasoning chains across artifact types, not just within `rules/`.
- **When to create:** One `KG` node per artifact instance that has at least one typed relationship to another artifact.
- **When NOT to create:** As a place to hold content — a `KG` node holds edges and a pointer to the artifact it wraps, never a copy of that artifact's actual content.
- **Example:** The `KG` node wrapping `Engineering Rule` `R007`, carrying a `depends_on` edge to `R003` — the same fact `RM-0007.dependencies` already states, exposed here as a graph edge instead of a YAML field, per [KNOWLEDGE_GRAPH_SPEC.md](docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md).
- **Relationship with other artifacts:** Wraps exactly one instance of any other artifact type; the full set of `KG` nodes and edges forms the Knowledge Graph that `Rule Retrieval Index` is one pre-existing, type-scoped projection of.
- **Lifecycle:** Created (on artifact creation) → Edges updated (on relationship discovery/change) → Recomputed (on source staleness) → Archived alongside the artifact it wraps.

---

# Knowledge Hierarchy

Knowledge in this repository does not move in a single straight line — it forms along a **Formation Track** (how raw experience becomes trusted knowledge) and is then applied along an **Application Track** (how trusted knowledge becomes agent behavior). Two artifact types — `ADR` and `Review`/`Architecture Review` — cut across both tracks as gates and decision records, rather than sitting at one fixed point.

```
FORMATION TRACK                          APPLICATION TRACK
────────────────                          ─────────────────

Observation ──┐
              ├─▶ Evidence ──┐
Production    │              │
Incident ─────┘              ├─▶ Lesson Learned ─▶ Engineering Principle
                              │                              │
              Research ───────┘                              ▼
                                                     Engineering Rule ◀── (formalized by) ADR
                                                              │
                        ┌─────────────────────────────────────┼──────────────────────────┐
                        ▼                                     ▼                           ▼
                    Pattern /                           Decision Tree /              Standard /
                   Anti-Pattern                            Checklist               Best Practice
                        │                                     │                           │
                        └──────────────────┬──────────────────┴─────────────┬─────────────┘
                                            ▼                                ▼
                                          Skill ◀── (illustrated by) Template / Example
                                            │
                                            ▼
                                          Agent ◀── (invoked via, tool-specific) Prompt
                                            │
                                            ▼
                                           MCP
                                            │
                                            ▼
                                           Tool
                                            │
                                            ▼
                                     Implementation
                              (outside this repository —
                            a consuming ERPNext project's code)
```

**Cross-cutting artifacts**, not fixed to one row above:

- `Reference` and `Knowledge Source` feed `Evidence` and `Research` from outside the repository at any point.
- `Review` and `Architecture Review` gate transitions at multiple points (most formally, Draft → Approved in the [Rule Lifecycle](#rule-lifecycle)).
- `Workflow` documents how artifacts move between stages of this hierarchy, including the human/agent process around it.
- `Migration Guide` addresses what happens to any layer of this hierarchy when an external dependency (an ERPNext version, an AI platform) changes.
- `Release Note` and `Deprecation Notice` record the hierarchy's own change history over time.

**Why this hierarchy improves on the example in the task prompt:** the original example treats knowledge formation as a single line ending in `Implementation`. In practice, formation (turning experience into a trusted `Rule`) and application (turning a trusted `Rule` into agent behavior) are different processes with different failure modes — formation fails by generalizing too early from too little evidence; application fails by drifting from the Rule it was generated from. Splitting them, and giving `ADR`/`Review` an explicit cross-cutting role as gates rather than hiding them inside the arrows, makes both failure modes independently auditable. `Implementation` is deliberately drawn *outside* the repository boundary: this repository produces the knowledge and the agent capability, never the ERPNext project code itself.

---

# Rule Lifecycle

An `Engineering Rule` moves through the following stages. Each transition should be attributable to a specific artifact (an `ADR`, a `Review`, new `Evidence`) — a rule never silently changes status.

1. **Idea** — A candidate rule is proposed, typically prompted by a `Lesson Learned` or directly by a `Production Incident`. No formal artifact required yet beyond the triggering one.
2. **Research** — Open questions about the proposed rule's correctness or scope are investigated (`Research` artifact opened if the question is non-trivial).
3. **Evidence Collection** — Supporting `Evidence` is gathered and attached; a rule cannot leave this stage without at least one Evidence record (see [Evidence Model](#evidence-model)).
4. **Draft** — The rule is written in full, following the required template (Principle → Architectural Impact → Bad Pattern → Good Pattern → Risk Level), and marked `Experimental` per the [Knowledge Quality Levels](#knowledge-quality-levels).
5. **Architecture Review** — The draft is formally reviewed (`Architecture Review` artifact) against existing rules for contradiction or overlap, and against the [Design Principles](#design-principles) of this Meta-Model.
6. **Approved** — The review concludes positively (recorded as an `ADR`); the rule is merged into `rules/` and quality level moves to `Proposed` or `Verified`, depending on evidence strength.
7. **Stable** — The rule has survived real application (`Review`s citing it, no contradicting `Production Incident`s) and reaches `Production Tested` or higher.
8. **Deprecated** — New `Evidence`, a framework change, or a superior `Pattern` makes the rule obsolete; a `Deprecation Notice` is issued, pointing to a replacement if one exists.
9. **Archived** — The rule is retained permanently for historical traceability (never deleted — see [Design Principles: Traceability](#design-principles)), but excluded from active `Skill`/`Agent` generation.

A rule may re-enter **Research** from **Stable** if new evidence contradicts it — this is a revision, not a failure, and should itself be logged as a new `Observation` or `Evidence` entry.

---

# Knowledge Quality Levels

Every artifact in the Formation and Application tracks (notably `Lesson Learned`, `Engineering Principle`, `Engineering Rule`, `Pattern`, `Best Practice`, `Skill`, and `Agent`) carries one of the following quality levels, reflecting how much trust an AI agent or human should place in it:

| Level | Meaning | Promotion requires |
|---|---|---|
| **Experimental** | Drafted, not yet reviewed. May be wrong. Agents should surface, not silently apply, Experimental knowledge. | An `Architecture Review`. |
| **Proposed** | Passed initial review; not yet exercised against real work. | At least one real `Review` citing it successfully. |
| **Verified** | Confirmed correct against at least one real case, but not yet load-bearing across the repository. | Repeated citation across multiple, independent `Review`s. |
| **Production Tested** | Applied in at least one real production ERPNext environment with no contradicting `Production Incident`. | A cited `Production Incident` (positive: an incident it *prevented*) or sustained incident-free use. |
| **Community Validated** | Independently adopted and confirmed by contributors/projects beyond the originating author. | Adoption evidence from more than one independent contributor or organization. |
| **Official** | Ratified as a permanent, non-negotiable standard of this repository — reserved for the most foundational rules (e.g., core isolation). | Explicit `Architecture Review` elevating a `Production Tested` or `Community Validated` rule, recorded as an `ADR`. |

Quality level is metadata on the artifact, not a separate artifact type. Demotion (e.g., `Production Tested` → `Experimental`) is legitimate and must be triggered by a contradicting `Production Incident` or `Evidence` record, never by opinion alone.

---

# Evidence Model

Every `Engineering Rule` — and every `Lesson Learned` or `ADR` that claims a factual basis — must cite at least one `Evidence` record. An `Evidence` record has a **type**, a **source**, and a **strength**.

## Evidence Types (ordered by typical strength, strongest first)

1. **Production Incident** — A real failure observed in a running system. Highest strength: proof of consequence, not just theory.
2. **Real Customer Project** — A pattern observed working (or failing) across actual client/production implementations, short of a full incident.
3. **Upgrade Failure** — A specific, reproducible failure triggered by a framework version upgrade.
4. **Migration Failure** — A specific, reproducible failure during a data or schema migration.
5. **Security Issue** — A confirmed vulnerability or exposure traceable to an architectural choice.
6. **Performance Benchmark** — Reproducible, measured performance data supporting or refuting a claim.
7. **Core Source Code** — Direct citation of Frappe/ERPNext core source demonstrating a behavior, at a specific commit or version.
8. **GitHub Pull Request** — A merged (or explicitly rejected) PR against Frappe/ERPNext core or a related project, demonstrating intended behavior or an accepted fix.
9. **GitHub Issue** — A reported and discussed issue, weaker than a merged PR but useful for corroborating a pattern others have hit.
10. **Official ERPNext Documentation** — The official product documentation.
11. **Frappe Framework Documentation** — The official framework documentation.
12. **Community Forum** — Discussion on the official Frappe/ERPNext forum or equivalent — useful corroboration, weakest formal evidence type, never sufficient alone for a `Production Tested` or higher rule.

## Structure of an Evidence Record

Every `Evidence` entry states: the **claim** it supports, its **type** (from the list above), its **source** (a `Reference` or `Knowledge Source` citation, with URL/commit/date), and its **strength** (Corroborating / Supporting / Conclusive). A `Rule` at `Production Tested` or higher requires at least one Conclusive-strength Evidence record; a `Community Forum`-type citation alone can never reach Conclusive strength.

## Why this matters

Evidence type and strength are what let an AI agent — or a human reviewer — distinguish "this rule is backed by a documented production incident" from "this rule is backed by one forum post someone half-remembered." Without this distinction, all rules read as equally authoritative, which is precisely the ambiguity this Meta-Model exists to remove.

---

# Repository Object Model

The relationships below form the complete object graph of the repository. Each line is a directed edge: **Source → creates/generates/informs → Target**.

**Formation edges**
- `Observation` → informs → `Evidence`
- `Observation` → informs → `Production Incident`
- `Research` → produces → `Evidence`
- `Knowledge Source` → is cited by → `Reference`
- `Reference` → supports → `Evidence`
- `Evidence` → supports → `Lesson Learned`
- `Production Incident` → is a high-strength → `Evidence`
- `Production Incident` → directly triggers → `Lesson Learned`
- `Lesson Learned` → generalizes into → `Engineering Principle`
- `Lesson Learned` → directly proposes → `Engineering Rule` (Idea stage)

**Codification edges**
- `Engineering Principle` → justifies → `Engineering Rule`
- `Engineering Rule` → is formalized by → `Architecture Decision Record`
- `Engineering Rule` → contains as illustration → `Pattern` (Good Pattern) and `Anti-Pattern` (Bad Pattern)
- `Engineering Rule` → is verified via → `Architecture Review`
- `Best Practice` → is promoted to → `Engineering Rule` (when evidence strengthens)
- `Standard` → governs the form of → every other artifact type

**Application edges**
- `Engineering Rule` → generates → `Decision Tree`
- `Engineering Rule` → generates → `Checklist`
- `Engineering Rule` + `Pattern` → generate → `Skill`
- `Decision Tree` → is consumed by → `Skill`
- `Checklist` → is consumed by → `Skill` and → `Review`
- `Skill` → is illustrated by → `Template`
- `Skill` → is illustrated by → `Example`
- `Skill` → composes into → `Agent`
- `Agent` → is invoked via → `Prompt` (tool-specific, non-durable)
- `Agent` → uses → `MCP`
- `MCP` → exposes → `Tool`
- `Tool` → executes against → `Implementation` (outside repository boundary)

**Governance edges**
- `Review` → checks a proposal against → `Rule` / `Standard` / `Checklist`
- `Review` → may surface a new → `Observation`
- `Architecture Review` → gates → `Engineering Rule` (Draft → Approved)
- `Architecture Review` → produces → `Architecture Decision Record`
- `Migration Guide` → is triggered by → an external version change, and → reviews → affected `Engineering Rule`s / `Pattern`s / `Skill`s
- `Release Note` → summarizes changes to → any artifact type
- `Deprecation Notice` → retires → any artifact type, and → points to → its replacement
- `Workflow` → describes the process connecting → multiple artifact types across the Formation and Application tracks

**Invariants of the object model**

1. Every `Engineering Rule` must trace backward to at least one `Evidence` record. A rule with no evidence edge is invalid.
2. Every `Skill` must trace backward to at least one `Engineering Rule`. A skill with no rule edge is undocumented judgment and must not exist.
3. Every `Agent` must trace backward, transitively, to `Engineering Rule`s only through `Skill`s — never directly.
4. `MCP`/`Tool` never have an outgoing edge to `Engineering Rule`, `Pattern`, or any knowledge artifact — execution never generates knowledge by definition; only `Observation` (created by whoever operates the tool) can do that.
5. `Prompt` never has an outgoing edge to any artifact other than the `Skill`/`Agent` it invokes — it is a terminal, disposable node.

---

# Repository Folder Mapping

```
/
├── AGENTS.md
├── PROJECT_CHARTER.md
├── ENGINEERING_META_MODEL.md
│
├── knowledge/                     # Formation Track raw material — high churn, low authority
│   ├── observations/              # OBS-####.md
│   ├── evidence/                  # EV-####.md
│   ├── incidents/                 # INC-####.md
│   └── lessons-learned/           # LL-####.md
│
├── principles/                    # PRN-####.md — durable values, low volume
│
├── rules/                         # R#### (= ER-####) — the source of truth [existing folder]
│   ├── metadata/                  # RM-####.rm.yaml — one per rule, derived, non-authoritative [added by ADR-0001]
│   └── index/                     # RULE_INDEX.yaml (RIX) — generated, never hand-edited [added by ADR-0001]
│
├── decisions/                     # Governance records — append-only, never edited in place
│   ├── adr/                       # ADR-####.md
│   ├── reviews/                   # RV-####.md
│   └── architecture-reviews/      # ARV-####.md
│
├── patterns/                      # Named reusable shapes, positive and negative
│   ├── patterns/                  # PAT-####.md
│   └── anti-patterns/             # AP-####.md
│
├── standards/                     # STD-####.md — repository-form conventions
├── best-practices/                # BP-####.md — Rule candidates, lower evidence bar
│
├── application/                   # Rule → action translation layer
│   ├── decision-trees/            # DT-####.md
│   └── checklists/                # CHK-####.md
│
├── docs/
│   ├── ai-retrieval/               # RM/RIX specification, schema, lifecycle, retrieval strategy [added by ADR-0001]
│   ├── knowledge-pipeline/         # KD/KA/KC/KG pipeline specs: acquisition, extraction, validation,
│   │                               # conflict resolution, graph, embeddings, retrieval, refresh [added by ADR-0002]
│   ├── crawler/                    # Crawler Framework: pipeline, plugin system, connector spec, storage,
│   │                               # download/rate-limit/retry/error/cache/version policy, observability,
│   │                               # testing — architecture only, extends knowledge-pipeline's Acquisition
│   │                               # stage; reuses MCP/Tool, no new artifact type [see CRAWLER_ARCHITECTURE.md §2.3]
│   ├── runtime/                    # Core Runtime Platform: module system, plugin registry, pipeline engine,
│   │                               # event bus, config, storage abstraction, observability, CLI, lifecycle,
│   │                               # boot sequence — the execution substrate every module (Crawler included)
│   │                               # plugs into; no new artifact type [see RUNTIME_ARCHITECTURE.md §3]
│   └── studio/                     # AI Architect Studio: permanent, purely observational Runtime module —
│                                   # a real-time Engineering Intelligence Dashboard built entirely from
│                                   # Event Bus subscriptions; capabilities_provided: [] always, structurally
│                                   # cannot be depended on or control anything [see STUDIO_ARCHITECTURE.md §4]
│
├── skills/                        # SK-####/ — one folder per skill (rule + procedure + metadata)
├── agents/                        # AG-####.md — persona + composed skill references
├── prompts/                       # PMT-####.md — tool-specific, explicitly non-authoritative
│
├── mcp/                           # Execution layer only
│   ├── servers/                   # MCP-####.md
│   └── tools/                     # TL-####.md
│
├── runtime/                       # Reserved, not yet created — the Core Runtime Platform every module
│                                   # (including crawler/) plugs into: module system, plugin registry,
│                                   # pipeline engine, event bus, DI container, storage adapters, CLI
│                                   # entry point ("architect") — see docs/runtime/RUNTIME_ARCHITECTURE.md
│
├── crawler/                       # Reserved, not yet created — Source Connector plugin code
│                                   # (crawler/sources/<name>/), structurally a Tool-like execution
│                                   # boundary per docs/crawler/CRAWLER_ARCHITECTURE.md §2.3; not populated;
│                                   # registers as a module with runtime/ once both are implemented
│
├── studio/                        # Reserved, not yet created — AI Architect Studio's own module code
│                                   # and materialized view-model storage namespace; registers as an
│                                   # ordinary module with runtime/ per docs/studio/STUDIO_INTEGRATION.md;
│                                   # provides zero capabilities, consumes Event Bus subscriptions only
│
├── workflows/                     # WF-####.md — cross-artifact process documentation
├── templates/                     # TMP-####.md (or scaffold directories referenced by ID)
├── examples/                      # EX-####.md — explicitly non-authoritative
├── references/                    # REF-####.md
├── research/                      # RS-####.md
├── knowledge-sources/             # KS-####.md — see knowledge-sources/README.md for the single-registry approach
│   └── pipeline/                  # KD/KA/KC/KG instance storage, once the pipeline is implemented [reserved by ADR-0002, not populated]
│       ├── raw/                   # immutable raw bytes, content-addressed [layout: docs/crawler/STORAGE_LAYOUT.md]
│       ├── documents/             # Knowledge Document instances (envelope + normalized text + structural metadata)
│       └── cache/                 # ETag/resume state — expendable, never a source of truth
├── migrations/                    # MIG-####.md
│
└── changelog/                     # Repository's own version history
    ├── release-notes/             # RN-####.md
    └── deprecations/              # DEP-####.md
```

**Why this structure:**

- **Every artifact type gets exactly one folder** so that an artifact's location alone communicates its type — no artifact should require opening the file to know what kind of claim it makes.
- **`knowledge/` is separated from `rules/`** because Formation Track material is expected to be high-volume, informal, and frequently superseded — mixing it with the curated, load-bearing `rules/` folder would dilute the trust `rules/` currently carries.
- **`decisions/` is grouped and marked append-only** because ADRs, Reviews, and Architecture Reviews are historical records — they document what was decided when, and must never be retroactively edited, only superseded.
- **`patterns/` splits positive and negative** so an engineer or agent scanning the folder can immediately tell which subfolder describes what *to* do versus what *not* to do, without reading file contents.
- **`application/` is a distinct top-level concept from `rules/`** because Decision Trees and Checklists are *derived, navigable indexes* over the Rules, not new sources of truth — keeping them visually and structurally separate reinforces that Rules remain the one source of truth per the [Knowledge Hierarchy](#knowledge-hierarchy).
- **`mcp/` is isolated and split into `servers/` and `tools/`** to make the "MCP only executes, never decides" principle structurally visible — nothing in `mcp/` should ever need to reference `rules/` directly.
- **`prompts/` is separated from `skills/` and `agents/`** so that vendor-specific, disposable material never gets mistaken for durable knowledge, and can be pruned aggressively without touching anything durable.
- **`changelog/` sits apart from `decisions/`** because release notes and deprecation notices summarize *what changed*, while ADRs and Reviews record *why a specific decision was made* — different audiences, different update cadence.
- **`rules/` keeps its existing top-level position and existing filenames**, unchanged by this Meta-Model, to avoid an unnecessary breaking migration of the repository's most load-bearing content — see [Naming Standards](#naming-standards) for how its existing `R0NN` convention reconciles with the ID scheme below.

---

# Naming Standards

Every artifact instance has a stable, permanent ID: **`PREFIX-NNNN`**, four-digit, zero-padded, sequential within its prefix, never reused even after archival.

| Artifact | Prefix | Example |
|---|---|---|
| Observation | `OBS` | `OBS-0001` |
| Evidence | `EV` | `EV-0001` |
| Production Incident | `INC` | `INC-0001` |
| Lesson Learned | `LL` | `LL-0001` |
| Engineering Principle | `PRN` | `PRN-0001` |
| Engineering Rule | `ER` | `ER-0001` |
| Architecture Decision Record | `ADR` | `ADR-0001` |
| Pattern | `PAT` | `PAT-0001` |
| Anti-Pattern | `AP` | `AP-0001` |
| Standard | `STD` | `STD-0001` |
| Best Practice | `BP` | `BP-0001` |
| Decision Tree | `DT` | `DT-0001` |
| Checklist | `CHK` | `CHK-0001` |
| Skill | `SK` | `SK-0001` |
| Agent | `AG` | `AG-0001` |
| Prompt | `PMT` | `PMT-0001` |
| Template | `TMP` | `TMP-0001` |
| Example | `EX` | `EX-0001` |
| Reference | `REF` | `REF-0001` |
| MCP | `MCP` | `MCP-0001` |
| Tool | `TL` | `TL-0001` |
| Workflow | `WF` | `WF-0001` |
| Research | `RS` | `RS-0001` |
| Knowledge Source | `KS` | `KS-0001` |
| Migration Guide | `MIG` | `MIG-0001` |
| Review | `RV` | `RV-0001` |
| Architecture Review | `ARV` | `ARV-0001` |
| Release Note | `RN` | `RN-0001` |
| Deprecation Notice | `DEP` | `DEP-0001` |
| Rule Metadata Record | `RM` | `RM-0001` |
| Rule Retrieval Index | `RIX` | n/a — singleton build artifact, not sequence-numbered |
| Knowledge Document | `KD` | `KD-0001` |
| Knowledge API | `KA` | `KA-0001` |
| Knowledge Conflict | `KC` | `KC-0001` |
| Knowledge Graph Node | `KG` | `KG-0001` |

**Reconciling `RM-####` with `R0NN`/`ER-####`.** An `RM` record's number always matches the rule it describes: `RM-0001` is the metadata record for `R001` / `ER-0001`, `RM-0002` for `R002` / `ER-0002`, and so on — the same numeric-sequence equivalence used for `ER-####`, extended one layer further. A rule with no `RM` record yet simply has a gap in the `RM` sequence at that number; gaps are expected during rollout and are not renumbered once the record is created.

**Reconciling `ER-####` with the existing `rules/R0NN-*.md` convention.** The `rules/` folder already contains files named `R001`–`R010` and is in active use before this Meta-Model was written. Rather than renaming existing files — a disruptive change with no architectural benefit — the two schemes are declared equivalent by shared numeric sequence: `R001` **is** `ER-0001`, `R002` **is** `ER-0002`, and so on. `R0NN` remains the canonical filename prefix inside `rules/` (short, established, already linked from `AGENTS.md`); `ER-####` is the formal cross-reference ID used by every other artifact type (an `ADR`, `Skill`, or `Checklist` citing a rule uses `ER-0001`, which resolves to `rules/R001-*.md`). This mapping itself should be recorded as an `ADR` the first time a new artifact type is added to the repository, so the reconciliation is traceable rather than assumed.

**ID rules:**
- IDs are assigned sequentially per prefix, at creation time, and are never reassigned or reused.
- An artifact's filename should embed its ID (e.g., `ER-0001-core-isolation-non-invasive-extension.md`), with a human-readable slug following the ID for discoverability — mirroring the existing `rules/` convention.
- Cross-references between artifacts (e.g., a `Skill` citing the `Rule`s it derives from) always use the ID, never the slug alone — slugs may be edited for clarity; IDs may not.

---

# Design Principles

The Meta-Model — and every artifact governed by it — must satisfy the following, simultaneously:

- **Single Source of Truth.** Every fact has exactly one authoritative artifact. `Engineering Rule` is the source of truth for architectural claims; nothing else may silently duplicate or contradict it (see [Repository Philosophy in PROJECT_CHARTER.md](PROJECT_CHARTER.md#repository-philosophy)).
- **Knowledge Reuse.** Lower-effort artifacts (`Skill`, `Template`, `Checklist`) are always compositions of higher-authority artifacts, never independent re-derivations — this is what the [Repository Object Model](#repository-object-model)'s invariants enforce structurally.
- **AI Independence.** No artifact's validity depends on a specific AI vendor or model. `Prompt` is the sole vendor-coupled artifact type, and it is explicitly disposable and non-authoritative.
- **Vendor Independence.** The same applies beyond AI — no artifact should assume a specific IDE, hosting platform, or proprietary tool it cannot function without.
- **ERPNext Upgrade Safety.** Every artifact type that touches implementation (`Pattern`, `Template`, `Skill`) must be checkable against the upgrade-safety criteria already established in [PROJECT_CHARTER.md](PROJECT_CHARTER.md#upgrade-safe-principles).
- **Traceability.** Every artifact's `Relationship with other artifacts` field must be real and followable — from any `Skill` back to the `Evidence` that ultimately justifies it, with no missing links.
- **Extensibility.** New artifact types may be added to this catalog, but only through the same rigor this document itself was produced under — proposed, reviewed, and recorded as an `ADR` against this Meta-Model.
- **Minimal Duplication.** If two artifacts say the same thing, one must be deprecated in favor of the other — the [Repository Object Model](#repository-object-model)'s promotion edges (`Best Practice` → `Engineering Rule`) exist precisely to resolve this over time rather than let duplicates accumulate.
- **Machine Readability.** IDs, prefixes, and required frontmatter fields (per [Naming Standards](#naming-standards)) exist so tooling — including AI agents — can parse the knowledge base structurally, not just read it as prose.
- **Human Readability.** Machine readability must never come at the cost of a human being able to open any file and understand it without tooling — IDs augment slugs, they never replace them.
- **Long-Term Maintainability.** Nothing in this model assumes constant maintenance attention. Deprecation, archival, and quality-level demotion are first-class, low-friction operations specifically so that stale knowledge decays visibly rather than rotting invisibly.

---

# Future Compatibility

This repository's knowledge must remain valid and usable even if every current tool around it changes. Concretely:

- **If Claude disappears** — every `Rule`, `Pattern`, `Skill`, and `Agent` remains fully readable and applicable by a human or by any other AI system, because none of them are written in a Claude-specific format. Only `Prompt` artifacts, already scoped as disposable, would need replacement.
- **If Cursor (or any specific IDE/agent runtime) disappears** — the same holds: `MCP` and `Tool` definitions describe capabilities, not a specific runtime's calling convention, and `Prompt` is the sole integration-specific layer.
- **If GPT (or any model) changes underlying behavior** — `Rule`s and `Skill`s do not encode model-specific behavior quirks; they encode architectural judgment, which is model-independent by construction (see [AI First Principles in PROJECT_CHARTER.md](PROJECT_CHARTER.md#ai-first-principles)).
- **If new AI models appear** — they onboard by reading `Rule`s, `Skill`s, and `Agent`s directly, and by authoring new `Prompt` artifacts for their own calling convention — no other layer needs to change.
- **If MCP (the protocol) changes** — only the `MCP`/`Tool` layer is affected. Because [Repository Object Model](#repository-object-model) invariant 4 guarantees `MCP`/`Tool` never carry knowledge, a protocol change is a mechanical migration with zero knowledge loss.
- **If ERPNext v16/v17/v18 (or beyond) arrives** — the `Migration Guide` artifact type exists specifically for this. Affected `Rule`s are re-reviewed (re-entering the [Rule Lifecycle](#rule-lifecycle) at Research if needed), not silently assumed to still hold. Rules that depend on version-specific behavior are expected to say so explicitly in their `Evidence`, making the blast radius of a version change discoverable rather than surprising.

The general mechanism that makes all of the above true is the same one stated in [Design Principles](#design-principles): knowledge (`Rule`, `Principle`, `Pattern`, `Standard`) is kept structurally separate from execution (`MCP`, `Tool`) and from vendor glue (`Prompt`). Technology churns at the execution and glue layers constantly; this Meta-Model is designed so that churn never has to touch the knowledge layer to be absorbed.

---

# Final Requirement

This document is the **Constitution** of the ERPNext AI Architect repository. Every `Rule`, `Skill`, `Agent`, `MCP` definition, `Template`, piece of `Documentation`, and future AI system built in this repository must be expressible in terms of the artifact types, relationships, and lifecycles defined above. An artifact that does not fit this model is either a sign the model needs a deliberate, reviewed extension (see [Design Principles: Extensibility](#design-principles)) — or a sign the artifact does not belong in this repository.

This document contains, deliberately, no implementation, no ERPNext code, no prompts, and no business-logic examples. Its only subject is the shape of the knowledge itself. Amending it should be treated with the same weight as amending [PROJECT_CHARTER.md](PROJECT_CHARTER.md) — a deliberate, explicit, reviewed change, never folded quietly into an unrelated commit.
