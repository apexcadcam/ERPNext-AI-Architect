# Sprint 23 Release Notes — Candidate Rule Formation

**Release:** `v1.4.2` — **pending, not yet tagged.**
**Outcome:** research and an architecture decision. **No Candidate Formation engine was built.**
**Contains no production capability and no contract change.**
**Depends on:** the Evidence Platform (`v1.1.0` Extraction, `v1.2.0` Aggregation, `v1.3.0` CLI, `v1.4.1` numerator alignment)

---

## Summary

Sprint 23 opened expecting Candidate Formation machinery — a stage turning measured Patterns into Candidate Rules. It ships none.

That is the result, not a shortfall. The sprint asked whether such a stage was justified, tested the question against the whole corpus, and found it was not. **Sprint success is defined by whether the question was answered, not by whether a component was produced.**

## Empirical basis

[RQ-0003](research/RQ-0003-evidence-derived-candidate-eligibility.md) examined **all 29 published Patterns individually** — no sampling — against the standing decision that evidence-derived candidacy is limited to Best Practice and Standard.

## Measured result

| | |
|---|---|
| Patterns examined | **29** |
| Structurally relevant to a claim-level convention | **3** Pattern instances → **2** distinct decorator-spelling claims, one per repository |
| Lacking sufficient semantics for any recommendation | **26** |
| Support threshold separating useful from unusable | **none exists** |

Both surviving claims concern how one decorator is spelled, and both were found by hand during the research itself.

The threshold hypothesis was **tested, not dismissed**. It fails in both directions: the two highest-support Patterns in the corpus (`1.0000`, `0.9962`) are precisely those whose obvious reading is unsupported, while `whitelist` at `0.0038` is structurally flagged and `cache_source` at `0.0028` is not. No non-tautological Pattern exceeds `0.3529` — every structurally sound measurement describes a *minority* practice.

## Architectural result

Recorded in [ADR-0016](adr/ADR-0016-no-automated-candidate-formation.md):

- **Eligibility is claim-relative**, not a property of a Pattern: `eligibility = relation(measurement semantics, proposed claim)`. The same measurement can give zero support to one claim and strong support to another.
- **Pattern support is descriptive frequency, never recommendation strength.**
- **Producer metadata may describe measurement construction only** — objective facts known by construction, never a normative eligibility flag.
- **No `CandidateRule`** artifact or model.
- **No salience score and no support threshold.**
- **No automatic Best Practice generation.**
- **Existing Rule promotion gates remain intact:** Research → corroborating evidence → human Architecture Review → `Draft` → Rule Review → `Stable`. Frequency alone is never Rule-grade evidence, at any support.

Future Candidate Formation is **demand-triggered, not roadmap-triggered**, and would have to operate on an explicit proposed claim plus measurement semantics — never on Pattern support alone.

## Artifacts

| Artifact | Role |
|---|---|
| [ADR-0016](adr/ADR-0016-no-automated-candidate-formation.md) | The decision — Accepted |
| [RQ-0003](research/RQ-0003-evidence-derived-candidate-eligibility.md) | The empirical record — all 29 Patterns |
| [D19](docs/DECISION_LOG.md) | Decision-log index entry |
| [W7](docs/evidence-platform/BACKLOG.md#w7--durable-evidenceset-identity) | Durable `EvidenceSet` identity — non-blocking |
| [W8](docs/evidence-platform/BACKLOG.md#w8--explicit-zero-observations-for-absent-subjects) | Explicit zero-observations — non-blocking |
| [W9](docs/evidence-platform/BACKLOG.md#w9--adr-documentation-provenance) | ADR documentation provenance — non-blocking |

## What did not change

**No production capability and no contract change.** No Python behaviour, no contract, no schema, no CLI, no persistence, no aggregation or evidence behaviour, and no corpus artifact. `evidence-data/` and `pattern-data/` are byte-identical to `v1.4.1`; every measurement published there still holds.

The only source-file change in this release is docstring and comment text in `aggregation/contract.py` and three test comments, correcting wording that said promotion into guidance was "Sprint 23's own, separate, later job". Executable structure is unchanged, proven by AST comparison.

## Known limitations

Unchanged from `v1.4.1` — see the [Evidence Platform backlog](docs/evidence-platform/BACKLOG.md). Sprint 23 closed none of them and added three non-blocking items.

Negative evidence remains unusable: **absence is not zero until an artifact explicitly represents zero**, and silence must never be read as a measurement.

## Follow-up work

Selected from demonstrated need rather than assumed sequencing. The highest-value genuinely open item is **[W3 — HRMS support](docs/evidence-platform/BACKLOG.md#w3--hrms-support)**: `hrms` is ranked `KS-0033` / #1 / P0 in this project's own committed source catalogue while the engine rejects it, and it is blocked on the framework-versus-consumer question rather than on effort.

> **Superseded 2026-08-01, after `v1.4.2` shipped.** The sentence above is preserved as the `v1.4.2` record and is not corrected in place: Sprint 23 closed genuinely believing W3 was design-blocked, and that is a historical fact worth keeping.
>
> [RQ-0004](research/RQ-0004-hrms-as-a-measurable-repository.md) subsequently found the framework-versus-consumer blocker was **dissolved rather than answered** — it assumed the platform makes normative claims, and [ADR-0016](adr/ADR-0016-no-automated-candidate-formation.md) had already established that it does not. [ADR-0017](adr/ADR-0017-canonical-repository-admission.md) records the rule that replaced it: a repository is admitted only once its supporting-corpus closure has been established by measurement and can be enforced.
>
> W3's remaining work is therefore **implementation, not a design question**. `repository_role`, which the item anticipated, is no longer expected. Nothing is built yet.

## A note on method

This is the first sprint in the project whose outcome is *build nothing*, and it is recorded deliberately rather than quietly.

The alternative — shipping an engine because the roadmap said the sprint would contain one — would have been speculative infrastructure built to rediscover two facts about decorator spelling that are now simply written down. [R009](rules/R009-yagni-no-speculative-infrastructure.md) forbids that by name, and the corpus gave no reason to make an exception.

The platform continues to claim exactly what its evidence supports, and no more.
