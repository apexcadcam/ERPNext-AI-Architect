# RETRIEVAL STRATEGY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). The general case of [docs/ai-retrieval/RULE_INDEX_SPEC.md](../ai-retrieval/RULE_INDEX_SPEC.md), which remains the concrete, already-authored specialization for `Engineering Rule` retrieval specifically — this document does not replace it, and any conflict between the two on `Engineering Rule` retrieval defers to `RULE_INDEX_SPEC.md`.
**Scope:** How an AI agent finds, ranks, and reasons over the full [Knowledge Graph](KNOWLEDGE_GRAPH_SPEC.md) — every artifact type, not just rules.

---

## 0. The Same Five Steps, Generalized

[`RULE_INDEX_SPEC.md`](../ai-retrieval/RULE_INDEX_SPEC.md) already established: find → rank → resolve conflicts → follow dependencies → build reasoning chains, for one artifact type. This document is that same five-step shape, generalized across all of them, plus the two additional concerns the task names explicitly (version filtering, trust weighting) that matter more once multiple artifact types with different trust profiles are in play together.

---

## 1. Filtering

Before any ranking runs, the candidate set is filtered on hard, non-negotiable criteria — cheap to apply, and applied first so ranking never wastes work on candidates that could never qualify:

- **`status` filter** — only `validated`/`approved` artifacts (see [KNOWLEDGE_VALIDATION_SPEC.md](KNOWLEDGE_VALIDATION_SPEC.md)); `rejected` and `pending-conflict-resolution` are excluded outright, never merely down-ranked.
- **Version filter** — see [§6](#6-version-filtering).
- **Trust floor** — a query may specify a minimum acceptable Trust Score (defaulting to [KNOWLEDGE_VALIDATION_SPEC.md § 5](KNOWLEDGE_VALIDATION_SPEC.md#5-trust-verification)'s per-type thresholds); a high-stakes query (e.g., feeding a code-generation decision) may raise this floor explicitly.
- **Artifact-type filter** — a query asking "what's the exact signature" restricts to `Knowledge API`; a query asking "how do I approach this" allows `Pattern`/`Best Practice`/`Workflow`. Query-shape-to-type mapping is the consuming `Agent`'s responsibility, informed by the type descriptions in [KNOWLEDGE_ARTIFACTS.md § 2](KNOWLEDGE_ARTIFACTS.md#2-artifact-types).

---

## 2. Ranking

Composite score, per [EMBEDDING_STRATEGY.md § 7](EMBEDDING_STRATEGY.md#7-re-ranking-strategy):

```
rank_score = similarity × confidence × trust_boost × type_priority(query_shape) × recency_factor
```

**Trust weighting, explicit:** `trust_boost` is not a flat multiplier — it is steeper for artifact types where being wrong is costlier. A `Knowledge API` (a claimed function signature) with a marginal trust score is far more dangerous to rank highly than an `Example` with the same marginal trust score, because code generated from a wrong signature fails loudly and immediately, while a mediocre example merely under-inspires. `trust_boost`'s curve is therefore parameterized per artifact type, not global — steep for `Knowledge API` and `Engineering Rule` candidates, shallow for `Example`/`Workflow`.

**`Engineering Rule` results specifically** are ranked using [`RULE_INDEX_SPEC.md § 2`](../ai-retrieval/RULE_INDEX_SPEC.md#2-rank-them)'s existing formula unchanged (Priority/`risk_boost`, `status_factor`) — this document's general formula and that one's specific formula are the same family, not two competing rankings an agent has to reconcile.

---

## 3. Conflict Handling

A result set containing two artifacts linked by an unresolved `conflicts_with` edge ([KNOWLEDGE_GRAPH_SPEC.md § 3](KNOWLEDGE_GRAPH_SPEC.md#3-relationship-vocabulary)) is never silently collapsed to "just return the higher-ranked one." Both are surfaced, explicitly labeled as conflicting, with whatever resolution status their `Knowledge Conflict` record carries (`resolved-deterministic`, `resolved-human`, or `undecided`) per [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md) — an `undecided` conflict reaching an agent is presented as exactly that, never picked for the agent by the retrieval layer itself. This is the same non-negotiable stance [RULE_INDEX_SPEC.md § 3](../ai-retrieval/RULE_INDEX_SPEC.md#3-resolve-conflicts) already takes for rule-level conflicts, applied to every artifact type here.

---

## 4. Dependency Expansion

For every artifact in the ranked result set, recursively pull in every artifact named in its `depends_on` edges ([KNOWLEDGE_GRAPH_SPEC.md § 3](KNOWLEDGE_GRAPH_SPEC.md#3-relationship-vocabulary)) — regardless of whether the dependency independently ranked highly enough to surface on its own — exactly [RULE_INDEX_SPEC.md § 4](../ai-retrieval/RULE_INDEX_SPEC.md#4-follow-dependencies)'s existing rule, generalized to any artifact type depending on any other. Traversal is bounded-depth and cycle-safe by construction, since [KNOWLEDGE_GRAPH_SPEC.md § 3](KNOWLEDGE_GRAPH_SPEC.md#3-relationship-vocabulary) rejects `depends_on` cycles at write time rather than merely tolerating them at read time.

---

## 5. Reasoning Chains

The expanded working set from [§4](#4-dependency-expansion) is topologically ordered by its `depends_on` edges and presented as an ordered chain — the general-case version of [RULE_INDEX_SPEC.md § 5](../ai-retrieval/RULE_INDEX_SPEC.md#5-build-reasoning-chains)'s worked example, now potentially mixing artifact types in one chain, e.g.:

```
Proposal: "add a field to track a custom approval state on Sales Invoice"

Reasoning chain:
 1. KA-0091 (Sales Invoice DocType schema)        — what fields already exist
 2. PAT-0014 (Workflow-based state modeling)       — implements the general shape
 3. R003 (Low-Code / Configuration Over Code)      — the Engineering Rule governing whether this needs code at all
 4. WF-0006 ("Adding a Workflow state" procedure)  — depends_on PAT-0014, the concrete steps
```

Mixed-type chains are expected and correct — the whole point of one graph instead of per-type silos is that a real proposal rarely needs only rules, or only API facts, in isolation.

---

## 6. Version Filtering

Every query carries an explicit or defaulted **target version** (defaulted to the latest `Stable`-tagged framework version unless the query states otherwise). Filtering happens in two passes:

1. **Hard exclude** — any artifact whose `version.applies_to` is confirmed (`explicit`/`stated` confidence, per [KNOWLEDGE_PIPELINE.md § 4](KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)) incompatible with the target version is removed from the candidate set entirely, before ranking — never merely down-ranked, because a wrong-version `Knowledge API` signature is not "less relevant," it is actively wrong for the query at hand.
2. **Soft demote** — an artifact with only `inferred`-confidence version scoping is retained but demoted in ranking and flagged `version-uncertain` in the result, since hard-excluding it risks losing a genuinely-applicable fact over a scoping guess that was never confident to begin with.

A query explicitly requesting historical/superseded knowledge (e.g., "how did this work in v13") bypasses [§1](#1-filtering)'s default exclusion of `superseded`-status artifacts entirely — historical retrieval is a first-class, explicitly-invoked mode, not a side effect of loose filtering.

---

## 7. What Agents Receive

Per [PROJECT_CHARTER.md § AI First Principles](../../PROJECT_CHARTER.md#ai-first-principles) ("Rules must change behavior, not just inform it"), a retrieval response is never a bare ranked list — it is the reasoning chain from [§5](#5-reasoning-chains), each entry carrying its `confidence`, `trust` origin, and any flagged conflicts or version uncertainty inline, so the consuming `Agent` can (and per that same principle, must) surface a genuine conflict or low-confidence result explicitly rather than presenting retrieved content as uniformly certain.
