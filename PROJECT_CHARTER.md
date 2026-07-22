# PROJECT CHARTER
## ERPNext AI Architect

**Status:** Foundational — Ratified
**Document type:** Project Charter
**Scope:** Defines the vision, philosophy, and success criteria for the entire project. All future rules, skills, agents, templates, and tooling must trace back to this document. Where a future artifact conflicts with this charter, the charter wins until it is explicitly amended.

---

# Vision

A world where every AI coding agent that touches a Frappe/ERPNext codebase behaves like a senior ERPNext solution architect by default — one who has personally lived through a broken `bench update`, a corrupted fixture, and a core file hand-edit that cost a client a weekend. The agent should not need to be reminded of this experience in every prompt; it should be structurally incapable of forgetting it.

ERPNext AI Architect exists to make correct architectural judgment the path of least resistance for AI-assisted development on Frappe/ERPNext, so that speed and safety stop being a tradeoff.

# Mission

To build and maintain an engineering knowledge base — a hierarchy of Rules, Skills, Agents, Templates, and Examples — that any AI agent (Claude, GPT, or otherwise) and any human engineer can load before writing a single line of ERPNext customization, and that structurally prevents the recurring, costly mistakes of invasive core edits, duplicated data models, non-reproducible fixtures, and upgrade-breaking shortcuts.

# Why this project exists

This project exists because we have already paid the cost this project is designed to prevent: broken upgrades after `bench update`, orphaned custom fields nobody remembers creating, duplicated DocTypes solving a problem ERPNext already solved, fixtures that only worked because of manual clicks in one person's browser, and access-control logic reinvented instead of configured.

Every one of these failures had the same root cause: the knowledge of *why* the good pattern is good lived in one engineer's head, was not written down, and was therefore invisible to whoever — human or AI — touched the code next. AI coding agents make this worse before they make it better: they can generate a plausible-looking Bad Pattern in seconds, with total confidence, at a volume no code review process was designed to catch.

ERPNext AI Architect exists to externalize that hard-won judgment into a durable, machine-readable, human-readable knowledge base — so the lesson is learned exactly once, by one person, on one project, and never has to be re-learned by anyone (or anything) again.

# Target audience

- **AI coding agents** (Claude Code, Claude Agent SDK–based agents, and other LLM-driven tooling) that generate, review, or modify Frappe/ERPNext code and configuration.
- **Frappe/ERPNext implementation partners and consultancies** who need a shared, enforceable architectural standard across multiple client codebases and multiple engineers.
- **In-house ERPNext development teams** who want new hires (human or AI) to inherit senior-level architectural instincts on day one instead of after their first production incident.
- **Open-source contributors** to the Frappe/ERPNext ecosystem who want a reference standard for what "upgrade-safe" and "core-isolated" actually mean in practice.

This project is not aimed at people new to software engineering in general — it assumes competence in writing code, and focuses entirely on the Frappe/ERPNext-specific architectural judgment that competence alone does not teach.

# Project Goals

1. Codify the recurring, costly architectural mistakes made on real Frappe/ERPNext projects as explicit, falsifiable Engineering Rules.
2. Make those rules consumable by AI agents in a form that changes agent *behavior*, not just agent *awareness* — a rule an agent reads and ignores has failed.
3. Provide a clear generation path from Rules → Skills → Agents so the knowledge base scales without every consumer having to re-derive judgment from first principles.
4. Keep every customization pattern in the knowledge base upgrade-safe by construction — safe to run before, during, and after a `bench update`.
5. Make the "native ERPNext way" more discoverable than the "build it from scratch" way, for both humans and AI.
6. Build a knowledge base that improves through use: every recurring mistake an agent makes becomes a candidate for a new or sharpened rule.
7. Keep the project genuinely open-source and framework-agnostic on the AI side — useful whether the agent is Claude, GPT, or a future model, because the knowledge lives in the rules, not in a vendor-specific prompt.

# Non Goals

