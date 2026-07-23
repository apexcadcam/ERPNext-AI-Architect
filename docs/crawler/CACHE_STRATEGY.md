# CACHE STRATEGY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). Governs the `cache/` zone defined in [`STORAGE_LAYOUT.md § 1`](STORAGE_LAYOUT.md#1-three-zones-three-different-durability-guarantees).
**Scope:** How the framework avoids redundant work — ETag/Last-Modified conditional requests, incremental crawls, and resuming an interrupted crawl. No code.

---

## 1. ETag / Last-Modified

For every successfully-downloaded resource, the response's `ETag` and/or `Last-Modified` header (whichever the source provides — some provide both, some neither) is written to `cache/etag/<connector_id>/<dedupe_key_hash>.json` alongside the resulting `content_hash`. On the next scheduled crawl of that same URI, [`DOWNLOAD_POLICY.md § 8`](DOWNLOAD_POLICY.md#8-conditional-requests)'s conditional request is sent; a `304` response confirms nothing changed without transferring the body at all, and only `last_seen_at` is updated. A source providing neither header falls back to [§2](#2-incremental-crawls-without-conditional-request-support)'s weaker guarantee.

## 2. Incremental Crawls Without Conditional-Request Support

Not every source type supports `ETag`/`Last-Modified` — an API-based source instead uses its own `since_parameter`/`webhook`/cursor mechanism, per [`SOURCE_CONNECTOR_SPEC.md § 1.9`](SOURCE_CONNECTOR_SPEC.md#19-incremental-sync-strategy). Whichever mechanism a connector declares, the shared principle is the same: **a full re-crawl is the fallback of last resort**, run only when a connector declares `sync_kind: full_rescan` outright (appropriate for small, cheaply-re-crawlable sources) or when a smarter mechanism's checkpoint is lost/corrupted.

## 3. Content-Hash Is the Final Authority, Not the Cache Entry

A cache hit (matching `ETag`, or a `webhook` reporting "unchanged") is a strong *hint* to skip re-downloading, never treated as proof the content is unchanged in a way that would justify skipping [`CRAWLER_PIPELINE.md § 4`](CRAWLER_PIPELINE.md#4-validate) entirely — the cache exists to avoid unnecessary *network* work, not to avoid unnecessary *correctness* work. If a download does proceed (cache miss, or periodic full re-verification per [§5](#5-periodic-re-verification)), the resulting content-hash — not the cache metadata that predicted a match — is what [`STORAGE_LAYOUT.md § 2`](STORAGE_LAYOUT.md#2-path-structure)'s content-addressing actually keys on.

## 4. Resuming an Interrupted Crawl

A crawl run's Queue-stage frontier (every discovered-but-not-yet-processed Crawl Item) is checkpointed to `cache/resume/<crawl_run_id>/frontier_checkpoint.json` at a regular interval, not only at clean shutdown — a killed process (crash, forced termination, infrastructure failure) loses at most the interval's worth of in-flight progress, never the entire run. On restart, a crawl run detects an existing checkpoint for its `crawl_run_id` and resumes the frontier from it rather than restarting Discovery from scratch — Discovery *may* still re-run (cheap, and self-correcting if new content appeared since the crash), but every item already past Persist is skipped via [§1](#1-etag--last-modified)'s cache, not re-processed.

## 5. Periodic Re-Verification

Even a source with a reliable `webhook`-based incremental sync is periodically fully re-scanned (cadence per [`KNOWLEDGE_REFRESH_POLICY.md § 1`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#1-refresh-cadence-by-source-type)'s type-level table) — webhooks and conditional requests are both mechanisms that can silently fail (a missed webhook delivery, a misconfigured cache header) without producing an error the framework would otherwise notice; periodic full re-verification is the backstop that catches silent staleness a purely event-driven cache strategy alone cannot.

## 6. Cache Is Never a Source of Truth

Restated from [`STORAGE_LAYOUT.md § 4`](STORAGE_LAYOUT.md#4-retention): the entire `cache/` zone can be deleted at any time with zero data loss beyond one extra round of conditional requests on the next crawl — nothing in this document describes information that isn't reconstructable from `raw/` plus a live re-check of the source.
