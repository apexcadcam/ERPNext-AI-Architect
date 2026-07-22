# rules/

## Purpose

The source of truth of this repository. A rule here is a non-negotiable, evidence-backed architectural default — not a preference. See [AGENTS.md](../AGENTS.md) for the mandatory procedure every proposal is checked against these rules.

## What belongs inside

One `R0NN-slug.md` file per rule, following the required template: Principle, Architectural Impact, Bad Pattern, Good Pattern, Risk Level (defined in [AGENTS.md](../AGENTS.md)).

## What does NOT belong inside

Unproven ideas, personal preferences, or anything without a concrete Bad Pattern you've actually hit. Work those out in [`research/`](../research/) first — only promote to a rule once you're confident enough to call it non-negotiable.

## Typical lifecycle

A question in `research/` gets resolved → written up directly as a new `R0NN` file (solo-dev pace — no formal review board) → used, as of Phase 2, to generate a Skill once the same task has been handled manually a few times.
