# ADR-0016: No Automated Candidate Formation; Eligibility Is Claim-Relative

**Date:** 2026-08-01
**Status:** Accepted
**Evidence:** [RQ-0003](../research/RQ-0003-evidence-derived-candidate-eligibility.md) — all 29 published Patterns examined individually
**Constrained by:** [ADR-0002](ADR-0002-knowledge-pipeline-artifact-reconciliation.md) — rule-shaped output stays behind human Architecture Review
**Opens:** [W7](../docs/evidence-platform/BACKLOG.md#w7--durable-evidenceset-identity), [W8](../docs/evidence-platform/BACKLOG.md#w8--explicit-zero-observations-for-absent-subjects) — both non-blocking

## Context

Sprint 23 opened expecting Candidate Formation machinery: a stage that would turn measured Patterns into Candidate Engineering Rules. A prior human decision had already narrowed that — evidence-derived candidacy limited to Candidate Best Practice, and Candidate Standard where the semantics fit — because [`ENGINEERING_META_MODEL.md`](../ENGINEERING_META_MODEL.md) requires *"`Production Incident`-grade evidence"* for a Rule, and the Evidence Platform measures frequency in source code, observing no incidents, consequences, or costs.

[RQ-0003](../research/RQ-0003-evidence-derived-candidate-eligibility.md) then tested whether the corpus could feed such a stage. It examined every one of the 29 Patterns published at `v1.4.1` — no sampling — and found:

- **Two distinct claim-level conventions survive**, expressed by three Pattern instances, both about how one decorator is spelled.
- **No non-tautological Pattern describes a majority practice.** The highest such support in the entire corpus is `0.3529`.
- **Support magnitude does not predict candidacy in either direction.** The two highest-support Patterns (`1.0000`, `0.9962`) are precisely those whose obvious reading is unsupported.
- **`ELIGIBLE_STANDARD` is zero by definition**, not by corpus: Standards govern this repository's own artifacts, never conventions observed in ERPNext source.

Both surviving claims were found by hand, in minutes, during the research itself.

## Decisions

1. **No automated Candidate Formation stage is justified** at the current corpus size or semantic maturity. Sprint 23 ships no such component.

2. **Pattern support is descriptive frequency, never recommendation strength.** A support figure states how often something occurs within a stated denominator. It carries no weight toward whether the thing should be done.

3. **Candidate eligibility is claim-relative, not a property of a Pattern.** Formally, `eligibility = relation(measurement semantics, proposed claim)`. The same measurement may give zero support to one claim and strong support to another — `frappe.whitelist 518/520` supports nothing about *whether* endpoints should be whitelisted, and supports well the conventional claim about *which spelling* dominates once one is used.

4. **The Pattern-level eligibility taxonomy is retired as production vocabulary.** `ELIGIBLE_BEST_PRACTICE` / `INELIGIBLE_TAUTOLOGICAL_POPULATION` and their siblings served as research instruments in RQ-0003 and are not adopted as a contract, an enum, or a persisted field. Decision 3 is why they cannot be.

5. **Measurement-construction semantics belong to the producer** when the producer knows them by construction. A population resolver already holds the set defining its own denominator; it can state *whether the subject predicate participates in constructing that denominator* as an objective structural fact.

6. **Producer metadata must remain strictly non-normative.** The producer may describe **how a measurement was constructed**. It must never infer eligibility, correctness, recommendation, Best Practice status, salience, confidence, severity, or any normative meaning. What claims a measurement can support is decided downstream, by research and by humans.

7. **No support or salience threshold is introduced.** RQ-0003 found none defensible. A `heuristic_default` threshold invented to make a component exist would be calibration theatre.

8. **No `CandidateRule` artifact or model is introduced.** [ADR-0002](ADR-0002-knowledge-pipeline-artifact-reconciliation.md) already refused to create a rule-shaped pipeline type for the same reason; this decision does not reverse it.

9. **No Best Practice artifacts are generated automatically.** The two surviving claims are preserved as RQ-0003 findings. Eligibility for an artifact does not imply the artifact is worth permanently adding to the knowledge base.

10. **Evidence-derived Engineering Rules remain prohibited.** Promotion stays behind Research → consequence and corroborating evidence → human Architecture Review → `Draft` → Rule Review → `Stable`, exactly as [ENGINEERING_RULE_SPECIFICATION.md §7](../docs/ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle) already requires. **Frequency alone is never Rule-grade evidence, at any support.**

## Consequences

**Sprint 23 intentionally ships no Candidate Formation engine.** Sprint success is defined by whether the question was answered, not by whether a component was produced. The research tested whether the component was justified and the measured corpus said it was not; building it anyway would be speculative infrastructure, which [R009](../rules/R009-yagni-no-speculative-infrastructure.md) forbids by name.

**Future implementation is demand-triggered, not roadmap-triggered.** Candidate Formation is reconsidered only when the corpus produces enough legitimate claim-level candidates that manual research and triage become a *demonstrated* bottleneck — not when a roadmap says the sprint should contain an engine.

**If reconsidered, it must operate on an explicit proposed claim plus measurement semantics — never on Pattern support alone.** Decision 3 makes a Pattern-only input incapable of expressing the question. Any future design that accepts a `PatternSet` and emits candidates without a claim has reintroduced the error this ADR exists to prevent.

**Negative evidence remains unusable.** Absence is not zero until an artifact explicitly represents zero ([W8](../docs/evidence-platform/BACKLOG.md#w8--explicit-zero-observations-for-absent-subjects)). Silence must never be read as a measurement.

**This ADR decides nothing about implementation timing for producer metadata.** Decision 5 records that such metadata is architecturally correct and producer-owned. It does not authorise adding a field, and nothing in this decision is implemented.

## Rejected alternatives

**Support threshold → Candidate.** Rejected on measurement. No threshold separates eligible from ineligible in this corpus in either direction: `whitelist` at `0.0038` is tautology-flagged while `cache_source` at `0.0028` is not, and the two highest-support Patterns are the two least usable. Any number chosen would encode this corpus's accidents as policy.

**High-frequency Pattern → Best Practice.** Rejected because the inference is backwards here. The highest-support measurements are the ones whose numerator predicate helps construct their own denominator, so their magnitude is a property of the population's definition rather than of the practice.

**A Pattern-level eligibility flag interpreted normatively.** Rejected because it is not well-defined. A flag can honestly say *"this subject participates in constructing its denominator"*; it cannot honestly say *"this Pattern is eligible"*, because eligibility depends on a claim the Pattern does not contain.

**Reuse of `knowledge.extraction`'s candidate machinery.** Rejected as a different concept sharing a word. That machinery consumes `ContentArtifact` documents and promotes solution shapes on a recurrence bar of two independent artifacts; evidence-derived candidacy would consume a measurement and produce a recommendation from a ratio. Routing measurements through it would require inventing a `ContentArtifact` that does not exist, solely to reuse a tag prefix.

**Building an engine now for completeness of the sprint.** Rejected explicitly, and recorded because it is the alternative most likely to be revisited by someone reading only the roadmap. Two claims, from 29 Patterns, both about spelling one decorator, do not justify a contract change, a registry, a persistence format and a CLI surface built to rediscover facts already written down.

## Notes

RQ-0003 is preserved unchanged as the empirical basis for this decision. Where this ADR and the research disagree, the research is the measurement and this document is the judgement.

Standards remain out of scope for evidence-derived candidacy, per [ENGINEERING_META_MODEL.md §10](../ENGINEERING_META_MODEL.md): they govern the form and internal consistency of this repository's artifacts, not conventions observed in ERPNext or Frappe source code.
