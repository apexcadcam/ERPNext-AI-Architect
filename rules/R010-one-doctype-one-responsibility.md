# R010: One DocType, One Responsibility

## Status
Stable

## Risk Level
**High**

## Rule
Every custom DocType must represent exactly one business concept with a clearly stated boundary — answerable in one sentence ("Lead = who is this?", "Customer = who bought?", "Opportunity = what's being sold right now?"). A DocType must never be allowed to absorb multiple unrelated responsibilities (identity + follow-up tracking + financial history + ad-hoc contact storage) just because it was convenient to bolt one more field onto an existing form.

## Rationale
A DocType that accumulates unrelated responsibilities becomes impossible to reason about or safely modify — every change risks breaking a completely unrelated feature that happens to live on the same doctype, and permission modeling breaks down, since visibility into one responsibility can't be granted without also granting the others bundled onto the same record.

## Scope
Applies whenever a new custom DocType is being designed, or an existing one is being extended with new fields or responsibilities.

## Bad Pattern
A single `Lead` DocType with an unbounded child table for ad-hoc contacts, a duplicate-of-core search index field, financial fields that only make sense post-conversion, and sync logic pulling data bidirectionally between it and Customer — one doctype quietly doing the job of four.

## Good Pattern
Separate DocTypes with a one-directional, one-time data flow at the natural transition point: `Lead` (identity + market knowledge, pre-sale) → converts once into `Customer` (commercial/financial record) + native `Contact` (official contact channel) → `Opportunity` (one doctype per deal, always linked to a Customer, never storing identity data of its own). Each DocType's field list should be answerable by its one-sentence responsibility statement; a field that doesn't fit that sentence belongs on a different DocType.

## Exceptions
None.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R002 — Native-First Discovery](R002-native-first-discovery.md)

## Related Anti-Patterns
None yet.
