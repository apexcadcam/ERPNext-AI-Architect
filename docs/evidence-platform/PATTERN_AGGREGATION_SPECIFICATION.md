# PATTERN AGGREGATION ENGINE — ARCHITECTURE SPECIFICATION

**Version:** 1.0
**Status:** Ratified and implemented. Released as `v1.2.0`.
**Package:** [`aggregation/`](../../aggregation/)

> **Provenance of this document.** Written and approved during Sprint 21, before implementation; every section number cited throughout `aggregation/` refers to it. Committed to the repository on 2026-07-28, after the fact. Where this document and the code disagree, **the code and its tests are authoritative**; §17 records the deltas.

---

## 1. Purpose

Turn atomic Evidence into measured Patterns: *this subject occurs this many times out of this population*. It states what **is** — never what to do about it.

The engine consumes **persisted Evidence only**. It never re-runs extraction, never touches a source tree, and never calls a language model. Counting is arithmetic.

## 2. Aggregation Capability Matrix

**The central table of this specification, and the reason the engine is honest.** Not every Evidence category has a derivable denominator. This matrix is the executable record of which do and which do not — implemented as the `POPULATION_BASES` registry in [`aggregation/population.py`](../../aggregation/population.py), so it cannot drift from behaviour the way prose can.

| Category | Status | Population |
|---|---|---|
| `whitelisted_api_decoration` | `aggregated` | Distinct symbols carrying a whitelist-family decorator (`frappe.whitelist` or `whitelist`) |
| `controller_lifecycle_hook` | `aggregated` **(since Sprint 22)** | Distinct classes descending from `Document`, resolved transitively. See §2.1 |

Two further categories — `class_definition` and `class_base_declaration` —
exist in the Evidence contract and deliberately have **no row here**. They
are topology, not signal: they describe the class graph so a population
can be resolved. See [Inheritance Resolution §5.3](INHERITANCE_RESOLUTION_SPECIFICATION.md).

Lookup is **default-deny**: a category with no matrix entry is skipped, never guessed at. `get_population_basis` returns `None` rather than raising.

### 2.1 The lifecycle-hook denominator gap — **closed in Sprint 22**

> **Resolved.** What follows is the gap as it stood from `v1.2.0` to
> `v1.3.0`, kept because the reasoning is why the platform is trusted:
> it declared what it could not measure rather than quoting a ratio it
> could not support. [RQ-0002](../../research/RQ-0002-controller-lifecycle-hook-population.md)
> measured the true population at **275** (frappe) and **510** (erpnext),
> against the lower bound of 482 recorded below, and
> [ADR-0015](../../adr/ADR-0015-cross-repository-inheritance-resolution.md)
> settled how it is derived.

The collector emits a record only when a hook is *found*, so classes without hooks leave no trace: **the numerator exists but the population does not.**

Measured against real ERPNext v15.102.0, the true population is at least 482 — 448 direct `class X(Document)` plus at least 34 via intermediate bases such as `AccountsController`, `TransactionBase`, `StockController`, `BuyingController` and `SellingController` — and multi-level inheritance chains remain unresolved even by that count.

Aggregating anyway would yield a share of hook *records* wearing the label of a share of controllers. Closing this requires a new Evidence category recording class definitions and their base classes (Sprint 22).

This gap was found by **measurement, not assumption**, and it is recorded as a persisted `SkippedAggregation` carrying the full reason — not as a comment, and not as a log line.

## 3. Inputs and outputs

`AggregationRequest` (wrapping an already-read `EvidenceSet`) → `PatternSet`.

## 4. Non-goals

- **Candidate Rules.** Sprint 23.
- **Verification and trust.** Sprint 24.
- **Cross-repository comparison.** Deliberately deferred: `frappe`'s 8.4% and `erpnext`'s 8.4% are not comparable quantities, because the populations are differently constituted. No `compare` surface exists anywhere, so nothing implies comparability before that is settled.
- **Any severity, priority, recommendation, or rule field** on `Pattern`.
- **Any Reasoning Engine / LLM call.** Zero.

## 5. No population, no Pattern

The governing principle. A Pattern without a denominator is a count wearing the costume of a rate. `Pattern.population` is constrained `ge=1` so a zero denominator is *unrepresentable* at the type level and cannot be produced even by a future bug in a resolver.

## 6. `support`, not `confidence`

`evaluation.contract.Confidence` already exists in this project as a closed enum meaning *how directly cited evidence supports a conclusion* — a judgement about inferential strength.

What this engine computes is a different quantity: **how frequently an observation occurs across a defined population.** That is `support`, stored alongside its `occurrences` numerator and `population` denominator so the raw counts are never hidden behind the ratio.

The word `confidence` is reserved for Sprint 24's Verification stage, where it will mean how much a *rule* is trusted given its source, corroboration, and human review. **No field named `confidence` exists anywhere in this module.**

## 7. Contract

All frozen. Full definitions: [`aggregation/contract.py`](../../aggregation/contract.py).

