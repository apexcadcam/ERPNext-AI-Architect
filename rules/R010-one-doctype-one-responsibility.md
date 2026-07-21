# R010: One DocType, One Responsibility

## Principle
Every custom DocType must represent exactly one business concept with a clearly stated boundary — answerable in one sentence ("Lead = who is this?", "Customer = who bought?", "Opportunity = what's being sold right now?"). A DocType must never be allowed to absorb multiple unrelated responsibilities (identity + follow-up tracking + financial history + ad-hoc contact storage) just because it was convenient to bolt one more field onto an existing form.

## Architectural Impact
A DocType that accumulates unrelated responsibilities becomes impossible to reason about or safely modify — every change risks breaking a completely unrelated feature that happens to live on the same doctype, and permission modeling breaks down (you can't grant "see financial history" without also granting "see follow-up notes" if they're the same record). The Apex CRM rebuild explicitly hit this: the original `apex_crm` design let Lead absorb "unlimited" contact storage, a bidirectional sync system, and a custom search index all on top of its core identity/market-intelligence responsibility, producing ~13,700 lines of custom JS and a 5,157-line `api.py` that became too fragile to safely modify. The rewrite fixed it by drawing hard boundaries — Lead owns identity/market-knowledge only, Customer owns commercial/financial history only, Opportunity owns one specific deal only — enforced by giving each concept its own DocType rather than a shared one with mode-switching fields.

## Bad Pattern
A single `Lead` DocType with a "Smart Contact Details" unbounded child table for contacts, a duplicate-of-core search index field, financial fields that only make sense post-conversion, and sync logic pulling data bidirectionally between it and Customer — one doctype quietly doing the job of four.

## Good Pattern
Separate DocTypes with a one-directional, one-time data flow at the natural transition point: `Lead` (identity + market knowledge, pre-sale) → converts once into `Customer` (commercial/financial record) + native `Contact` (official contact channel) → `Opportunity` (one doctype per deal, always linked to a Customer, never storing identity data of its own). Each DocType's field list should be answerable by its one-sentence responsibility statement; a field that doesn't fit that sentence belongs on a different DocType.

## Risk Level
**High**
