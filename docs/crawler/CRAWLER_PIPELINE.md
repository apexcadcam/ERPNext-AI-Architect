# CRAWLER PIPELINE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md), whose [§2.2](CRAWLER_ARCHITECTURE.md#22-mapping-the-crawlers-lifecycle-onto-the-knowledge-pipelines-stages) mapping this document implements in detail.
**Scope:** Nine stages, each a strict producer/consumer boundary. No stage inspects, mutates, or depends on another stage's internal state — every stage's *only* contact with its neighbors is the one fixed item contract defined below.

---

## 0. The Crawl Item — One Contract, Nine Consumers

Every stage communicates through a single evolving structure, the **Crawl Item**, that accumulates fields as it passes through the pipeline but whose fields already written are never rewritten by a later stage — only appended to. This is what makes "no stage knows internal details of another" concrete rather than aspirational: a stage declares which fields it *reads* and which it *adds*, and nothing else about its internals is visible to, or assumable by, any other stage. A stage may be replaced entirely (a new downloader implementation, a new parser) as long as it honors this same read/write contract.

| Field group | Written by stage | Consumed by |
|---|---|---|
| `candidate_uri`, `discovery_context` | Discover | Queue |
| `queue_priority`, `dedupe_key` | Queue | Download |
| `raw_bytes`, `response_metadata` (status, headers, final URL after redirects) | Download | Validate |
| `transport_valid: bool`, `validation_notes` | Validate | Normalize |
| `normalized_text`, `encoding` | Normalize | Parse |
| `structural_metadata` (headings, code-block boundaries, tables) | Parse | Extract Metadata |
| `document_metadata` (title, author, publish date, content-hash, declared/inferred version) | Extract Metadata | Persist |
| `storage_location`, `knowledge_document_id` | Persist | Emit Pipeline Event |
| *(nothing — this is the terminal stage)* | Emit Pipeline Event | External: [`KNOWLEDGE_VALIDATION_SPEC.md § 1`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#1-schema-validation) |

A Crawl Item that fails a stage does not silently vanish — see [§10](#10-failure-is-a-terminal-state-per-stage-not-a-dropped-item) below, and [ERROR_HANDLING.md](ERROR_HANDLING.md) for the full categorization.

---

## 1. Discover

**Input:** a [Source Connector](SOURCE_CONNECTOR_SPEC.md)'s discovery strategy (sitemap walk, API pagination, git ref list, RSS/feed poll — connector-specific, opaque to this stage's caller).
**Output:** zero or more Crawl Items, each carrying `candidate_uri` and `discovery_context` (why this URI was discovered — e.g., "linked from sitemap.xml," "returned by Issues API page 3").
**Responsibility:** enumerate *what exists to be crawled*, nothing more — Discover never fetches content, only identifies candidates.
**Failure handling:** a discovery-strategy failure (the sitemap itself is unreachable) is a connector-level failure, not a per-item failure — see [ERROR_HANDLING.md § Recoverable](ERROR_HANDLING.md#1-recoverable) and triggers [`KNOWLEDGE_PIPELINE.md § 2`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#2-acquisition-stage-1-detail)'s source-health flag if sustained.

## 2. Queue

**Input:** a Crawl Item with `candidate_uri` set.
**Output:** the same item, with `queue_priority` (derived from the source's [Trust Score/Priority](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) and the connector's configured crawl policy) and `dedupe_key` (a canonicalized form of the URI, used to collapse re-discovered duplicates *before* any network request is made — the cheapest possible dedup check, well before [`KNOWLEDGE_PIPELINE.md § 5`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#5-deduplication-stage-4-detail)'s content-level pass).
**Responsibility:** ordering and admission control — this is the stage [`RATE_LIMITING.md`](RATE_LIMITING.md) and [`CACHE_STRATEGY.md`](CACHE_STRATEGY.md)'s "skip if unchanged" check actually gate against, before Download ever runs.
**Failure handling:** none, structurally — Queue cannot fail in a way distinct from the system running out of storage for its own frontier, which is an operational/infrastructure concern outside this document's scope.

## 3. Download

**Input:** a Crawl Item with `queue_priority` set, released from the queue per [`RATE_LIMITING.md`](RATE_LIMITING.md)'s budget.
**Output:** the same item with `raw_bytes` and `response_metadata` populated, per [`DOWNLOAD_POLICY.md`](DOWNLOAD_POLICY.md).
**Responsibility:** exactly one network fetch (or one git operation, one API call), nothing else — no parsing, no interpretation of the response body.
**Failure handling:** the primary entry point for [`RETRY_POLICY.md`](RETRY_POLICY.md) — network failures, `429`s, `5xx`s, timeouts are all Download-stage failures, retried per that policy before ever reaching Validate.

## 4. Validate

**Transport-level only** — per [`CRAWLER_ARCHITECTURE.md § 2.4`](CRAWLER_ARCHITECTURE.md#24-two-different-things-named-validate), this is not epistemic validation.
**Input:** a Crawl Item with `raw_bytes` populated.
**Output:** the same item with `transport_valid` set, and `validation_notes` if false.
**Checks:** declared `Content-Type` matches actual content (a `.json` URL that returned an HTML error page fails here); byte count matches `Content-Length` if provided; content is not truncated (parseable to at least a well-formed top-level structure for its claimed format); not an authentication/paywall redirect masquerading as a `200`.
**Failure handling:** `transport_valid: false` routes to [`ERROR_HANDLING.md § Corrupted Document`](ERROR_HANDLING.md#6-corrupted-document) or [`§ Authentication`](ERROR_HANDLING.md#3-authentication), depending on `validation_notes` — never silently passed forward as if valid.

## 5. Normalize

**Input:** a transport-valid Crawl Item.
**Output:** the same item with `normalized_text` and `encoding` populated — realizes [`KNOWLEDGE_PIPELINE.md § 3`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#3-cleaning-stage-2-detail)'s Cleaning (strip chrome/ads/boilerplate, fix encoding) as the first half of this stage.
**Responsibility:** produce one canonical text representation regardless of which of the eight source types ([`KNOWLEDGE_PIPELINE.md § 1`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type)) produced the raw bytes — an HTML page, a Discourse JSON payload, and a GitHub API response all exit this stage as normalized text, never as three different downstream shapes.
**Failure handling:** a source-format the connector's declared parser can't recognize is [`ERROR_HANDLING.md § Parsing`](ERROR_HANDLING.md#5-parsing).

## 6. Parse

**Input:** normalized text.
**Output:** `structural_metadata` — heading hierarchy, identified code-block boundaries and declared language, tables, lists — realizing the second half of [`KNOWLEDGE_PIPELINE.md § 4`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)'s Normalization.
**Responsibility:** structure, never meaning — Parse identifies *that* a code block exists and *what language it's declared as*; it never decides *what the code demonstrates* (that's [`KNOWLEDGE_EXTRACTION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md), out of scope here).
**Format-specific behavior:** delegated to a pluggable parser keyed by content-type — see [`PARSER_SPEC.md`](PARSER_SPEC.md).

## 7. Extract Metadata

**Document-level only** — title, author/maintainer if declared, publish/update date, canonical URL, content-hash, and the version signal ([`KNOWLEDGE_PIPELINE.md § 4`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)'s `explicit`/`stated`/`inferred` confidence bands) — never a knowledge claim.
**Input:** a parsed Crawl Item.
**Output:** `document_metadata`, matching the fields [`KNOWLEDGE_ARTIFACTS.md § 1`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#1-the-common-envelope)'s envelope expects (`metadata`, `version`, part of `provenance`).
**Failure handling:** a document with no discoverable date or version signal is not rejected — it proceeds with `version` confidence `inferred` or, if truly absent, flagged `unscoped`, consistent with [`KNOWLEDGE_CONFLICT_RESOLUTION.md § 2`](../knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md#2-two-documentation-versions-disagree)'s treatment of ambiguous version scoping downstream.

## 8. Persist Raw Document

**Input:** a Crawl Item with `document_metadata` populated.
**Output:** a written [`Knowledge Document`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#21-knowledge-document) instance, physically stored per [`STORAGE_LAYOUT.md`](STORAGE_LAYOUT.md), plus `storage_location` and a freshly-assigned `knowledge_document_id` written back onto the item.
**Responsibility:** the write is atomic and idempotent — persisting the same content-hash twice is a no-op that updates only a `last_seen_at` timestamp, never a duplicate write, per [`CACHE_STRATEGY.md`](CACHE_STRATEGY.md).

## 9. Emit Pipeline Event

**Input:** a persisted Crawl Item.
**Output:** one event, `{ knowledge_document_id, connector_identity, connector_version, crawl_run_id, timestamp, storage_location }` — nothing else. This event is the entire handoff surface to the rest of the system.
**Responsibility:** decoupling. The Crawler Framework does not call into [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md) directly — it publishes an event; whatever consumes Validation's queue picks it up independently. Neither side needs to know the other's implementation, only this one event shape.

---

## 10. Failure Is a Terminal State Per Stage, Not a Dropped Item

Per this repository's standing Traceability principle, a Crawl Item that fails any stage is retained with a `failed_at_stage` marker and the [`ERROR_HANDLING.md`](ERROR_HANDLING.md) category, not discarded — the same "gate, not filter" discipline [`KNOWLEDGE_PIPELINE.md § 0`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#0-stage-overview) already established for the Knowledge Pipeline's own stages, applied here one layer earlier.
