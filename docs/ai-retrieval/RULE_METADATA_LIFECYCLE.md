# RULE METADATA LIFECYCLE

**Status:** Foundational
**Authority:** Subordinate to [RULE_METADATA_SPECIFICATION.md](RULE_METADATA_SPECIFICATION.md). Does not modify the Engineering Rule's own lifecycle ([docs/ENGINEERING_RULE_SPECIFICATION.md § 7](../ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle), [ENGINEERING_META_MODEL.md § Rule Lifecycle](../../ENGINEERING_META_MODEL.md#rule-lifecycle)) — it describes a second, dependent lifecycle that tracks alongside it.

---

## Two lifecycles, not one

An `RM` record has no independent lifecycle of its own kind — it does not get "approved" separately from its rule, and it cannot be `Stable` while its rule is `Draft`. What it *does* have, and what did not previously exist anywhere in this repository, is a **sync lifecycle**: a record of whether the metadata still matches the source it was derived from. These are the two axes:

```
                 mirrored, never independent
Rule Status  ─────────────────────────────────▶  RM.status
(canonical, docs/ENGINEERING_RULE_SPECIFICATION.md §3)

                 new — tracks drift, not approval
RM.sync_state:  generated ──▶ validated ──▶ synced ──▶ stale ──▶ (regenerate) ──▶ generated
```

## Axis 1 — `status` (mirrored)

`RM.status` is a direct copy of its source rule's `## Status` field at the time the record was last generated. It is never set by an `RM` author independently of that field, and it is not a separate approval gate an `RM` record must pass through on its own.

**Reconciling with a generic Draft → Review → Approved → Stable → Deprecated → Archived lifecycle.** A general knowledge-artifact lifecycle of that shape is a reasonable default, and this repository already has two versions of it at different granularities — [ENGINEERING_META_MODEL.md § Rule Lifecycle](../../ENGINEERING_META_MODEL.md#rule-lifecycle) (nine stages, Idea → Research → Evidence Collection → Draft → Architecture Review → Approved → Stable → Deprecated → Archived) and its collapsed, operational form in [docs/ENGINEERING_RULE_SPECIFICATION.md § 3](../ENGINEERING_RULE_SPECIFICATION.md#3-rule-structure) (`Draft` / `Review` / `Stable` / `Deprecated`, four values). Introducing a third, slightly different version here — with its own `Approved` and `Archived` — would let three lifecycles for the same underlying fact drift apart. `RM.status` therefore reuses the four-value collapsed set verbatim:

| Generic stage (as commonly requested) | Reconciled value used by `RM.status` | Note |
|---|---|---|
| Draft | `Draft` | Direct match. |
| Review | `Review` | Direct match. |
| Approved | *(not a separate value)* | Folded into the transition **to** `Stable` — per the Rule Lifecycle, "Approved" is the review outcome that produces `Stable`, not a resting state a rule (or its `RM` record) stays in. |
| Stable | `Stable` | Direct match. |
| Deprecated | `Deprecated` | Direct match. |
| Archived | *(not a separate `RM.status` value)* | Archival is a meta-model-level, whole-repository event (moving a rule out of active `Skill`/`Agent` generation — [ENGINEERING_META_MODEL.md § Rule Lifecycle, stage 9](../../ENGINEERING_META_MODEL.md#rule-lifecycle)), not a per-record field. When a rule is archived, its `RM` record is archived alongside it by the same repository-level action, not by setting a value inside the record. |

## Axis 2 — `sync_state` (new)

This is the genuinely new lifecycle this document introduces, because nothing like it needs to exist for the canonical rule itself (a Rule is its own source; it cannot be "out of sync with itself").

1. **`generated`** — an `RM` record has just been produced (by hand or by tooling) from a specific version of its source rule. Not yet checked against [METADATA_SCHEMA.yaml](METADATA_SCHEMA.yaml).
2. **`validated`** — the record passes schema validation (every required field present and well-formed) and the [Quality Standards](RULE_METADATA_SPECIFICATION.md#7-quality-standards) self-check (no restated prose, `requirements` traceable to the source `## Rule` section, `conflicts` actually reviewed).
3. **`synced`** — `validated`, **and** `source_content_hash` matches the current content hash of `source_file`. This is the steady state a healthy `RM` record should be in most of the time.
4. **`stale`** — `source_content_hash` no longer matches `source_file`'s current hash (the rule changed after this record was last generated). A `stale` record remains usable for retrieval — see [RULE_METADATA_SPECIFICATION.md § 6](RULE_METADATA_SPECIFICATION.md#6-sync-and-validation) — but any [`RIX`](RULE_INDEX_SPEC.md) query result built from it must surface that fact rather than presenting stale structure as current.
5. **Regeneration** returns a record to `generated`, restarting the cycle. Regeneration never silently mutates a `stale` record in place without re-running validation — going stale → synced directly is not a valid transition.

**What triggers a state change:**

| Trigger | Effect |
|---|---|
| `RM` record authored or regenerated | → `generated` |
| Schema + quality self-check passes | `generated` → `validated` |
| `source_content_hash` confirmed equal to live `source_file` hash | `validated` → `synced` |
| `source_file` is edited (any change, including a `## Status` flip) | `synced` → `stale`, immediately, regardless of whether the edit was substantive |
| Rule reaches `Status: Deprecated` | `RM.status` mirrors to `Deprecated` on next regeneration; the record is not deleted — deprecated rules remain retrievable, ranked lower per [RULE_INDEX_SPEC.md § 2](RULE_INDEX_SPEC.md#2-rank-them) |

## Why staleness is tracked instead of enforced synchronously

Requiring every `RM` record to regenerate the instant its rule changes would couple ordinary rule editing to metadata tooling that may not exist yet at every point in this repository's life — [ROADMAP.md](../../ROADMAP.md) is explicit that Phase 2 stages roll out incrementally. Tracking `stale` as a first-class, visible state (rather than pretending synchronicity is guaranteed) is what makes this layer honest at partial tooling maturity: a human or agent can always tell, from the record itself, whether to trust its structured fields outright or re-read the source rule first.
