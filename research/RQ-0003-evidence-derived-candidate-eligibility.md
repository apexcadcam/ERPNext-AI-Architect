# Eligibility for Evidence-Derived Candidates

## Status

- Date opened: 2026-08-01
- Date closed: 2026-08-01
- Status: `Resolved` — accepted at review; the decisions it framed are recorded in [ADR-0016](../adr/ADR-0016-no-automated-candidate-formation.md).

**Changelog**
- 2026-08-01 — Opened and investigated (RQ-0003). Examines every published Pattern in the `v1.4.1` corpus against the human decision that evidence-derived candidacy is limited to Best Practice and Standard.
- 2026-08-01 — Accepted at review. Findings unchanged; the architectural consequences are recorded in [ADR-0016](../adr/ADR-0016-no-automated-candidate-formation.md), including the decision to ship no Candidate Formation engine.

## Question

**Which of the platform's currently published Patterns are actually eligible to produce an evidence-derived Candidate Best Practice or Candidate Standard, and what measurable property distinguishes an eligible Pattern from one whose measurement cannot safely support candidacy?**

Sub-questions: can tautological populations be identified structurally rather than by interpreting prose; does support magnitude participate in eligibility; are eligibility and salience separate concepts; what distinguishes a Standard from a Best Practice here; is absence usable; is the provenance chain sufficient; and is an automated Candidate Formation stage justified at all.

## Background

Sprint 23 opened expecting Candidate Formation machinery. A prior research report established that the repository already models candidacy — `Best Practice (BP)` is defined in [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md) as *"a candidate `Engineering Rule` in waiting"*, and [ADR-0002](../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md) binds any rule-shaped pipeline output to the existing human-gated lifecycle.

The human decision entering this research: **a measured Pattern must never directly become a Candidate Engineering Rule.** Evidence-derived candidacy is limited to Candidate Best Practice, and Candidate Standard where the semantics genuinely fit.

## Method

Every one of the 29 Patterns published in the `v1.4.1` corpus was examined individually — no sampling. Structural tests were computed against the live registries (`WHITELIST_FAMILY_SUBJECTS`, `POPULATION_RESOLVERS`) and the persisted artifacts, never against natural-language interpretation of `population_description`.

Corpus: `frappe` v15.103.1, `erpnext` v15.102.0, at repository `v1.4.1`.

## Findings

### F1 — Tautology is structurally computable, and producer-owned

The test *"does membership in the numerator predicate logically participate in construction of the denominator?"* is answerable from the registries alone:

```
WHITELISTED_API_DECORATION
  denominator := { symbol : subject ∈ WHITELIST_FAMILY_SUBJECTS }
  numerator(S) := { symbol : subject == S }
  participates ⟺ S ∈ WHITELIST_FAMILY_SUBJECTS

CONTROLLER_LIFECYCLE_HOOK
  denominator := resolved Document descendants  (class_definition evidence)
  numerator(S) := classes defining a method named S  (lifecycle-hook evidence)
  participates ⟺ never — drawn from different Evidence categories
```

**3 of 29 participate.** The population resolver already holds the set that defines its own denominator, so it can state this as a fact about construction without any normative interpretation.

### F2 — Tautology is claim-relative, not a property of a Pattern

The two whitelist-family spellings **partition the population exactly** — measured: `frappe` 518 + 2 = 520, `erpnext` 705 + 0 = 705, overlap 0 in both.

Therefore `frappe.whitelist 518/520`:

- gives **zero** support to *"endpoints should be whitelisted"* — undecorated symbols are excluded from the denominator by construction;
- gives **strong** support to *"given that a whitelist-family decorator is used, the dotted spelling is the dominant convention"*.

The same measurement, two claims, opposite verdicts. **The proposed `ELIGIBLE`/`INELIGIBLE_TAUTOLOGICAL` taxonomy cannot express this**, and forcing a single Pattern-level label would discard the distinction that matters. Reported rather than resolved by inventing vocabulary.

### F3 — Support magnitude has no defensible role

| Group | n | min | max | mean |
|---|---|---|---|---|
| Tautology-flagged | 3 | 0.0038 | 1.0000 | 0.6667 |
| Not flagged | 26 | 0.0028 | 0.3529 | 0.0757 |

- *high support ⇒ more eligible*: **refuted.** The two highest-support Patterns in the corpus (1.0000, 0.9962) are exactly those whose obvious reading is unsupported.
- *low support ⇒ less eligible*: **refuted.** `whitelist` at 0.0038 is flagged; `cache_source` at 0.0028 is not.

No threshold separates eligible from ineligible in either direction. **None is proposed**; any value would be an artifact of this corpus.

### F4 — No Pattern describes a majority practice

The highest non-tautological support in the entire corpus is **0.3529**. Zero non-tautological Patterns exceed 0.50. Every structurally sound measurement describes a **minority** practice, and a minority frequency cannot support a recommendation to follow something *by default*.

### F5 — `ELIGIBLE_STANDARD` is zero by definition, not by corpus

[ENGINEERING_META_MODEL.md §10](../ENGINEERING_META_MODEL.md) defines a Standard as keeping *"the repository itself internally consistent and machine-parseable"*, and states it must **not** be created *"for an architectural preference about ERPNext customization."*