- This project is **not** an ERPNext app, plugin, or module. It ships no runtime code that installs into a `bench`.
- This project does **not** aim to replace Frappe/ERPNext core documentation. It assumes and points to that documentation; it exists to cover the judgment calls the official docs don't make for you.
- This project does **not** aim to be a general-purpose AI prompt library. Prompts that are not backed by a durable, falsifiable Engineering Rule do not belong here.
- This project does **not** aim to enforce a single team's business logic, industry vertical, or company-specific process. Rules encode *architectural* principles, not *business* decisions.
- This project does **not** aim to lock users into a single AI vendor, model, or agent framework. Any generated Skill or Agent artifact must remain a faithful derivative of the underlying Rule, not a vendor-specific reinterpretation of it.
- This project does **not** aim for exhaustive rule coverage on day one. A small set of rigorously correct, battle-tested rules is worth more than a large set of speculative ones — see [R009](rules/R009-yagni-no-speculative-infrastructure.md).

# Core Engineering Philosophy

Good architecture on Frappe/ERPNext is not a matter of taste — it is a matter of surviving the next `bench update` with zero surprises. Every principle in this project reduces to one test: **if ERPNext core were updated tomorrow with no warning, would this customization survive intact, or would it silently break, silently duplicate, or silently corrupt data?**

Where a shortcut and the correct pattern both "work" today, this project always documents and defaults to the pattern that still works after the shortcut's cost has come due — because in this domain, that cost always comes due.

# Design Principles

