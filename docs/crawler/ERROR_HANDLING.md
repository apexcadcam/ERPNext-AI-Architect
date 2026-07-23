# ERROR HANDLING

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). The categorization every [`CRAWLER_PIPELINE.md`](CRAWLER_PIPELINE.md) stage's failure routes into, and what [`RETRY_POLICY.md`](RETRY_POLICY.md) is deciding retryability *against*.
**Scope:** Six categories, each with a fixed disposition. No code.

---

## 0. Every Category Shares One Rule

Per [`CRAWLER_PIPELINE.md § 10`](CRAWLER_PIPELINE.md#10-failure-is-a-terminal-state-per-stage-not-a-dropped-item): a categorized failure is retained with its category and stage, never silently discarded. The categories below differ only in *what happens next*, never in *whether the failure is recorded*.

---

## 1. Recoverable

**Definition:** a failure with a real chance of succeeding on a later attempt, with no change to how the request itself is made — network blips, `5xx`, timeouts, connection resets, oversized-response aborts.
**Disposition:** routed to [`RETRY_POLICY.md § 1`](RETRY_POLICY.md#1-failure-mode--retry-behavior) immediately.
**Terminal state if retries exhaust:** demoted to a source-health signal, per [`RETRY_POLICY.md § 3`](RETRY_POLICY.md#3-circuit-breaker)'s circuit breaker — not immediately treated as Permanent, since exhausting *this attempt's* retry budget doesn't mean the underlying condition won't clear on the *next scheduled crawl*.

## 2. Permanent

**Definition:** a failure no amount of retrying will fix without an external change — `404`, a malformed request the connector itself constructed, a source confirmed removed.
**Disposition:** never retried ([`RETRY_POLICY.md § 4`](RETRY_POLICY.md#4-what-is-never-retried)). Logged once, surfaced in [`OBSERVABILITY.md`](OBSERVABILITY.md), and — if the failing URI was previously a valid, crawled `Knowledge Document`'s source — feeds [`KNOWLEDGE_REFRESH_POLICY.md § 5`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#5-deprecation-and-retirement)'s deprecation path rather than being treated as a crawl bug.

## 3. Authentication

**Definition:** `401`/`403` outside [`RETRY_POLICY.md § 1`](RETRY_POLICY.md#1-failure-mode--retry-behavior)'s temporary-ban pattern, or a connector's declared credential ([`SOURCE_CONNECTOR_SPEC.md § 1.2`](SOURCE_CONNECTOR_SPEC.md#12-authentication)) rejected outright.
**Disposition:** never retried automatically — a credential that's invalid now will not become valid by trying again. Distinct from Permanent because the *fix* is different and actionable (rotate/renew a credential) rather than "this content no longer exists." Escalated directly to an operator-visible alert, per [`OBSERVABILITY.md § Health Checks`](OBSERVABILITY.md#4-health-checks) — a whole connector, not just one item, is likely affected.

## 4. Version Mismatch

**Definition:** the content fetched doesn't match what Discovery expected to find at that version-scoped location — e.g., a version-pinned API endpoint that started returning a different version's data, or a documentation page whose URL path segment claims one version while its content explicitly states another.
**Disposition:** not a crawl failure in the usual sense — the fetch succeeded, the *content* is the problem. Routed onward as a Crawl Item with `document_metadata.version` confidence forced to `inferred`-or-lower ([`CRAWLER_PIPELINE.md § 7`](CRAWLER_PIPELINE.md#7-extract-metadata)) rather than trusting the mismatched signal, and flagged for [`KNOWLEDGE_CONFLICT_RESOLUTION.md § 2`](../knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md#2-two-documentation-versions-disagree)'s downstream handling — this category is where the Crawler Framework and the Knowledge Pipeline's conflict machinery meet, deliberately, rather than the crawler silently guessing which version is correct.

## 5. Parsing

**Definition:** [`PARSER_SPEC.md § 5`](PARSER_SPEC.md#5-failure-mode)'s explicit parser failure — content that downloaded successfully and passed transport [`Validate`](CRAWLER_PIPELINE.md#4-validate) but that the bound parser cannot structure.
**Disposition:** the Crawl Item halts at Parse, is retained with the parser's failure detail, and — if this is the *first* time this content-type has failed for this connector — is flagged for [`CRAWLER_PLUGIN_SYSTEM.md § 3`](CRAWLER_PLUGIN_SYSTEM.md#3-what-a-new-connector-must-provide)'s "does this content-type need a new parser" review, distinguishing a one-off malformed document from a systematic parser gap.

## 6. Corrupted Document

**Definition:** [`CRAWLER_PIPELINE.md § 4`](CRAWLER_PIPELINE.md#4-validate)'s transport-level validation failure — truncated content, a content-type mismatch between declared and actual, a checksum/length mismatch.
**Disposition:** never proceeds to Normalize. Retried once (a corrupted download is often itself a transient network artifact, per [Recoverable](#1-recoverable)) before being retained as a terminal Corrupted-Document failure — distinct from Parsing because the problem is detected *before* any structural interpretation is attempted, and distinct from Permanent because a corrupted transfer, unlike a genuinely removed resource, plausibly succeeds on the very next attempt.

---

## 7. Category Summary

| Category | Retried? | Escalates to |
|---|---|---|
| Recoverable | Yes, per [`RETRY_POLICY.md`](RETRY_POLICY.md) | Source-health signal if exhausted |
| Permanent | No | [`KNOWLEDGE_REFRESH_POLICY.md`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md) deprecation path |
| Authentication | No | Operator alert |
| Version Mismatch | N/A — not a fetch failure | [`KNOWLEDGE_CONFLICT_RESOLUTION.md`](../knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md) |
| Parsing | No | Parser-gap review |
| Corrupted Document | Once | Terminal failure record |