Standards govern the form of this knowledge repository's own artifacts. A convention observed in Frappe source code is not one, and never could be — for any corpus the Evidence Platform could produce.

### F6 — Absence is unusable and remains so

Of 11 recognised lifecycle-hook names, **4 appear nowhere in frappe's artifact**: `before_submit`, `on_cancel`, `on_submit`, `on_update_after_submit`. No Pattern, no below-threshold entry, no marker of any kind.

`observed_below_threshold` is **not** a zero-observation: every entry records a real count of 1 that fell below the floor. Nothing in the artifact represents zero.

No inference was drawn from silence anywhere in this research.

### F7 — The provenance chain resolves; the locator gap is not blocking

Three Patterns traced end to end — all `supporting_evidence_ids` resolve to real records carrying repository, version, commit, path and line.

`PatternSet.source_evidence_set_id` is a per-run UUID rather than a durable locator, but `repository + version + commit` already identifies the corpus uniquely and the conventional artifact path resolves it. **Separate backlog item ([W7](../docs/evidence-platform/BACKLOG.md#w7--durable-evidenceset-identity)), not a prerequisite.**

### F8 — The existing candidate machinery is a different concept

`knowledge.extraction`'s `PATTERN_CANDIDATE_TAG_PREFIX` machinery consumes `ContentArtifact` documents and promotes `Pattern`/`AntiPattern` solution shapes on a *recurrence* bar of two independent artifacts. Evidence-derived candidacy consumes a measurement and would produce a recommendation on a *ratio*. Different input, output, and corroboration model — **reuse is not appropriate**.

**Naming hazard:** `knowledge`'s `Pattern` (a solution shape) and `aggregation`'s `Pattern` (a measurement) are unrelated concepts sharing a name — the third such collision after `Evidence` (three meanings) and `rule` (three meanings).

## Classification result

All 29 Patterns were classified individually. The full table is preserved in the RQ-0003 research artifact; the counts are:

| Classification | Count |
|---|---|
| `ELIGIBLE_BEST_PRACTICE` — scoped to a spelling-convention claim only | 3 |
| `ELIGIBLE_STANDARD` | 0 |
| `INELIGIBLE_TAUTOLOGICAL_POPULATION` as a sole label | 0 |
| `INELIGIBLE_ABSENCE_DERIVED` | 0 |
| `INELIGIBLE_INSUFFICIENT_SEMANTICS` | 26 |
| `INELIGIBLE_OTHER` | 0 |
| **Total examined** | **29** |

The three eligible Patterns collapse to **two distinct claims**, one per repository, because the frappe pair is a single partition seen from both sides. Merging across repositories is blocked by the cross-repository prohibition.

`INELIGIBLE_TAUTOLOGICAL_POPULATION` is zero **not because no Pattern is tautological** — three are — but because tautology alone did not disqualify them once the claim was narrowed. That is F2 expressed numerically.

## Evidence Summary

The corpus supports exactly two claim-level conventions, both about how to spell one decorator, and both found by hand during this research. It supports no recommendation derived from frequency, because no non-tautological measurement describes a majority. It supports no threshold, because none separates the useful from the unusable.

## Open Questions

1. Are the two spelling claims worth recording as Best Practices at all? Eligibility for an artifact is not the same as the artifact being worth keeping. **Settled at review: not at this time** — preserved as findings here instead.
2. Should the Pattern-level eligibility taxonomy be revised to operate on (measurement, claim) pairs, or retired unused? **Settled by [ADR-0016](../adr/ADR-0016-no-automated-candidate-formation.md): retired as production vocabulary.**
3. When would Candidate Formation become justified? Left open deliberately — see ADR-0016's demand-triggered consequence.

## Final Recommendation

**Record the measurement-construction property in the producer, and build nothing.**

Two claims from 29 Patterns do not justify a contract change, a registry, a persistence format and a CLI surface. The construction *fact* is worth preserving — it is objective, producer-computable, and it prevented a wrong candidate. The *engine* is speculative infrastructure, which [R009](../rules/R009-yagni-no-speculative-infrastructure.md) forbids by name.

## Potential Rule Candidates

**None.** This research concerns the platform's own measurement semantics, not how an ERPNext developer should build something. Consistent with the standing decision, no evidence-derived Engineering Rule is proposed, and frequency alone is never Rule-grade evidence.

## Related Topics

- [ADR-0016](../adr/ADR-0016-no-automated-candidate-formation.md) — the decisions this research framed
- [ADR-0002](../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md) — the binding constraint on rule-shaped pipeline output
- [W7](../docs/evidence-platform/BACKLOG.md#w7--durable-evidenceset-identity), [W8](../docs/evidence-platform/BACKLOG.md#w8--explicit-zero-observations-for-absent-subjects)
- [RQ-0002](RQ-0002-controller-lifecycle-hook-population.md) — the measurement platform this research examines the output of

## References

Tier 1, measured directly at `v1.4.1`:

- `pattern-data/frappe-v15.103.1.patterns.jsonl` — 15 Patterns
- `pattern-data/erpnext-v15.102.0.patterns.jsonl` — 14 Patterns
- `aggregation/resolvers.py` — `WHITELIST_FAMILY_SUBJECTS`, `POPULATION_RESOLVERS`
- `evidence/collectors.py` — the closed lifecycle-hook name list
- [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md) §10 (Standard), §11 (Best Practice)
