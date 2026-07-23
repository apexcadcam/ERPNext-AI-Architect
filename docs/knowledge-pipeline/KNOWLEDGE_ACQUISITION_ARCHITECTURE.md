# KNOWLEDGE ACQUISITION ARCHITECTURE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [PROJECT_CHARTER.md](../../PROJECT_CHARTER.md) and [ENGINEERING_META_MODEL.md](../../ENGINEERING_META_MODEL.md). Records the decision behind this architecture's shape in [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md). This document is the entry point to the nine documents beneath it — read it first.
**Scope:** The complete pipeline from `Knowledge Source` to `AI Agent`. No implementation, no crawling code, no running system — architecture and specification only, per the task's own constraint.

---

## 1. What This Is, and Isn't

This is the architecture for turning the 48 sources already identified and scored in [`knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) into structured, validated, version-aware, retrievable knowledge — deterministically, auditably, and traceably, per the task's explicit constraints. It is not: a rewrite of this repository's existing Rule format (that remains frozen, see [PROJECT_CHARTER.md § Architecture Freeze v1.0](../../PROJECT_CHARTER.md#architecture-freeze-v10)), a competing knowledge model (every new concept here either reuses an existing Meta-Model artifact type or is added additively, per [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md)), or a running crawler (nothing in this document set has been executed — no source has been acquired, no artifact instance exists).

---

## 2. The Pipeline, End to End

```
Knowledge Source (KS)                                    ─┐
    │  [existing type, already populated — 48 sources]     │ knowledge-sources/
    ▼                                                       │ KNOWLEDGE_SOURCE_CATALOG.md
Acquisition                                                ─┘
    │  [per source-type method: git, HTTP crawl, API]      ─┐
    ▼                                                        │
Cleaning                                                     │
    │  [strip noise, normalize encoding]                    │ KNOWLEDGE_PIPELINE.md
    ▼                                                        │
Normalization                                                │
    │  [canonical structure, version stamping]              │
    ▼                                                        │
Deduplication  ──▶  Knowledge Document (KD)                 ─┘
    │
    ▼
Knowledge Extraction                                        ─┐
    │  [per source-type: docs, code, issues, PRs, release    │ KNOWLEDGE_EXTRACTION_SPEC.md
    │   notes, forum, marketplace, tutorials, video, talks]  │
    ▼                                                        │
Pattern Extraction                                           │
    │  [2nd pass: recurring shape across ≥2 artifacts]       │
    ▼                                                        ─┘
    ├──────────────► Knowledge Conflict (KC)  ───┐
    │                                              │  KNOWLEDGE_CONFLICT_RESOLUTION.md
    ▼                                              ▼  [precedence hierarchy, 5 named
Conflict Resolution ◀─────────────────────────────┘   scenarios, "undecided" escalation]
    │
    ▼
Validation                                                  ─┐
    │  [8 gates: schema → dup → version-conflict →           │ KNOWLEDGE_VALIDATION_SPEC.md
    │   source-verify → trust-verify → engineering-review →  │
    │   human-approval → confidence-scoring]                 │
    ▼                                                        ─┘
Knowledge Graph (KG nodes + typed edges)                    ─┐  KNOWLEDGE_GRAPH_SPEC.md
    │  [depends_on / implements / extends / replaces /       │  [+ KNOWLEDGE_ARTIFACTS.md
    │   conflicts_with / related_to / deprecated_by /        │   for the artifact schemas
    │   supersedes / references]                             │   every node wraps]
    ▼                                                        ─┘
Embeddings                                                  ─┐  EMBEDDING_STRATEGY.md
    │  [artifact-boundary chunking, version-aware,           │
    │   hybrid lexical+semantic]                             │
    ▼                                                        ─┘
Retrieval                                                    ─┐  RETRIEVAL_STRATEGY.md
    │  [filter → rank → handle conflicts → expand             │  (generalizes the existing
    │   dependencies → build reasoning chains]                │  docs/ai-retrieval/RULE_INDEX_SPEC.md)
    ▼                                                        ─┘
AI Agents
    (existing Agent artifact type, unchanged — composed
     from Skills, which compose Engineering Rules, per
     ENGINEERING_META_MODEL.md's existing Knowledge Hierarchy)

     [Refresh — KNOWLEDGE_REFRESH_POLICY.md — runs continuously
      alongside every stage above: cadence by source type,
      staleness propagation, breaking-change propagation,
      deprecation/retirement]
```

---

## 3. Document Map

| Document | Answers |
|---|---|
| [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md) | This document — the whole shape, and how it relates to what already exists. |
| [KNOWLEDGE_PIPELINE.md](KNOWLEDGE_PIPELINE.md) | How is raw content acquired, cleaned, normalized, and deduplicated — per source? |
| [KNOWLEDGE_ARTIFACTS.md](KNOWLEDGE_ARTIFACTS.md) | What artifact types exist, what does every one of them carry (ID, provenance, confidence, relationships)? |
| [KNOWLEDGE_EXTRACTION_SPEC.md](KNOWLEDGE_EXTRACTION_SPEC.md) | Exactly what gets pulled out of each of the ten source types — and what never does? |
| [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md) | When two sources disagree, what wins, deterministically? |
| [KNOWLEDGE_VALIDATION_SPEC.md](KNOWLEDGE_VALIDATION_SPEC.md) | What eight gates does every artifact pass through before it's trusted? |
| [KNOWLEDGE_GRAPH_SPEC.md](KNOWLEDGE_GRAPH_SPEC.md) | How do artifacts relate to each other, structurally? |
| [EMBEDDING_STRATEGY.md](EMBEDDING_STRATEGY.md) | What gets embedded, what never does, and how? |
| [RETRIEVAL_STRATEGY.md](RETRIEVAL_STRATEGY.md) | How does an agent actually find, rank, and reason over all of this? |
| [KNOWLEDGE_REFRESH_POLICY.md](KNOWLEDGE_REFRESH_POLICY.md) | How often does each source type get re-checked, and what happens when something changes? |

---

## 4. Relationship to Existing, Frozen Architecture

This pipeline is **additive**, following the same policy established for [`docs/ai-retrieval/`](../ai-retrieval/) in [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md):

- **`rules/*.md` remains untouched and authoritative.** No stage of this pipeline may set `Status: Stable` on an `Engineering Rule`. A rule-shaped candidate is drafted and stopped at `Draft`, per [KNOWLEDGE_ARTIFACTS.md § 2.9](KNOWLEDGE_ARTIFACTS.md#29-engineering-rule-candidate-not-a-pipeline-native-type) and [KNOWLEDGE_VALIDATION_SPEC.md § 7](KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate) — the existing, human-gated [Research → Engineering Rule lifecycle](../ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle) is the only path from `Draft` to `Stable`, unchanged.
- **No `KR` artifact type exists.** Per [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md), rule-shaped output routes into the existing `Engineering Rule` type rather than a parallel one.
- **`KS`, `Pattern`/`Anti-Pattern`, `Best Practice`, `Example`, `Workflow` are reused**, not duplicated under new `K*` names, for the same reason.
- **`Rule Retrieval Index` (`RIX`) is not superseded** — [KNOWLEDGE_GRAPH_SPEC.md § 1](KNOWLEDGE_GRAPH_SPEC.md#1-relationship-to-the-existing-rule-retrieval-index) makes it one artifact-type-scoped projection of the larger graph this document set defines; [RETRIEVAL_STRATEGY.md](RETRIEVAL_STRATEGY.md) defers to [`RULE_INDEX_SPEC.md`](../ai-retrieval/RULE_INDEX_SPEC.md) for any conflict on `Engineering Rule` retrieval specifically.
- **Four genuinely new artifact types** (`Knowledge Document`, `Knowledge API`, `Knowledge Conflict`, `Knowledge Graph Node`) are added to [ENGINEERING_META_MODEL.md](../../ENGINEERING_META_MODEL.md)'s catalog, additively — no existing entry edited or removed, per the same discipline ADR-0001 established.

---

## 5. Design Principles This Architecture Holds Itself To

Per the task's own constraints, restated here as standing design commitments every one of the nine subordinate documents was written against:

- **Deterministic over probabilistic, wherever a deterministic rule can be stated.** [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md)'s precedence hierarchy and [KNOWLEDGE_VALIDATION_SPEC.md](KNOWLEDGE_VALIDATION_SPEC.md)'s eight fixed-order gates exist specifically so that "which source wins" and "does this artifact qualify" are never left to an unreviewable model judgment call where a rule can instead be written down.
- **No hallucinated knowledge.** Every artifact's `source_references` must dereference to real, checkable content ([KNOWLEDGE_ARTIFACTS.md § 1](KNOWLEDGE_ARTIFACTS.md#1-the-common-envelope)), independently re-verified by [KNOWLEDGE_VALIDATION_SPEC.md § 4](KNOWLEDGE_VALIDATION_SPEC.md#4-source-verification) — an artifact that only *asserts* a source, without that source checking out, cannot pass validation.
- **Everything auditable, everything traceable to origin.** Nothing is ever deleted — failed validation, superseded facts, retired sources, and resolved conflicts are all retained with their status and reason, per [KNOWLEDGE_PIPELINE.md § 0](KNOWLEDGE_PIPELINE.md#0-stage-overview)'s standing "gate, not filter" rule, applied consistently through every document in this set.
- **Human review where it matters, automation everywhere else.** [KNOWLEDGE_VALIDATION_SPEC.md § 7](KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate) names exactly four conditions requiring a human — rule candidates, rule-contradiction escalations, unresolvable conflicts, ambiguous-confidence artifacts — and lets everything else flow through automated, audited approval. This is what makes "millions of artifacts" and "no hallucinated knowledge" simultaneously achievable: mandatory human review of every artifact would not scale; zero human review anywhere would not be auditable. The four-condition gate is this architecture's answer to that tension, not a compromise of either constraint.
- **Version-awareness as a first-class property, not an afterthought.** Every artifact carries `version.applies_to` from normalization onward ([KNOWLEDGE_PIPELINE.md § 4](KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)); it is never inferred late or bolted on at query time, precisely because [`KNOWLEDGE_SOURCE_CATALOG.md`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) already surfaced version fragmentation as a real, live risk (`KS-0001` vs. `KS-0002`) before this pipeline was designed to consume either.

---

## 6. What Happens Next (Explicitly Out of Scope Here)

This document set is architecture only. Building any of it — a real crawler, a real vector store, a real graph database, a real extraction model — is separately-scoped implementation work, to be undertaken only once this architecture itself has been reviewed, the same [Architecture Review](../../ENGINEERING_META_MODEL.md#rule-lifecycle) gate this repository already requires before a design becomes something built. Nothing in this document set should be read as claiming otherwise.
