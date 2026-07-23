# STORAGE LAYOUT

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). Gives physical shape to where [`CRAWLER_PIPELINE.md § 8`](CRAWLER_PIPELINE.md#8-persist-raw-document)'s output actually lands, and to the `knowledge-sources/pipeline/` path [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md) reserved but left undefined.
**Scope:** Logical layout and lifecycle per content type. No storage-product choice (no mandated filesystem, object store, or database vendor) — that remains an implementation decision, deliberately deferred.

---

## 1. Three Zones, Three Different Durability Guarantees

| Zone | Contents | Mutability | Deletable? |
|---|---|---|---|
| **Raw** | Exact bytes as downloaded — HTML, PDF, images, JSON API responses, video captions | Immutable once written | Never (retained for provenance, per this project's Traceability principle applied to storage) |
| **Documents** | Normalized `Knowledge Document` instances (envelope + `normalized_text` + `structural_metadata` + `document_metadata`) | Append-only — a changed source produces a *new* document version, per [`KNOWLEDGE_REFRESH_POLICY.md § 2`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#2-version-scoping)'s "never overwrite a version-scoped artifact in place" | Never |
| **Cache** | ETag/Last-Modified records, in-flight/resumable download state, queue frontier checkpoints | Fully mutable, expected to churn | Freely — cache holds no fact not reconstructable from Raw + a re-crawl |

---

## 2. Path Structure

```
knowledge-sources/pipeline/
    raw/
        <source_type>/<connector_id>/<content_hash_prefix>/<content_hash>.<ext>
        # e.g. raw/documentation-site/frappe_docs/a1/a1b2c3....html
    documents/
        <knowledge_document_id>/
            envelope.json          # KNOWLEDGE_ARTIFACTS.md §1's envelope fields
            normalized_text.md
            structural_metadata.json
            attachments/           # images/PDFs this document references, content-addressed
    cache/
        etag/<connector_id>/<dedupe_key_hash>.json
        resume/<crawl_run_id>/frontier_checkpoint.json
```

**Content addressing** (`content_hash_prefix`/`content_hash` as the path itself, not a metadata field bolted on afterward) means identical bytes from any two sources — or two crawl runs of the same source — resolve to the same storage location automatically, giving [`CRAWLER_PIPELINE.md § 8`](CRAWLER_PIPELINE.md#8-persist-raw-document)'s idempotent-write guarantee for free, without a separate deduplication lookup at write time.

---

## 3. Mapping Content Types to Zones

| Content type | Zone(s) |
|---|---|
| Raw HTML, PDF, JSON (API responses) | `raw/` |
| Images, other downloaded assets | `raw/`, referenced from a document's `attachments/` |
| Markdown (normalized text) | `documents/<id>/normalized_text.md` |
| Metadata (envelope, structural metadata) | `documents/<id>/envelope.json`, `structural_metadata.json` |
| Attachments | `documents/<id>/attachments/`, pointing into content-addressed `raw/` — never duplicated bytes, only a reference |
| Temporary cache | `cache/` — explicitly excluded from every backup/audit process that treats `raw/`+`documents/` as the system of record |

---

## 4. Retention

`raw/` and `documents/` are retained permanently — the same "never delete, only supersede" discipline already established for `Engineering Rule`s, `RM` records, and every artifact type in [`KNOWLEDGE_ARTIFACTS.md`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md). `cache/` has no retention requirement at all — a cache entry's absence simply means the next crawl re-verifies via a fresh conditional request rather than trusting a cached ETag, per [`CACHE_STRATEGY.md`](CACHE_STRATEGY.md), at worst costing one extra request, never costing correctness.

---

## 5. Additive Note to `ENGINEERING_META_MODEL.md`

[ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md) reserved `knowledge-sources/pipeline/` with the comment *"KD/KA/KC/KG instance storage, once the pipeline is implemented."* This document refines that comment's internal shape (raw/documents/cache, per [§2](#2-path-structure)) without changing the reservation itself — still not populated, still architecture only. The refinement is applied as a small, additive edit to the same folder-mapping line, per this repository's established practice of keeping that section a living, additively-extended index (see [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md), [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md)).
