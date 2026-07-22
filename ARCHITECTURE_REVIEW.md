# ARCHITECTURE REVIEW
## ERPNext AI Architect — Repository Coherence Review

**Reviewer role:** Lead Software Architect (review only — no code, no business logic, no repository changes made in the course of this review)
**Scope:** Root structure, folder structure, README strategy, AGENTS.md, and the Research → Rules → Skills → Agents → MCP lifecycle.
**Reviewed against:** Solo-developer maintenance, AI-agent friendliness, long-term simplicity.

---

## Strengths

- **The phase order is sound and correctly enforced structurally, not just by convention.** `research/`, `rules/`, `skills/`, `agents/`, `mcp/` exist in the filesystem in the same order they're allowed to be populated, and the three not-yet-active folders (`skills/`, `agents/`, `mcp/`) say so explicitly in their own README rather than silently sitting empty with no explanation. An AI agent or a new contributor can't accidentally start in the wrong folder.
- **`rules/` is genuinely the load-bearing artifact, and everything else currently defers to it.** No file outside `rules/` currently contains architectural judgment of its own — `ROADMAP.md`, the placeholder READMEs, and `AGENTS.md` all point back to `rules/` rather than restating or shadowing it. That's the single most important property this repository needs and it currently holds.
- **Nothing is empty without justification.** Every folder that exists has a README explaining why it exists even while empty, which directly satisfies "avoid files that will remain empty" — a README documenting intent is not empty content, it's the folder's only necessary content at this stage.
- **The `R0NN` filename convention in `rules/` is simple, sortable, and has ten real files using it consistently.** It works, and nothing about the review below requires touching it.
- **`ADR` and `anti-patterns/` are correctly modeled as cross-cutting, not sequential phases.** `ROADMAP.md` states this explicitly instead of forcing them into the five-phase line, which avoids a subtle but common mistake (treating every folder as if it belongs to exactly one phase).

## Weaknesses

- **`ENGINEERING_META_MODEL.md` (659 lines, ~65KB) is scoped for an organization, not a solo developer.** It defines 29 distinct artifact types, a four-digit zero-padded ID scheme (`OBS-0001`, `EV-0001`, ...), a six-level Knowledge Quality promotion table (Experimental → Proposed → Verified → Production Tested → Community Validated → Official), and an Evidence strength model with 12 evidence types. None of this is reflected anywhere in the actual repository — there is no `knowledge/observations/`, no `decisions/`, no `application/` folder, no ID-prefixed filename anywhere. The document describes a repository that does not exist yet and may never need to at this scale. This is the single largest coherence gap in the repository: a newcomer (human or AI) reading the meta-model first would expect a much larger, more bureaucratic structure than the eight folders actually present.
- **`AGENTS.md` predates `ROADMAP.md` and `ENGINEERING_META_MODEL.md` and hasn't been updated to reflect them.** It still only describes the rule-checking procedure against `rules/`; it says nothing about the phase gate (don't generate a Skill before Rules are stable, etc.), doesn't mention `research/`, and doesn't reference `ROADMAP.md` at all. Any AI agent that reads only `AGENTS.md` — which is the file most coding assistants auto-load — will not learn about the mandatory phase order unless it separately discovers `ROADMAP.md`.
- **No root `README.md` exists.** GitHub (and most repository browsers) render `README.md` as the default landing page, not `AGENTS.md`. Right now a human visitor landing on the repository sees a raw file listing with no orientation, even though four well-written orientation documents (`AGENTS.md`, `PROJECT_CHARTER.md`, `ENGINEERING_META_MODEL.md`, `ROADMAP.md`) already exist.
- **The naming schemes disagree with each other.** `rules/` uses `R0NN`. `ENGINEERING_META_MODEL.md` specifies `ER-0001` as the formal ID and reconciles the two only in prose ("`R001` **is** `ER-0001`"), noting the reconciliation "should be recorded as an ADR" — which hasn't happened. `adr/` is empty. The one decision most worth capturing as this repository's first ADR doesn't have one yet.
- **Placeholder-folder READMEs partially duplicate `ROADMAP.md`.** `skills/README.md`, `agents/README.md`, and `mcp/README.md` each restate, in their own words, why the folder isn't active yet — the same dependency logic `ROADMAP.md` already states in full, with justification. It's not a large duplication, but for a single maintainer it's two places to keep in sync if the phase logic ever changes.

## Things to Simplify

