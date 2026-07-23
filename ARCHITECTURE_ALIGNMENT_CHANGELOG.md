# ARCHITECTURE ALIGNMENT CHANGELOG

**Status:** Documentation-only alignment. No code, no stubs, no Runtime changes accompany this changelog.
**Trigger:** [`ARCHITECTURE_INCONSISTENCY_REPORT.md`](ARCHITECTURE_INCONSISTENCY_REPORT.md) — the Validation-vs-Extraction ordering conflict raised during Sprint 2 ("Knowledge Factory") planning.
**Decision applied:** The canonical Knowledge Factory stage order is now fixed as:

```
Extraction → Pattern Extraction → Conflict Resolution → Validation
```

This is Interpretation B from the inconsistency report — the interpretation `STUDIO_EVENT_MODEL.md § 2` and `KNOWLEDGE_VALIDATION_SPEC.md`'s own Authority line already asserted, and the interpretation `SPRINT2_IMPLEMENTATION_PLAN.md` was already assuming. This changelog brings every other frozen document into agreement with it.

---

## Documents Changed

1. `docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md`
2. `docs/knowledge-pipeline/KNOWLEDGE_PIPELINE.md`
3. `docs/knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md`
4. `docs/runtime/PIPELINE_ENGINE.md`

No other document under `docs/`, `adr/`, or the repository root was found to assert or depend on the old ordering — confirmed by a repository-wide search for every remaining occurrence of "Validation" positioned before "Extraction" in a stage sequence, re-run after the edits below, with zero matches remaining outside this changelog, the inconsistency report, and the Sprint 2 plan (all three are historical/review records of the prior state, not architecture, and are intentionally left untouched).

---

## Sections Changed

### 1. `docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md`

**§ 2, "The Pipeline, End to End"** — the ASCII pipeline diagram.

- **Reason:** This diagram was the primary source of the conflict (Document A in the inconsistency report). It placed the `Validation` block directly between `Knowledge Document (KD)` and `Knowledge Extraction`. Moved the `Validation` block to sit between `Conflict Resolution` and `Knowledge Graph`, so the diagram now reads `Knowledge Extraction → Pattern Extraction → Conflict Resolution → Validation → Knowledge Graph`, matching the decided order. No box's internal annotation text, source-document attribution, or wording was changed — only the block's vertical position moved.

**§ 3, "Document Map"** — the document-map table.

- **Reason:** This table's row order visually mirrored the diagram's (now-corrected) stage order, listing `KNOWLEDGE_VALIDATION_SPEC.md` before `KNOWLEDGE_EXTRACTION_SPEC.md` and `KNOWLEDGE_CONFLICT_RESOLUTION.md`. Reordered the `KNOWLEDGE_VALIDATION_SPEC.md` row to appear after the `KNOWLEDGE_CONFLICT_RESOLUTION.md` row, so the table's row order matches § 2's corrected diagram order. Every row's own wording ("What eight gates does every artifact pass through before it's trusted?", etc.) is unchanged — only row position moved.

### 2. `docs/knowledge-pipeline/KNOWLEDGE_PIPELINE.md`

**§ 0, "Stage Overview"** — the post-`Knowledge Document` stage-name chain.

- **Reason:** This line read `Validation → Extraction → Pattern Extraction → Conflict Resolution → Knowledge Graph → ...` (Document consistent with the old ordering, cited as supporting evidence for Document A's reading in the inconsistency report). Reordered to `Extraction → Pattern Extraction → Conflict Resolution → Validation → Knowledge Graph → ...`. No other wording in this line, or the document it's part of, was changed.

### 3. `docs/knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md`

**§ 3 ("Staleness Propagation"), cascade step 1** — the re-run stage list for a changed `Knowledge Document`.

- **Reason:** This step read "re-run through Cleaning → Normalization → Deduplication → Validation → Extraction as new content," asserting the old order in the one place this document touches the question. Reordered the two affected terms to "Cleaning → Normalization → Deduplication → Extraction → Validation." The stage list here has never included `Pattern Extraction` or `Conflict Resolution` — that abbreviation is preserved unchanged; only the relative order of `Validation` and `Extraction` was corrected, consistent with "preserve wording wherever possible."

### 4. `docs/runtime/PIPELINE_ENGINE.md`

**§ 4, "Existing Pipelines as Pipeline Definitions"** — the Pipeline Definition table.

- **Reason:** This document already contained an internal inconsistency independent of Document A: its own closing paragraph ("Discover → Download → Parse → Normalize → **Extract → Validate** → Persist → Graph → Embed → Index") already stated the now-canonical order, while the table immediately above it listed the `knowledge.validation` row *before* the `knowledge.graph_build` row — a row ordering that visually implied the opposite sequence and disagreed with the same document's own prose. Swapped the two rows so `knowledge.graph_build` (Extraction, Pattern Extraction, Conflict Resolution, Graph Node/Edge Materialization) is listed before `knowledge.validation` (the eight gates), matching this document's own closing paragraph and the now-canonical order. Every cell's wording, including the `knowledge.validation` row's "note this pipeline's stages are strictly ordered and non-parallel" annotation, is unchanged — only the two rows' relative position moved. The internal four-stage composition of `knowledge.graph_build` itself (including where "Graph Node/Edge Materialization" falls relative to Validation) was not touched — that question was not part of the decided scope and remains exactly as previously specified.

---

## Confirmation: No Architectural Behavior Changed

Every change in this document is a **reordering of already-existing text** — a diagram block's vertical position, two table rows' relative position, or two words' order within an existing arrow-chain. No new stage, gate, artifact type, module, capability, or concept was introduced. No existing stage's internal behavior (what a gate checks, what Extraction produces, what Conflict Resolution's precedence hierarchy does) was reworded or reinterpreted — those sections were already correct under the now-canonical order and were left untouched. `KNOWLEDGE_VALIDATION_SPEC.md`, `KNOWLEDGE_EXTRACTION_SPEC.md`, `KNOWLEDGE_CONFLICT_RESOLUTION.md`, and `STUDIO_EVENT_MODEL.md` required no edits at all, because their content was already internally consistent with the decision; only documents whose *sequencing* text contradicted the decision were touched.

This is a documentation-consistency fix, not a redesign: it makes the frozen architecture agree with itself on a question it had already answered three ways out of four before this change, and one way out of four after it.

No code, stub, or `runtime/` file was modified. No Sprint 2 implementation has begun.
