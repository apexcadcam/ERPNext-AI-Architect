# R009: YAGNI — No Speculative Infrastructure

## Status
Stable

## Risk Level
**Medium**

## Rule
Do not build caching layers, generic "scope"/strategy abstractions, or any infrastructure to solve a performance or flexibility problem that has not been *measured* and proven to exist. Every piece of infrastructure must be justified by a real, observed bottleneck or a concrete, already-confirmed requirement — never by "we might need it later."

## Rationale
Speculative infrastructure adds permanent maintenance cost and cognitive load for a problem that may never materialize, and it is frequently wrong about the shape of the eventual real problem anyway — meaning it gets rewritten regardless once the real need arrives, making the original effort pure waste.

## Scope
Applies whenever new infrastructure (caching, generic abstractions, strategy layers) is proposed to address a performance or flexibility concern.

## Bad Pattern
Building a summary-cache table "in case the query gets slow at scale" before any query has actually been measured; writing a generic strategy-pattern layer to support hypothetical future variants nobody has asked for yet.

## Good Pattern
Ship the straightforward implementation first. When a real performance concern exists, measure it (e.g. `EXPLAIN`, a load test against real production-scale data) before deciding whether optimization infrastructure is actually justified — and if the measurement says it's fine, do not build the optimization at all.

## Exceptions
Building infrastructure is justified once a real bottleneck has been measured (e.g., via `EXPLAIN` or a load test) — not before.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R003 — Low-Code / Configuration Over Code](R003-low-code-configuration-over-code.md); [R007 — Thin Hooks, Centralized Service Layer](R007-thin-hooks-centralized-service-layer.md)

## Related Anti-Patterns
None yet.