- **Treat `ENGINEERING_META_MODEL.md` as an aspirational reference, not a current spec, and say so at the top of the file.** A one-paragraph "Implementation status" note — stating plainly that only `Rule`, `ADR`, `Anti-Pattern`, `Template`, `Skill`, `Agent`, and `MCP` are active folders today, and that the remaining ~22 artifact types (Observation, Evidence, Lesson Learned, Standard, Best Practice, Decision Tree, Checklist, Prompt, Example, Reference, Tool, Workflow, Research-the-artifact-type, Knowledge Source, Migration Guide, Review, Architecture Review, Release Note, Deprecation Notice) are deferred until the repository's scale actually justifies them — would resolve most of the coherence gap without deleting any of the thinking already done.
- **Drop the ID-prefix scheme (`OBS-0001` etc.) from active use entirely for now.** It's designed for multi-contributor traceability at volume. A solo developer gets nothing from zero-padded sequential IDs that a filename and a `git log` don't already give them. Keep the scheme documented in the meta-model as a future option; don't adopt it in practice until there's a second contributor or a real volume problem it solves.
- **Drop the six-level Knowledge Quality promotion table from active use.** "Community Validated" specifically requires more than one independent contributor or organization — structurally inapplicable to a one-person repository. `Experimental` vs. `Stable` (already implied by the Rule Lifecycle) is enough resolution at this scale.
- **Shorten `skills/README.md`, `agents/README.md`, and `mcp/README.md` to a pointer, not a restatement.** Each can say, in three lines: "Not active yet — see `ROADMAP.md` Phase N for why and when," plus its one-line "what belongs here once active." Let `ROADMAP.md` be the single place the *dependency reasoning* lives.

## Things to Rename

None. Root filenames (`AGENTS.md`, `PROJECT_CHARTER.md`, `ENGINEERING_META_MODEL.md`, `ROADMAP.md`) and folder names (`research`, `rules`, `skills`, `agents`, `mcp`, `templates`, `adr`, `anti-patterns`) are each self-descriptive and consistent with their contents. Renaming any of them would cost more (broken cross-references — every document above links the others by exact filename) than it would gain in clarity.

## Things to Remove

Nothing needs to be deleted. Every existing file earns its place. The recommendation is **scope reduction inside `ENGINEERING_META_MODEL.md`** (marking most of the artifact catalog as deferred, per "Things to Simplify" above), not removal of the document or the folders — the eight folders on disk are already the right, minimal set.

## Things to Keep

- The five-phase order (`Research → Rules → Skills → Agents → MCP`) exactly as specified — evaluated below, it's correct and shouldn't change.
- `rules/` as the single source of truth, and the `R0NN` filename convention as-is.
- The per-folder README pattern for `research/` and `rules/` specifically — these two are *active*, and their READMEs carry real, non-duplicated operational content (the research queue; the rule-writing procedure). This pattern earns its keep for active folders even if it's trimmed for dormant ones.
- `ROADMAP.md` as the authoritative home for phase-dependency reasoning.
- `ADR` and `anti-patterns/` as cross-cutting (non-phase) folders — this modeling choice is correct and should not be forced into the five-phase sequence.

## Final Recommendations

1. **Add a root `README.md`.** Short — a table of contents pointing to `AGENTS.md` (for AI agents), `PROJECT_CHARTER.md` (vision), `ENGINEERING_META_MODEL.md` (structural spec), and `ROADMAP.md` (current phase + what's next). This is the single highest-leverage addition available: it costs one small file and fixes the "no landing page" gap for both human visitors and any tool that only checks `README.md`.
2. **Add an "Implementation status" note to the top of `ENGINEERING_META_MODEL.md`** naming which artifact types are active now (backed by a real folder) versus deferred (documented for the future, not yet needed). This is the fix for the review's biggest weakness and requires no deletion — the full model stays intact as a reference for when the repository actually grows into it.
3. **Update `AGENTS.md`** to reference `ROADMAP.md` and state the phase gate explicitly (e.g., "before proposing a Skill, confirm the relevant Rules exist and are stable; before proposing an Agent, confirm the relevant Skills exist" — mirroring the mandatory-procedure style already used for rule-checking). Also add one sentence disambiguating `AGENTS.md` (operating instructions for whichever AI tool is working in this repo, a cross-tool convention many coding assistants auto-load) from `agents/` (the Phase 3 folder for composed-persona knowledge artifacts) — same word, two different meanings, worth one explicit sentence rather than leaving it implicit.
4. **Write the first real ADR**: the decision to keep `R0NN` as the canonical filename convention in `rules/` and defer the `ER-####` ID scheme (and the rest of the ID-prefix system) until the repository has more than one contributor. This is low-effort, immediately useful, and gives `adr/` its first real content instead of sitting empty indefinitely.
5. **Trim the three dormant-folder READMEs** (`skills/`, `agents/`, `mcp/`) to a short pointer into `ROADMAP.md` rather than a restated rationale, once #1–#3 above are done — low priority, purely a duplication cleanup.

### On the lifecycle itself

`Research → Engineering Rules → Skills → AI Agents → MCP Tools` is correct as specified and should not change. Each stage only ever *composes* the stage before it and is structurally forbidden from introducing judgment of its own — that's what makes the whole chain auditable back to a Rule, which is the property this entire repository exists to protect. The only refinement worth naming is one already reflected correctly in `ROADMAP.md` and not worth re-litigating: `templates/`, `adr/`, and `anti-patterns/` are support structures that apply *across* every phase rather than belonging to one — the repository already models this correctly and no change is needed here.
