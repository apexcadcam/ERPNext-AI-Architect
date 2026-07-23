# KNOWLEDGE GRAPH SPECIFICATION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). Defines the `Knowledge Graph Node` (`KG`) structure introduced by [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md) and the relationship vocabulary every validated artifact participates in.
**Scope:** Node and edge structure only — [RETRIEVAL_STRATEGY.md](RETRIEVAL_STRATEGY.md) defines how the graph is *queried*, not how it's shaped.

---

## 1. Relationship to the Existing `Rule Retrieval Index`

[`docs/ai-retrieval/RULE_INDEX_SPEC.md`](../ai-retrieval/RULE_INDEX_SPEC.md) already implements a graph-shaped structure — `dependency_graph` and `conflict_graph` — but scoped to `Engineering Rule` alone. This document generalizes that pattern to every artifact type in [KNOWLEDGE_ARTIFACTS.md](KNOWLEDGE_ARTIFACTS.md). The relationship is one of **containment, not replacement**: the existing `RIX` (`Rule Retrieval Index`) becomes one artifact-type-scoped *projection* of the larger graph this document defines — every `depends_on`/`conflicts_with` edge already recorded in an `RM` record's `dependencies`/`conflicts` fields is, in this graph, the identical edge between two `KG` nodes wrapping `Engineering Rule` instances. Nothing about `RM`/`RIX` changes; this document is what those structures generalize *into* once other artifact types exist alongside `Engineering Rule`.

---

## 2. Node Structure

A `Knowledge Graph Node` wraps exactly one artifact instance and holds no content of its own:

```
KG-NNNN:
  wraps: <artifact id, e.g. KA-0042, PAT-0007, R007>
  wraps_type: <artifact type>
  edges: [ { relationship, target, note, confidence_of_edge } ]
```

`confidence_of_edge` is distinct from the wrapped artifact's own `confidence` ([KNOWLEDGE_ARTIFACTS.md § 1](KNOWLEDGE_ARTIFACTS.md#1-the-common-envelope)) — a relationship can be asserted with lower certainty than the two artifacts it connects (e.g., an `extends` edge inferred from naming-convention similarity rather than an explicit statement in source).

---

## 3. Relationship Vocabulary

| Relationship | Direction | Valid between | Meaning |
|---|---|---|---|
| `depends_on` | A → B | Any → Any | Correctly reasoning about A requires also loading B. The subset of `relationships` surfaced separately as `dependencies` in the common envelope. Cycle-checked at write time — a `depends_on` cycle is rejected at graph-write, not merely detected later at query time (stricter than [RULE_INDEX_SPEC.md § 4](../ai-retrieval/RULE_INDEX_SPEC.md#4-follow-dependencies)'s query-time cycle *tolerance*, because at graph-scale a write-time reject is cheaper than repeatedly detecting the same cycle on every query). |
| `implements` | A → B | `Example`/`Pattern`/`Workflow` → `Knowledge API` | A demonstrates/realizes B's formal interface. |
| `extends` | A → B | `Knowledge API` → `Knowledge API`; `Pattern` → `Pattern` | A is a specialization/subclass/override of B. |
| `replaces` | A → B | Any → same type | A is the intended, adopted replacement for B going forward (a deliberate authoring choice, e.g. one `Pattern` explicitly written to replace another) — distinct from `supersedes` below, which is a *version-transition* fact, not an authoring choice. |
| `conflicts_with` | A ↔ B (symmetric) | Any → Any | Unresolved or resolved disagreement, per [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md). Always paired with a `Knowledge Conflict` artifact recording the resolution status. |
| `related_to` | A ↔ B (symmetric) | Any → Any | Composes with or should be read alongside — the lowest-commitment edge, used when no more specific relationship applies. Mirrors `RM.related_rules`' existing semantics. |
| `deprecated_by` | A → B | Any → same or successor type | A is no longer recommended; B is why (a newer `Knowledge API`, a `Deprecation Notice`, or nothing if removed outright with no direct replacement). |
| `supersedes` | A → B | Any → same type, same lineage | A is a newer version-scoped fact directly replacing B for current-version queries; B remains retrievable for historical/audit queries. The mechanical, non-authored counterpart to `replaces`. |
| `references` | A → B | Any → `Knowledge Document`/`Knowledge Source` | Provenance pointer — the graph-native form of the common envelope's `source_references`, materialized as a traversable edge rather than an embedded list, so provenance chains are queryable graph-wide without opening every individual artifact. |

**Directionality discipline:** every edge is stored once, in its canonical direction, with symmetric relationships (`conflicts_with`, `related_to`) stored as a single undirected edge rather than two mirrored directed ones — avoids the exact asymmetry bug this project already caught and fixed once, manually, in the `RM` layer (`R001`↔`R002`'s conflict entry required a symmetric fix during that layer's construction; this graph structure makes that class of bug structurally impossible rather than relying on manual symmetry maintenance).

---

## 4. Node Creation and Update Rules

- A `KG` node is created automatically the moment its wrapped artifact gains its first relationship edge — an artifact with zero relationships has no `KG` node, keeping the graph's size proportional to actual connectivity, not to total artifact count.
- Edges are appended, never overwritten — a relationship that later proves incorrect gains a `retracted` flag with the reason and the retraction's own provenance; it is not silently deleted, per this document's own provenance requirement applied recursively to itself.
- When [KNOWLEDGE_REFRESH_POLICY.md](KNOWLEDGE_REFRESH_POLICY.md)'s staleness propagation marks a wrapped artifact `stale`, every edge naming it as a target is annotated `target-stale` at read time — a consumer traversing `depends_on` into a stale node is told so, rather than silently receiving outdated confidence as if it were current.

---

## 5. Scale

At "millions of artifacts," this graph is a property graph, not an in-memory structure — node/edge storage and traversal are an implementation concern deferred entirely (per this document's "architecture only" scope), but the *design* constraint this specification imposes on any future implementation is: every traversal [RETRIEVAL_STRATEGY.md](RETRIEVAL_STRATEGY.md) performs must be expressible as a bounded-depth walk from a small seed set (the artifacts an initial search pass already ranked highly) — never a full-graph scan. This is the same principle already stated for the rules-only case in [RULE_INDEX_SPEC.md § 4](../ai-retrieval/RULE_INDEX_SPEC.md#4-follow-dependencies), generalized: dependency expansion is always *outward from a ranked seed*, never *inward from the whole graph*.