- **Explicit over implicit.** A customization's existence, scope, and owner must be discoverable from the repository — never from tribal knowledge or a support ticket history.
- **Reversible over permanent.** Prefer changes that can be cleanly uninstalled (fixtures, hooks, Property Setters) over changes that leave residue if removed.
- **Configuration over code, code over core.** Reach for native configuration first, custom code second, and a core file edit never — see [R003](rules/R003-low-code-configuration-over-code.md).
- **One responsibility per unit.** A DocType, hook, or module earns exactly one clearly bounded job; overloaded responsibilities are a design smell, not a convenience — see [R010](rules/R010-one-doctype-one-responsibility.md).
- **Boring is a feature.** The most standard, most native, least clever solution is preferred by default. Cleverness must justify itself against the maintenance cost it adds.
- **Prefer improving engineering knowledge over redesigning repository architecture.** Once a structure works, resist the urge to reshape it for elegance alone — see [Architecture Freeze v1.0](#architecture-freeze-v10).

# Architecture Principles

- **Isolation by construction, not by discipline.** Core isolation ([R001](rules/R001-core-isolation-non-invasive-extension.md)) must be structurally enforced by the tooling and the review process, not merely requested of engineers or agents.
- **Discoverability before invention.** Before any new DocType, field, or workflow is designed, the native ERPNext data model must be searched for an existing equivalent — see [R002](rules/R002-native-first-discovery.md).
- **Thin surface, thick service layer.** Hooks and event handlers are wiring, not logic. Real business logic lives in a testable, framework-independent service layer — see [R007](rules/R007-thin-hooks-centralized-service-layer.md).
- **Permissions are configuration, not code.** Access control is expressed through Frappe's native Role Permission Manager and User Permissions, not bespoke `has_permission` logic reinventing what the framework already provides — see [R008](rules/R008-native-permission-system-over-custom-checks.md).
- **Reproducibility is non-negotiable.** Any environment must be rebuildable from git history alone: UI/metadata state via fixtures, data-shape changes via idempotent patches — see [R006](rules/R006-full-reproducibility-fixtures-and-patches.md).

# AI First Principles

- **An agent is a consumer of judgment, not a source of it.** The knowledge base exists so an AI agent does not have to rediscover, from scratch and under time pressure, a lesson this project has already paid for.
- **Rules must change behavior, not just inform it.** A rule that an agent can read, acknowledge, and then violate has failed its purpose. Every rule is written to be checked against a concrete proposal (its Bad Pattern) before code is generated, not audited after the fact.
- **Refuse silently overriding a rule.** When a proposal conflicts with a rule, the correct agent behavior is to surface the conflict explicitly and let a human decide — never to quietly pick convenience over the documented standard.
- **Model-agnostic by design.** Knowledge is authored so that any sufficiently capable AI agent can consume it — this project is a knowledge base first and a Claude-specific toolset second.
- **The agent is accountable to the rules, not the other way around.** An agent that produces working code by violating a Bad Pattern has still failed the task.

# ERPNext First Principles

- **ERPNext already solved more of this than you think.** Most business requirements map to an existing DocType, field, report, or workflow feature. The default assumption is "this exists already" until a genuine search proves otherwise — see [R002](rules/R002-native-first-discovery.md).
- **Extend the framework's vocabulary, don't fork it.** New concepts should be expressed as extensions of ERPNext's existing data model and permission model wherever a faithful mapping exists.
- **The framework's upgrade cycle is a first-class constraint.** Every recommendation accounts for the fact that `bench update` will run again, on a timeline this project does not control.
- **Native tooling over custom tooling.** Frappe's own fixture, patch, hook, and permission systems are preferred over parallel custom infrastructure that reimplements what the framework already offers.

# Upgrade Safe Principles

- **Zero core diffs, always.** No file inside `apps/frappe`, `apps/erpnext`, or any other vendor app is ever hand-edited. Every customization is discoverable in a `git diff` of a custom app alone — see [R001](rules/R001-core-isolation-non-invasive-extension.md).
- **Idempotent by default.** Installs, migrations, and patches must be safely re-runnable without duplicating data, overwriting admin-managed state, or erroring on a second run — see [R005](rules/R005-idempotent-upgrade-safe-deployment.md).
- **Fixtures are scoped and reversible.** Fixture exports are module-tagged and intentional, never a blanket dump of an entire site's state — see [R004](rules/R004-fixture-and-metadata-integrity.md).
- **Assume the next update breaks nothing you didn't explicitly protect.** If a pattern's survival across an update depends on ERPNext core *not* changing a specific file, that pattern is treated as fragile and documented as a known risk, not shipped as a default recommendation.

# Extension over Modification

Every customization is additive, never invasive. The standard is not "does this achieve the requirement" but "does this achieve the requirement while leaving core untouched and every change attributable to our own app."

In practice this means preferring, in descending order:

1. Native configuration already exposed by ERPNext (fields, settings, workflows, print formats).
2. Framework-sanctioned extension points (Custom Field, Property Setter, Client Script, Server Script, `hooks.py` event handlers, whitelisted method overrides).
3. A genuinely new Custom DocType or app-level module, only when 1 and 2 cannot express the requirement.

A core file edit is never an option on this list — it is the failure mode this entire principle exists to prevent.

# Knowledge Hierarchy

This project's knowledge is organized as a strict hierarchy. Each layer is *generated from* the layer above it and must remain traceable back to it. Nothing in a lower layer may contradict the layer that produced it.

```
Engineering Rules   (source of truth)
        │
        ▼
      Skills        (generated from Rules)
        │
        ▼
      Agents        (generated from Skills)
        │
        ▼
       MCP          (executes tools only)

Templates  — implementation examples of Rules/Skills in practice
Examples   — reference material, not authoritative
```

- **Engineering Rules are the source of truth.** Every rule in `rules/` (see [AGENTS.md](AGENTS.md) for the current set, `R001`–`R010` and beyond) is the single authoritative statement of a Principle, its Architectural Impact, a Bad Pattern, and a Good Pattern. If any other artifact in this project — a skill, an agent prompt, a template, an example — disagrees with a rule, the rule wins and the other artifact is considered a bug.
- **Skills are generated from Rules.** A skill packages one or more rules into an actionable, repeatable procedure an agent or engineer can invoke for a specific task (e.g. "add a custom field," "write a migration patch"). A skill is a *distillation* of the rules relevant to that task, never a new source of architectural judgment. If a skill needs a principle the rules don't yet contain, the rule is written first, and the skill follows.
- **Agents are generated from Skills.** An agent composes one or more skills into a persona capable of carrying out a broader piece of work autonomously. Agents inherit their judgment entirely from the skills — and transitively the rules — they are built from. An agent is not a place to smuggle in undocumented preferences.
- **MCP only executes tools.** Any Model Context Protocol server in this project's ecosystem is a mechanical execution layer — it calls functions, reads data, runs commands. It carries no architectural judgment of its own and makes no decisions the layers above it did not already make. If an MCP tool's behavior needs to change based on architectural judgment, that judgment is added at the Rule/Skill/Agent layer, not hidden inside the tool.
- **Templates are implementation examples.** A template is a concrete, working instantiation of a rule or skill — scaffolding an engineer or agent can start from. Templates demonstrate compliance with the rules; they do not define new rules of their own.
- **Examples are references.** Examples illustrate a pattern in a specific real or realistic scenario for learning purposes. They carry no authority — an example that falls out of date with a rule is a documentation bug, not a rule violation, and is fixed by updating the example.

# Repository Philosophy

**This repository is not a prompt collection.**

A prompt collection is a set of phrasings optimized to make one model, on one day, produce one desired output. It decays the moment the model changes, and it teaches nothing to the human maintaining it — the judgment lives entirely inside the prompt's wording, invisible and unexaminable.

**This repository is an engineering knowledge base.**

Every artifact here — Rule, Skill, Agent, Template, Example — is written to be independently defensible: it states a Principle, explains the Architectural Impact of ignoring it, and shows a concrete Bad Pattern against a concrete Good Pattern. That structure is deliberately model-agnostic. It should read as correct architectural guidance to a human engineer with no AI assistant at all, and remain correct if the AI agent consuming it is swapped out tomorrow for a different one.

The test for whether something belongs in this repository is not "does this make the AI produce better output" — it is "is this a durable, falsifiable statement about how to build safely on Frappe/ERPNext, that would still be true in five years." If the answer is no, it belongs in a project-specific prompt, not here.

# Success Criteria

One year from now, this project is successful if:

1. **The rule set is battle-tested, not merely written.** Every rule in `rules/` has been checked against real proposals — human or AI-generated — and has caught at least one real Bad Pattern before it shipped.
2. **AI agents visibly change behavior because of this project.** There is concrete evidence (rejected proposals, redesigned drafts, explicit conflict call-outs) that agents following this knowledge base produced different, safer output than they would have without it.
3. **The Rules → Skills → Agents generation path is real, not aspirational.** At least one Skill and one Agent exist, are traceable to specific rules, and are in active use — proving the hierarchy works in practice, not just on paper.
4. **Zero core-file incidents on projects that adopted this charter.** No project using this knowledge base has experienced a `bench update` breakage traceable to a hand-edited core file, an orphaned fixture, or a non-idempotent migration.
5. **The knowledge base has grown from real mistakes, not speculation.** New rules added over the year trace back to actual recurring failures observed in practice — consistent with [R009](rules/R009-yagni-no-speculative-infrastructure.md) — not to hypothetical future needs.
6. **External adoption.** At least one team or contributor outside the project's original authors has adopted this knowledge base for their own Frappe/ERPNext work, evidence that the principles generalize beyond the specific projects that produced them.
7. **The project remains a knowledge base, not a prompt collection.** Every artifact added over the year still follows the Principle → Architectural Impact → Bad Pattern → Good Pattern structure, and the Knowledge Hierarchy has not been bypassed by shortcuts baked directly into agent prompts.

# Architecture Freeze v1.0

**Phase 1 — Repository Foundation is complete.** The repository's architecture — how knowledge is captured, structured, and turned into agent behavior — is now considered stable.

**Approved architectural artifacts:**
- [ENGINEERING_META_MODEL.md](ENGINEERING_META_MODEL.md) — the knowledge model every artifact type obeys.
- [research/RESEARCH_FRAMEWORK.md](research/RESEARCH_FRAMEWORK.md) — how research is chosen, sourced, and evaluated.
- [docs/ENGINEERING_RULE_SPECIFICATION.md](docs/ENGINEERING_RULE_SPECIFICATION.md) — the canonical definition of what an Engineering Rule is.
- [templates/ENGINEERING_RULE_TEMPLATE.md](templates/ENGINEERING_RULE_TEMPLATE.md) — the authoring template every rule now follows.
- All ten founding Engineering Rules (`R001`–`R010`), migrated to the canonical rule format.

**What "frozen" means:** future changes to this architecture — the knowledge model, the Rule structure, the folder layout, the Research → Rule → Skill → Agent pipeline — are exceptional events, not routine ones. They require an explicit architectural review, and they must be driven by a genuine structural deficiency surfaced through real usage — never by a theoretically cleaner idea arriving on its own.

**What "frozen" does not mean:** research, rules, skills, and agents keep being produced — that production is the entire point of what comes next. Freezing the architecture is what makes it safe to stop redesigning it and start using it.

From this point forward, the repository's primary work shifts from *designing the system* to *using the system* — see [ROADMAP.md § Phase 2 — Knowledge Engineering](ROADMAP.md#phase-2--knowledge-engineering) for what that means in practice.

---

*This charter is a living document only in the sense that it can be amended by explicit, deliberate decision — not by silent drift. Any change to Vision, Mission, or the principle sections above should be treated as significant enough to warrant its own reviewed change, not folded quietly into an unrelated commit.*