| § | Type | Notes |
|---|---|---|
| 7.1 | `AggregationStatus` | `aggregated` / `skipped_no_population`. Mirrors §2 exactly. A third value is added only when a third real situation exists |
| 7.2 | `PopulationBasis` | One row of the §2 matrix, made executable |
| 7.3 | `Pattern` | One measured observation, with content-addressed `pattern_id` |
| 7.4 | `SkippedAggregation` | A **first-class result**, not a diagnostic. See §9 |
| 7.5 | `ObservedBelowThreshold` | A subject seen fewer than `min_occurrences` times: recorded with its real count, never promoted, never silently dropped |
| 7.6 | `AggregationRequest` | The Input |
| 7.7 | `PatternSet` | The final artifact. `schema_version` is `"1.0"` |

`pattern_id` = `sha256(repository | version | commit | category | subject)`.

## 8. Population resolution

A dispatch table (`POPULATION_RESOLVERS`) maps a category to the function that derives its denominator. Default-deny at engine level: no matrix entry, or no resolver, means skip.

The resolver for `WHITELISTED_API_DECORATION` counts **distinct symbols**, not records — which is cheap and correct precisely *because* Evidence is atomic (Extraction §5).

## 9. Skip as a result

`SkippedAggregation` is carried in `PatternSet.skipped_aggregations`, persisted to disk, and asserted on by tests — so a consumer can act on it programmatically and a declared gap cannot silently drift closed.

A silently absent category would look identical to a category with nothing to report; only one of those is correct. `evidence_records_present` records how much data *was* available but could not be measured — the difference between "no records" and "no denominator".

**An empty `patterns` tuple alongside a populated `skipped_aggregations` is a valid, meaningful, successful result.** It says nothing was measurable, and precisely why. In v1.0, `skipped_aggregations` is never expected to be empty.

## 10. Algorithm

1. Partition Evidence by category.
2. For each category: look up its population basis; skip if absent.
3. Resolve the population; skip if no resolver.
4. Count distinct symbols per subject.
5. Promote subjects at or above `min_occurrences` to `Pattern`; record the rest as `ObservedBelowThreshold`.

Four distinct skip paths exist, each producing a typed, persisted result.

## 11. Determinism

Two runs against the same `EvidenceSet` produce an identical `PatternSet` in every field, including every `pattern_id`, except `pattern_set_id` and `aggregated_at`. Verified: the persisted `patterns.jsonl` is **byte-identical** across runs.

## 12. Module and plugin

Standard Module shape, registered as plugin `aggregation`. `capabilities_required` is empty even though this engine consumes Evidence — because it consumes the *persisted artifact*, not a running Evidence module.

## 13. Architecture boundaries

The most important boundary in this Sprint, checked by **exact dotted path** rather than top-level name:

| Import | Allowed |
|---|---|
| `evidence.contract`, `evidence.persistence` | ✅ |
| `evidence.engine`, `evidence.collectors`, `evidence.module`, `evidence.pipeline` | ❌ |

That is the executable form of "consume persisted Evidence only". All four share the top-level name `evidence`, so a top-level check would not distinguish them.

Additionally: no frozen package imports `aggregation` (one named exception); `aggregation` imports no Repository Intelligence package; `evidence` never imports `aggregation`, keeping the chain one-directional; no LLM library; no new third-party dependency (no pandas, numpy, scipy, statistics, duckdb, sqlite3, sqlalchemy — the executable form of the JSONL-over-database decision).

## 14. Rule Metadata Registry

Every numeric constant is a named registry entry carrying its own justification and a `calibration_status` of either `empirical` or `heuristic_default`.

**`MIN_OCCURRENCES_THRESHOLD`** — value `2`, `heuristic_default`:

> A subject observed exactly once is an anecdote, not a pattern — `staticmethod` occurs 1/705 in real ERPNext v15.102.0. Disclosed as a judgement call rather than a measured one: no production `PatternSet` data exists yet to calibrate it against. Revisited once real aggregation output accumulates.

## 15. Measured results

At the released version, against the committed Evidence corpus:

| Repository | Evidence consumed | Population | Patterns | Below threshold | Skipped |
|---|---|---|---|---|---|
| `frappe` v15.103.1 | 812 | 520 | 8 | 4 | 1 |
| `erpnext` v15.102.0 | 1,245 | 705 | 3 | 3 | 1 |

**The project's first empirically calibrated figure:** `frappe.validate_and_sanitize_search_inputs` occurs on 59 of 705 whitelisted symbols in ERPNext — `8.37%`. This confirmed a falsifiable prediction written into the implementation plan *before the engine existed*.

## 16. Public API and persistence

`aggregate_patterns(request: AggregationRequest) -> PatternSet`.

`write_pattern_set` / `read_pattern_set` — JSONL plus JSON sidecar, `sort_keys=True`, byte-identical on rewrite, with every malformed-input error converted to `AggregationError_`.

## 17. Known deltas between this document and the code

- **None outstanding.** The engine implements every section above as written.
- One test was found to be wrong rather than the source: `test_population_module_defines_no_resolver_or_arithmetic` failed because `dir()` includes imported callables. The test was corrected to filter on `__module__`; `population.py` was not changed.
