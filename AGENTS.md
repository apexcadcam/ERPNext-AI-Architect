# AGENTS.md — Instructions for AI Agents

This repository is the architectural rulebook for building custom applications on top of Frappe / ERPNext. It exists because we have repeatedly paid the cost — broken upgrades, orphaned fields, duplicated data models — of skipping these rules.

## Mandatory Procedure

Before generating **any** code, DocType design, field, fixture, hook, or architecture proposal for an ERPNext/Frappe app in this or any related repository, you MUST:

1. Read every rule file in [`rules/`](rules/) in full, in numeric order (`R001`, `R002`, ...).
2. Check the proposal you are about to make against each rule's **Principle** and **Bad Pattern** section. If your draft resembles a Bad Pattern, stop and redesign it to match the corresponding Good Pattern.
3. If a proposal conflicts with a rule, do not silently override it. State the conflict explicitly and explain the tradeoff before proceeding — the rules are non-negotiable defaults, not suggestions to weigh against convenience.
4. If a new rule is discovered during work (a new recurring mistake, a new upgrade-breaking pattern), propose a new `rules/R00N-*.md` file following the exact template below rather than leaving the lesson undocumented.

## Rule File Template

Every file in `rules/` follows this exact structure — do not deviate from it when adding new rules:

```markdown
# R00N: Title

## Principle
Short, non-negotiable architectural statement.

## Architectural Impact
Why this prevents technical debt and broken upgrades.

## Bad Pattern
Example of the poor architectural choice, with code.

## Good Pattern
The standard Frappe Framework / ERPNext core way, with code.

## Risk Level
Critical / High / Medium
```

## Core Bias

When in doubt between two designs, prefer the one that:
- Touches zero core (`frappe`/`erpnext`) files — see [R001](rules/R001-core-isolation-non-invasive-extension.md).
- Reuses an existing native doctype/field/child table over inventing a new one — see [R002](rules/R002-native-first-discovery.md).
- Uses configuration (Property Setter, Workflow, Client/Server Script) over custom code — see [R003](rules/R003-low-code-configuration-over-code.md).
- Keeps fixtures scoped, module-tagged, and reversible — see [R004](rules/R004-fixture-and-metadata-integrity.md).
- Installs and migrates idempotently without silently overwriting admin-managed state — see [R005](rules/R005-idempotent-upgrade-safe-deployment.md).

Agents that skip this procedure and propose a Bad Pattern from any rule file are considered to have failed the task, regardless of whether the code runs.
