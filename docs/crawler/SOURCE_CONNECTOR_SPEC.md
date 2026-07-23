# SOURCE CONNECTOR SPECIFICATION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). The one fixed contract every [Source Connector](CRAWLER_PLUGIN_SYSTEM.md) implements, regardless of source type — this is what makes the framework source-agnostic.
**Scope:** The declaration schema. No code, no interface syntax — a specification of what must be knowable about a connector, not how it's expressed in a programming language.

---

## 1. The Ten Required Declarations

Every connector declares all ten, even when a declaration is simply "none" — an omitted field is a defect, not an implicit default, per this project's standing discipline of stating "None" explicitly rather than leaving a section silently blank (already established for `rules/*.md`'s `Exceptions` field and carried forward here).

### 1.1 Identity

`{ connector_id, display_name, maintained_by, source_type }` — `source_type` is one of the eight already enumerated in [`KNOWLEDGE_PIPELINE.md § 1`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type) (git repository, documentation site, Discourse forum, Stack Exchange API, video platform, chat platform, app/marketplace directory, structured training platform), or a newly-registered ninth type the moment one is genuinely needed. `connector_id` is stable and permanent, same discipline as every other ID in this repository — never reassigned.

### 1.2 Authentication

`{ required: bool, method: none | api_key | oauth_token | bot_session | enrollment_credentials, credential_reference }` — `credential_reference` never contains a literal secret, only a pointer to where one is configured, per this project's standing security discipline (no credential is ever hand-written into a declarative connector manifest). A connector declaring `required: true` with no valid `credential_reference` fails to activate, loudly, at startup — never silently falls back to unauthenticated access at a degraded rate limit without that being an explicit, visible configuration state.

### 1.3 Discovery Strategy

`{ strategy_kind: sitemap | api_pagination | git_ref_enumeration | feed_poll | directory_listing, entry_point, expected_candidate_volume }` — the one stage every connector must implement itself, per [`CRAWLER_PLUGIN_SYSTEM.md § 3`](CRAWLER_PLUGIN_SYSTEM.md#3-what-a-new-connector-must-provide). `expected_candidate_volume` is a rough order-of-magnitude estimate (tens, hundreds, thousands, tens-of-thousands), used only for [`OBSERVABILITY.md`](OBSERVABILITY.md)'s progress-reporting baseline — never a hard cap.

### 1.4 Pagination

`{ pagination_kind: none | offset | cursor | link_header | page_number, page_size, max_pages }` — `max_pages` is a safety ceiling, not a target; a connector hitting it triggers an [`OBSERVABILITY.md`](OBSERVABILITY.md) warning that discovery may be incomplete, not a silent truncation.

### 1.5 Crawling Policy

`{ politeness_delay_ms, concurrency_limit, respects_robots_txt: bool, allowed_content_types }` — `respects_robots_txt: false` is only ever valid for API-based source types (a REST API has no `robots.txt` concept); for any HTTP-crawled documentation/blog-type source it is a **hard-required `true`**, per [`KNOWLEDGE_PIPELINE.md § 1`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type)'s existing "honor `robots.txt` disallow rules absolutely."

### 1.6 Supported Artifact Types

Which [`Knowledge Document`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#21-knowledge-document) content shapes this connector is expected to produce (e.g., "HTML pages with code blocks," "JSON API payloads," "video + caption pairs") — informs which [`PARSER_SPEC.md`](PARSER_SPEC.md) parser(s) the connector binds to. Not to be confused with `Knowledge Extraction`'s output types ([`Knowledge API`/`Pattern`/etc.](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#2-artifact-types)) — a connector declares what *raw* shape it produces, never what *knowledge* will later be extracted from it, per [`CRAWLER_ARCHITECTURE.md § 2.1`](CRAWLER_ARCHITECTURE.md#21-where-this-frameworks-output-boundary-is)'s boundary.

### 1.7 Rate Limits

`{ requests_per_second, daily_quota, quota_reset_schedule, respects_platform_headers: bool }` — full design in [`RATE_LIMITING.md`](RATE_LIMITING.md); a connector's declared values are the *ceiling* it must never exceed, and `respects_platform_headers: true` connectors additionally throttle below their declared ceiling whenever the platform's own response headers say to.

### 1.8 Retries

`{ max_attempts, backoff_kind: exponential, base_delay_ms, retryable_status_codes }` — full design in [`RETRY_POLICY.md`](RETRY_POLICY.md); a connector may narrow the framework's default retryable-status-code set (e.g., a connector whose platform is known to return `403` for legitimate rate-limiting rather than a hard block may declare `403` retryable) but may never widen it to retry a status the framework classifies [`ERROR_HANDLING.md § Permanent`](ERROR_HANDLING.md#2-permanent) without an explicit, reviewed override.

### 1.9 Incremental Sync Strategy

`{ sync_kind: full_rescan | conditional_request | webhook | since_parameter, checkpoint_field }` — how this connector avoids re-crawling unchanged content on its second and subsequent runs, per [`CACHE_STRATEGY.md`](CACHE_STRATEGY.md). `checkpoint_field` names what the connector persists between runs to know where it left off (a last-modified timestamp, a cursor, a commit SHA).

### 1.10 Version Awareness

`{ version_signal_kind: url_path_segment | explicit_field | text_inference | none, confidence_default }` — matches [`KNOWLEDGE_PIPELINE.md § 4`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)'s three confidence bands (`explicit`, `stated`, `inferred`) exactly; a connector declaring `version_signal_kind: none` is explicitly stating every document it produces starts at `inferred`-or-lower confidence, never silently defaulting to a higher band it didn't earn.

---

## 2. Example Declarations (Illustrative Only — Not Implementation)

Two contrasting connectors, shown only to demonstrate the contract is genuinely source-agnostic — neither is code:

| Declaration | `github` connector | `frappe_docs`-type connector |
|---|---|---|
| source_type | git repository | documentation site |
| authentication | `api_key`, GitHub PAT | none |
| discovery | `git_ref_enumeration` + `api_pagination` for Issues/PRs | `sitemap` |
| pagination | `link_header` (GitHub's own) | none |
| crawling policy | `respects_robots_txt: false` (API), concurrency per GitHub's docs | `respects_robots_txt: true`, 1 req/sec |
| rate limits | 5,000/hr authenticated, `respects_platform_headers: true` | self-imposed only, no platform quota |
| incremental sync | `webhook` where available, else `since_parameter` (commit date) | `conditional_request` (ETag/Last-Modified) |
| version awareness | `explicit_field` (commit SHA, tag) | `url_path_segment` (`/vNN/`) |

---

## 3. Contract Compliance

A connector that cannot truthfully complete all ten declarations does not qualify for registration — per [`CRAWLER_PLUGIN_SYSTEM.md § 2`](CRAWLER_PLUGIN_SYSTEM.md#2-registration-not-modification), the framework enumerates and instantiates only what satisfies this full contract, and [`TESTING_STRATEGY.md § Connector Tests`](TESTING_STRATEGY.md#1-connector-tests) verifies this compliance mechanically before a connector is ever allowed to run against a live source.
