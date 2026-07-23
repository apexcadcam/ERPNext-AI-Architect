# DOWNLOAD POLICY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). Governs [`CRAWLER_PIPELINE.md § 3`](CRAWLER_PIPELINE.md#3-download)'s behavior.
**Scope:** How a single fetch behaves, before retry logic ([`RETRY_POLICY.md`](RETRY_POLICY.md)) or rate budgeting ([`RATE_LIMITING.md`](RATE_LIMITING.md)) even enter the picture — this document is what happens *within* one attempt.

---

## 1. Concurrency

Bounded **per connector** and **per host**, independently — a connector may run many concurrent fetches against a multi-host source type (e.g., a marketplace directory pointing at many different repositories) while still respecting a single host's own concurrency ceiling. Global concurrency is the sum across active connectors, capped separately so one connector's burst can never starve another's [`RATE_LIMITING.md`](RATE_LIMITING.md) budget.

## 2. Timeout Policy

Two timeouts, not one: a **connect timeout** (fails fast if the host is unreachable at all) and a **total-transfer timeout** (bounds a slow-but-connected download, e.g., a large PDF over a throttled connection) — a single combined timeout would either fail fast connections too eagerly or let a stalled slow connection hang indefinitely, depending on which failure mode it was tuned for. Timeout values are a [`SOURCE_CONNECTOR_SPEC.md`](SOURCE_CONNECTOR_SPEC.md)-declared property of the connector's crawling policy, not a single global constant — a video-platform connector's expected transfer size is not a documentation-page connector's.

## 3. Redirect Handling

Followed, up to a fixed hop limit, with the **final URL after redirects** recorded in `response_metadata` (per [`CRAWLER_PIPELINE.md § 0`](CRAWLER_PIPELINE.md#0-the-crawl-item--one-contract-nine-consumers)'s item contract) — this is what lets [`Extract Metadata`](CRAWLER_PIPELINE.md#7-extract-metadata) record the *canonical* URL, not the one originally queued, and what lets [`Validate`](CRAWLER_PIPELINE.md#4-validate) detect an authentication/paywall redirect masquerading as success (a redirect chain terminating at a login page is a transport-validation failure, not a successful fetch of that login page's content).

## 4. Content-Type Validation

The declared `Content-Type` response header is checked against the [`SOURCE_CONNECTOR_SPEC.md § 1.5`](SOURCE_CONNECTOR_SPEC.md#15-crawling-policy)-declared `allowed_content_types` for that connector **before** the body is fully downloaded wherever the transport allows a HEAD-request or early-header check — a connector expecting JSON that receives `text/html` is rejected at the earliest possible point, not after downloading a full unwanted payload.

## 5. Size Limits

A per-connector maximum payload size (declared, not global) — exceeding it aborts the download as [`ERROR_HANDLING.md § Recoverable`](ERROR_HANDLING.md#1-recoverable) with a distinct reason ("oversized"), never silently truncated and passed forward as if complete (a truncated document silently treated as complete is exactly the kind of corrupted-but-undetected input [`CRAWLER_PIPELINE.md § 4`](CRAWLER_PIPELINE.md#4-validate) exists to catch, and Download must not create a case Validate can't detect).

## 6. `robots.txt` Compliance

For any HTTP-crawled, non-API source type: fetched once per host per crawl session, cached for that session's duration, and its `Disallow` rules and `Crawl-delay` directive are **absolute** — this is not a configurable-away setting, per [`SOURCE_CONNECTOR_SPEC.md § 1.5`](SOURCE_CONNECTOR_SPEC.md#15-crawling-policy)'s hard-required `true` for this source-type class, inherited unchanged from [`KNOWLEDGE_PIPELINE.md § 1`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type).

## 7. User-Agent Policy

Every request identifies itself truthfully — a descriptive, project-attributed User-Agent string, never a spoofed browser identity. A source that blocks the honest identifier is a source this framework does not crawl around; it is logged as a [`§ Authentication`](ERROR_HANDLING.md#3-authentication)-adjacent failure and surfaced, never bypassed. This is a direct extension of this project's standing refusal to "quietly pick convenience over the documented standard" ([`PROJECT_CHARTER.md § AI First Principles`](../../PROJECT_CHARTER.md#ai-first-principles)), applied to crawling etiquette specifically.

## 8. Conditional Requests

`If-None-Match`/`If-Modified-Since` headers are sent whenever [`CACHE_STRATEGY.md`](CACHE_STRATEGY.md) holds a prior ETag/Last-Modified for the target URI — a `304 Not Modified` response short-circuits the rest of the Download stage entirely (no body to validate, normalize, or parse), updating only the cache entry's `last_seen_at`.
