# R009: YAGNI — No Speculative Infrastructure

## Principle
Do not build caching layers, generic "scope"/strategy abstractions, or any infrastructure to solve a performance or flexibility problem that has not been *measured* and proven to exist. Every piece of infrastructure must be justified by a real, observed bottleneck or a concrete, already-confirmed requirement — never by "we might need it later."

## Architectural Impact
Speculative infrastructure adds permanent maintenance cost and cognitive load for a problem that may never materialize, and it is frequently wrong about the *shape* of the eventual real problem anyway — meaning it gets rewritten regardless once the real need arrives, making the original effort pure waste. During the Commission Manager design review, a proposed `CommissionBalance` cache and a generic `commission_scope` abstraction were both explicitly rejected with the reasoning "Over-engineering قبل وجود مشكلة" (over-engineering before a problem exists) / "تعقيد غير مبرر" (unjustified complexity). The same discipline paid off concretely on the `crm_apex` rewrite: rather than pre-building a custom `KanbanView` render override to handle a hypothetical performance problem, the team ran a real load test against the actual ~3,501-lead dataset first — it showed the existing native Kanban scaled fine (single-digit-to-low-double-digit ms queries, confirmed index usage), so the contingency was correctly never built at all.

## Bad Pattern
Building a `CommissionBalance` summary-cache table "in case the ledger query gets slow at scale" before any query has actually been measured; writing a generic `commission_scope`/strategy-pattern layer to support hypothetical future commission types nobody has asked for yet.

## Good Pattern
Ship the straightforward implementation first. When a real performance concern exists, measure it (e.g. `EXPLAIN`, a load test against real production-scale data) before deciding whether optimization infrastructure is actually justified — and if the measurement says it's fine, do not build the optimization at all, as happened with the Kanban render-override contingency that load-testing proved unnecessary.

## Risk Level
**Medium**
