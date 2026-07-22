# adr/

## Purpose

Dated records of non-obvious decisions about *this repository's own structure or process* — not ERPNext architecture decisions (those are Rules), decisions about how the repository itself is run. E.g., why a folder was structured a certain way, or why the mandatory phase order was deliberately broken once.

## What belongs inside

One file per decision: the context, the alternatives considered, what was decided, and the consequence accepted. Short is fine.

## What does NOT belong inside

General architectural rules for ERPNext work — those belong in [`rules/`](../rules/). Routine, obvious choices that need no justification don't need an ADR either.

## Typical lifecycle

Written at the moment a non-obvious call is made about the repo itself → kept permanently as-is → superseded by a new ADR if the decision is later reversed (never edited in place).
