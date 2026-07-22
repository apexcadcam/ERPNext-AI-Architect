# templates/

## Purpose

Concrete, reusable implementation scaffolds that demonstrate a rule or pattern already proven in practice — a starting point, not a finished solution.

## What belongs inside

A scaffold (file structure, boilerplate) tied explicitly to a specific rule in [`rules/`](../rules/) — e.g., a `hooks.py` starting shape that already keeps hook functions thin.

## What does NOT belong inside

A full, finished solution to a one-off business problem. If it's only ever going to be used once, it belongs in that project, not here.

## Typical lifecycle

Stays empty until a rule has been applied by hand enough times that re-deriving the same scaffold each time is wasted effort → added opportunistically → revised if the underlying rule changes.
