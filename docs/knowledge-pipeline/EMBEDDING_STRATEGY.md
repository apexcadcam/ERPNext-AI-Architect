# EMBEDDING STRATEGY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). Operates on artifacts that have passed [KNOWLEDGE_VALIDATION_SPEC.md](KNOWLEDGE_VALIDATION_SPEC.md) and entered the [Knowledge Graph](KNOWLEDGE_GRAPH_SPEC.md). Feeds [RETRIEVAL_STRATEGY.md](RETRIEVAL_STRATEGY.md).
**Scope:** What is embedded, what never is, and how — no model selection, no vector-database product choice, no running code. This is the same "architecture, not implementation" boundary already held in [docs/ai-retrieval/RULE_INDEX_SPEC.md § 1](../ai-retrieval/RULE_INDEX_SPEC.md#1-find-relevant-rules), generalized here from `Engineering Rule` alone to every artifact type.

---

## 1. What Gets Embedded

Exactly one thing per artifact: a **deterministic, reproducible text composition**, generated the same way `RM.ai_retrieval.embedding_text` already is for rules — never the artifact's raw stored fields fed directly to an embedding model ad hoc, because two different runs over the same artifact must produce the identical embedding input, or staleness detection ([§4](#4-version-aware-embeddings)) has nothing stable to compare against.

**Composition template, by artifact type:**

| Artifact type | Embedding text composition |
|---|---|
| Knowledge API | `interface_kind + name + signature + parent DocType/module + tags` |
| Pattern / Anti-Pattern | `title + problem it solves + solution shape summary + tags` |
| Best Practice | `title + recommendation + scope + tags` |
| Example | `title + what it demonstrates + implements-linked artifact's name + tags` |
| Workflow | `title + step summary (ordered) + tags` |
| Engineering Rule (existing, unchanged) | `RM.ai_retrieval.embedding_text`, exactly as already defined in [METADATA_SCHEMA.yaml](../ai-retrieval/METADATA_SCHEMA.yaml) — this strategy does not redefine it, only incorporates it |

Only **validated, non-rejected, non-`undecided`-conflict** artifacts are embedded — an artifact still awaiting [KNOWLEDGE_VALIDATION_SPEC.md § 7](KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate) does not enter the embedding index yet, because an unapproved candidate showing up in similarity search results would be functionally indistinguishable from an approved fact to whatever consumes retrieval output.

---

## 2. What Should Never Be Embedded

- **Raw, unprocessed `Knowledge Document` content** — only artifacts extracted *from* a `KD`, never the `KD` itself; embedding raw acquisition-stage text would let un-extracted, unvalidated noise leak into semantic search.
- **`rejected`-status artifacts** — from any [KNOWLEDGE_VALIDATION_SPEC.md](KNOWLEDGE_VALIDATION_SPEC.md) stage, regardless of how semantically relevant their content might otherwise be. A hallucination-risk artifact must not become findable via similarity search just because it "sounds right."
- **Content from any source in [`KNOWLEDGE_SOURCE_CATALOG.md § 10`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#10-sources-that-should-never-be-used)** — enforced structurally (these sources have no acquisition method at all, per [KNOWLEDGE_PIPELINE.md § 1](KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type)), restated here because an embedding index is the layer where an accidental leak would be hardest to notice after the fact.
- **`vision-roadmap`-tagged conference content** (per [KNOWLEDGE_EXTRACTION_SPEC.md § 8](KNOWLEDGE_EXTRACTION_SPEC.md#8-tutorials-videos-and-conference-talks)) — excluded from the default technical-retrieval embedding index; may exist in a separate, explicitly-labeled "roadmap/vision" index if a future consumer specifically wants product-direction content, but never mixed into the same similarity space as technical fact retrieval.
- **Superseded/deprecated artifacts, by default** — retained in the graph for provenance ([KNOWLEDGE_GRAPH_SPEC.md § 4](KNOWLEDGE_GRAPH_SPEC.md#4-node-creation-and-update-rules)), but excluded from the default embedding index; available only through an explicit historical-query index, mirroring [RULE_INDEX_SPEC.md § 2](../ai-retrieval/RULE_INDEX_SPEC.md#2-rank-them)'s exclusion of `Deprecated` rules from default results.
- **Any raw credential, token, or personally-identifying detail** that acquisition might incidentally capture (e.g., a forum post's author contact info) — stripped at [KNOWLEDGE_PIPELINE.md § 3](KNOWLEDGE_PIPELINE.md#3-cleaning-stage-2-detail)'s Cleaning stage, before embedding is even reachable, not filtered at embedding time as a last resort.

---

## 3. Chunking Strategy

**Chunk boundaries are artifact boundaries, not token windows.** Because [KNOWLEDGE_EXTRACTION_SPEC.md](KNOWLEDGE_EXTRACTION_SPEC.md) already breaks raw content down into well-typed, appropriately-scoped artifacts (one `Knowledge API` per interface, one `Pattern` per solution shape, one `Workflow` per procedure) before this stage ever runs, a fixed-size sliding-window chunker over raw text — the usual RAG default — is deliberately **not used**. An artifact *is* the chunk; its size is however large the actual interface/pattern/procedure genuinely is, not an arbitrary token count that might split a DocType schema mid-field or a procedure mid-step.

**Exception — oversized artifacts:** a `Workflow` with an unusually long step sequence, or a `Knowledge API` for a very large DocType, is split at its own internal structural boundaries (per-step, per-field-group) rather than at an arbitrary token count — each sub-chunk retains a `part_of` pointer back to the parent artifact so retrieval can reassemble or cite the whole when needed.

---

## 4. Version-Aware Embeddings

Every embedding carries its source artifact's `version.applies_to` and `version` confidence band ([KNOWLEDGE_PIPELINE.md § 4](KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)) as **filterable metadata alongside the vector**, never encoded into the vector itself — semantic similarity should find "how do I register a whitelisted method" regardless of which version's phrasing was used to ask; version scoping is then applied as a hard filter *after* similarity ranking, per [RETRIEVAL_STRATEGY.md § 6](RETRIEVAL_STRATEGY.md#6-version-filtering). Encoding version into the vector itself (e.g., prepending "as of v15:" to the embedded text) is explicitly rejected — it would make cross-version comparison ("what changed between v14 and v15") harder, not easier, by scattering semantically-identical content across the vector space by version alone.

---

## 5. Metadata Strategy

Every embedding is stored with its artifact's `id`, `type`, `version.applies_to`, `confidence`, `tags`, and originating `Knowledge Source`'s Trust Score attached as structured, filterable metadata (not embedded text) — this is what makes [§6](#6-hybrid-search-strategy) and [RETRIEVAL_STRATEGY.md § 1](RETRIEVAL_STRATEGY.md#1-filtering)'s pre-similarity filtering possible without a second lookup.

---

## 6. Hybrid Search Strategy

Generalizes the two-pass approach already established in [RULE_INDEX_SPEC.md § 1](../ai-retrieval/RULE_INDEX_SPEC.md#1-find-relevant-rules) from `Engineering Rule` alone to the full graph:

- **Pass A — deterministic/lexical.** Exact and near-exact match against structured fields (`Knowledge API` names, `tags`, extracted identifiers like a specific DocType or method name) — cheap, precise, no embedding model needed. Best for queries that already name the exact thing they're asking about ("what does `frappe.db.set_value` do").
- **Pass B — semantic/dense.** Embedding similarity against the [§1](#1-what-gets-embedded) composition, for paraphrased or conceptual queries with no exact term match.

Both passes run against the same metadata-filtered candidate set ([§5](#5-metadata-strategy)) — version and trust-threshold filtering happens *before* either pass runs, not after, keeping both passes cheap by construction.

---

## 7. Re-Ranking Strategy

After Pass A/B produce a merged candidate set, re-rank by the same composite-score family already established for rules in [RULE_INDEX_SPEC.md § 2](../ai-retrieval/RULE_INDEX_SPEC.md#2-rank-them), generalized:

```
rank_score = similarity_or_match_strength
           × artifact.confidence           (from KNOWLEDGE_VALIDATION_SPEC.md § 8)
           × trust_boost(source_trust)
           × type_priority(artifact.type)   -- e.g. Knowledge API ranks above Example at equal similarity, for a "what's the exact signature" query
           × recency_factor(version_match)
```

`type_priority` is query-shape-dependent, not fixed — [RETRIEVAL_STRATEGY.md § 2](RETRIEVAL_STRATEGY.md#2-ranking) defines how the consuming agent's query shape selects which artifact type should be boosted for that specific query, rather than this document fixing one global type ordering that would be wrong for half of all queries.
