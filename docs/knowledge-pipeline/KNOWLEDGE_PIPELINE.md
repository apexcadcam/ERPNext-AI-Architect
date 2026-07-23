# KNOWLEDGE PIPELINE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). Defines the first four pipeline stages (Acquisition → Cleaning → Normalization → Deduplication) in detail, and the per-source acquisition profile the task requires.
**Scope:** Everything up to, but not including, extraction — see [KNOWLEDGE_EXTRACTION_SPEC.md](KNOWLEDGE_EXTRACTION_SPEC.md) for what happens to a validated `Knowledge Document` next.

---

## 0. Stage Overview

```
Knowledge Source
      │
      ▼
[1] Acquisition        — pull raw content, per source-type method (§2)
      │
      ▼
[2] Cleaning            — strip boilerplate/navigation/ads, normalize encoding (§3)
      │
      ▼
[3] Normalization       — canonical structure: headings, code blocks, metadata fields (§4)
      │
      ▼
[4] Deduplication       — exact + near-duplicate detection, within and across sources (§5)
      │
      ▼
Knowledge Document (KD) — ready for validation
      │
      ▼
Validation  →  Extraction  →  Pattern Extraction  →  Conflict Resolution  →
Knowledge Graph  →  Embeddings  →  Retrieval  →  AI Agents
(see their own documents, linked from KNOWLEDGE_ACQUISITION_ARCHITECTURE.md)
```

Every stage is a **gate**, not a filter that silently drops content — content that fails a stage is retained with a `rejected` status and the reason, never deleted, per this repository's existing [Traceability principle](../../ENGINEERING_META_MODEL.md#design-principles).

---

## 1. Acquisition Method by Source Type

Rather than one acquisition policy per individual source (48 near-duplicate rows), policy is defined once per **source type** — the actual differentiator — then every cataloged source maps to exactly one type in [§6](#6-full-source-acquisition-profile).

| Source Type | Method | Authentication | Rate Limit Policy | Version Awareness |
|---|---|---|---|---|
| **Git repository** (official + long-tail code) | `git clone`/`fetch` for full history; GitHub REST + GraphQL API for issues/PRs/releases/discussions metadata | GitHub Personal Access Token (raises API quota from 60/hr unauthenticated to 5,000/hr authenticated; required at any real scale) | Respect GitHub's returned rate-limit headers; exponential backoff on `403`/`429`; never poll faster than the platform allows regardless of quota remaining | Every commit SHA is an exact version anchor; tags/branches map directly to ERPNext/Frappe version lines |
| **Documentation site** (docs.frappe.io, docs.erpnext.com, frappecloud.com/docs, frappeframework.com) | Sitemap-driven HTTP crawl; HTML → structured text via DOM-aware extraction (preserve heading hierarchy and code blocks, discard nav/footer/ads) | None required (public) | Self-imposed politeness delay (default: 1 request/second/host); honor `Crawl-delay` in `robots.txt` if present; honor `robots.txt` disallow rules absolutely | URL path segment (e.g. `/erpnext/v15/`) is the primary version signal, extracted and stamped at acquisition time — never inferred later |
| **Discourse forum** (discuss.frappe.io) | Discourse's native JSON API (`<topic-url>.json`) — structured, includes author role/badge and accepted-answer flags directly, preferred over HTML scraping | Public read access sufficient for current categories; API key only if rate limits become binding | Respect Discourse's rate-limit response headers and `Retry-After` | Not URL-versioned; inferred from post date + explicit version mentions in text — flagged as **lower-confidence version scoping** at acquisition time |
| **Stack Exchange API** (Stack Overflow) | Official Stack Exchange API (structured: votes, accepted-answer flag, tags, dates — no HTML parsing needed) | Optional app key (raises daily quota); no user auth needed for public Q&A | Stack Exchange API daily quota, tracked via response `quota_remaining` | Inferred from tags/body text; generally weak, flagged accordingly |
| **Video platform** (YouTube — official channel + conference recordings) | YouTube Data API for metadata; caption/transcript API for text where captions exist; no transcript = no acquisition (never auto-generate a fabricated transcript) | API key required (quota-based) | Daily quota units — metadata and caption calls both consume quota; budget explicitly, prioritize official-channel content over third-party | Publish date only, plus any explicit version mentioned in title/description/transcript text |
| **Discourse-adjacent chat** (Telegram, if ever enabled — see below) | Bot API or session-based client joining as a read member, where the group's own rules permit | Bot token or authenticated user session required | Telegram flood-limit rules, strictly enforced by the platform itself | None — weakest version signal of any source type in this catalog |
| **App/marketplace directory** (Frappe Gems, Frappe Cloud Marketplace) | The directory's own listing API/page (metadata only: name, repo URL, category, framework-version compatibility, maintenance status) — this acquisition step itself *generates new acquisition targets* for the git-repository method above | None confirmed required | Self-imposed politeness delay | Directory-reported compatibility tags, when present; otherwise inferred from the target repo itself once acquired |
| **Structured training platform** (Frappe School) | Public marketing/catalog pages via HTTP crawl; gated course content requires enrollment and is out of scope for automated acquisition unless a licensing agreement exists | Session/enrollment credentials required for gated content — **not assumed available**; public catalog pages only by default | Self-imposed politeness delay | Course-level, not fine-grained; tied to publish/update date shown on the platform |

**Telegram is acquisition-capable in principle but excluded by default**, consistent with [KNOWLEDGE_SOURCE_CATALOG.md § 10](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#10-sources-that-should-never-be-used)'s conditional-exclusion of `KS-0028` — this table specifies the method for completeness, not as a recommendation to enable it. **Discord (`KS-0030`) has no acquisition method defined at all** — it is not a source type this pipeline acquires from, full stop, per the catalog's hard exclusion.

---

## 2. Acquisition (Stage 1, detail)

**Input:** a `Knowledge Source` entry and its type-mapped method from [§1](#1-acquisition-method-by-source-type).
**Output:** a raw `Knowledge Document` — `metadata.extraction_method` set to the acquisition method used, `provenance` set to `[Knowledge Source]`, content unprocessed.
**Failure handling:** a failed acquisition attempt (network error, 404, auth failure) is logged against the source with a timestamp and reason — three consecutive failures for a given source triggers a source-health flag surfaced in [KNOWLEDGE_REFRESH_POLICY.md](KNOWLEDGE_REFRESH_POLICY.md), not a silent skip.
**Crawl policy, general form:** full initial crawl on first acquisition of a source; incremental acquisition thereafter (webhook-driven for git repositories where available, polling on the [refresh cadence](KNOWLEDGE_REFRESH_POLICY.md) otherwise) — never re-acquire content whose source content-hash is unchanged since the last successful acquisition.

---

## 3. Cleaning (Stage 2, detail)

**Input:** a raw `Knowledge Document`.
**Output:** the same `KD`, `content.cleaned_text` populated.
**Operations:** strip navigation chrome, ads, cookie banners, and site furniture; normalize character encoding to UTF-8; strip tracking parameters from any URLs referenced in the content; collapse redundant whitespace without destroying meaningful code-block indentation.
**What cleaning never does:** rewrite, summarize, or paraphrase the actual content — cleaning only removes noise, it never alters the substance of what was said, or the confidence pipeline downstream would be scoring a different claim than the one that was actually acquired.

---

## 4. Normalization (Stage 3, detail)

**Input:** a cleaned `Knowledge Document`.
**Output:** the same `KD`, `content.structural_metadata` populated: heading hierarchy, identified code-block boundaries and their declared language, identified tabular data, identified list structures.
**Operations:** convert source-specific markup (HTML, Discourse's flavor of Markdown, GitHub's flavor of Markdown, YouTube caption timing files) into one canonical internal representation, so every downstream stage operates on one structure regardless of which of the eight source types in [§1](#1-acquisition-method-by-source-type) produced it.
**Version stamping:** the version signal identified during acquisition ([§1](#1-acquisition-method-by-source-type)'s "Version Awareness" column) is normalized into the envelope's `version.applies_to` field here, in one of three confidence bands — `explicit` (URL path or commit tag), `stated` (text explicitly names a version), `inferred` (date-based guess only) — carried forward so no downstream consumer has to re-derive it.

---

## 5. Deduplication (Stage 4, detail)

**Input:** a normalized `Knowledge Document`.
**Output:** either a new, unique `KD`, or a link from this acquisition attempt to an existing `KD` (no new artifact created), plus an updated `last_seen_at` on the existing one.
**Two-pass detection:**
1. **Exact-match** — content hash comparison against every existing `KD` from the same `Knowledge Source`. Catches re-crawls of unchanged pages.
2. **Near-duplicate** — a lightweight similarity check (not full semantic embedding — that's reserved for [EMBEDDING_STRATEGY.md](EMBEDDING_STRATEGY.md) further downstream) against `KD`s from *different* sources, catching e.g. the same tutorial mirrored on two blogs, or a forum answer that quotes documentation verbatim.
**On near-duplicate detection across sources of different trust:** both `KD`s are retained (provenance must stay complete), but only the higher-trust source's `KD` proceeds to extraction by default — the lower-trust duplicate is marked `superseded_by` the higher-trust one and excluded from default extraction, retrievable only for provenance/audit queries.

---

## 6. Full Source Acquisition Profile

Every source from [`knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md), mapped to its acquisition type and the artifact type(s) its extraction stage targets. Trust Score, Priority, and Refresh Cadence are **not restated here** — they are already authoritative in the catalog; restating them in a second document would create exactly the dual-source-of-truth risk this whole pipeline exists to eliminate. This table adds only the pipeline-specific columns the catalog doesn't carry.

| Catalog ID(s) | Source(s) | Acquisition Type | Primary Artifact(s) Produced |
|---|---|---|---|
| KS-0003, KS-0004 | `frappe/frappe`, `frappe/erpnext` source | Git repository | Knowledge API, Pattern (via Pattern Extraction) |
| KS-0033–KS-0046 | All first-party product repos, `frappe-ui`, `bench`, `frappe_docker`, `press` | Git repository | Knowledge API, Pattern, Example |
| KS-0047 | Long-tail third-party apps | Git repository, **gated by the [Long-Tail Vetting Gate](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#13-long-tail-vetting-gate) pre-acquisition** | Pattern (observed-only, lower confidence), Example |
| KS-0014, KS-0015 | GitHub Issues (frappe/frappe, frappe/erpnext) | Git repository (Issues API) | Example (reproduction steps), Pattern (workarounds), Knowledge Conflict (contested reports) |
| KS-0016 | Merged Pull Requests | Git repository (PR + review API) | Knowledge API (diff), Pattern (rationale), Engineering Rule candidate drafts (when review discussion reveals a general principle) |
| KS-0010 | GitHub Releases/Changelogs | Git repository (Releases API) | Knowledge API (version deltas), triggers for [breaking-change propagation](KNOWLEDGE_REFRESH_POLICY.md#4-breaking-change-propagation) |
| KS-0018 | Commit History | Git repository (`git log`) | Corroborating provenance for Knowledge API/Pattern, not a primary extraction target on its own |
| KS-0017 | GitHub Discussions | Git repository (Discussions API) | Example, Best Practice |
| KS-0001, KS-0002, KS-0008, KS-0012, KS-0013 | Documentation sites | Documentation site crawl | Knowledge API, Workflow, Example |
| KS-0005, KS-0019 | Frappe Forum (general + staff-tagged) | Discourse API | Best Practice, Knowledge Conflict (contested threads), Pattern |
| KS-0009, KS-0011, KS-0020 | Engineering Blog, Architecture Handbook, RFC-substitute composite | Documentation site crawl | Pattern, Engineering Rule candidate drafts (rationale-heavy content) |
| KS-0006 | Frappe School | Structured training platform | Workflow, Example |
| KS-0007, KS-0024 | YouTube channel, conference talks | Video platform | Workflow (lower confidence), Example |
| KS-0021, KS-0022 | Curated "awesome" lists | Documentation site crawl (treated as discovery, not content) | Feeds new Git-repository acquisition targets; produces no content artifact itself |
| KS-0023 | Individual technical blog | Documentation site crawl | Pattern (individually-attributed, lower confidence) |
| KS-0025 | Implementation-partner blogs | Documentation site crawl, **mandatory human spot-check before extraction per catalog policy** | Best Practice (low-confidence, rarely promoted further) |
| KS-0027 | Stack Overflow | Stack Exchange API | Example, Best Practice |
| KS-0028 | Telegram | Chat platform — **excluded by default**, see [§1](#1-acquisition-method-by-source-type) | N/A while excluded |
| KS-0032, KS-0048 | Frappe Gems, Frappe Cloud Marketplace | App/marketplace directory | Feeds new Git-repository acquisition targets (KS-0047), subject to the vetting gate before any content is extracted |
| KS-0026, KS-0029, KS-0030, KS-0031 | Excluded/never-use sources | **No acquisition method assigned** | N/A |

---

## 7. Scale Note

"Capable of supporting millions of knowledge artifacts" is an acquisition-and-storage scale question this document treats as a property of the **acquisition/storage layer's design**, not of any individual pipeline run: incremental acquisition (never re-pulling unchanged content), content-hash-based deduplication, and type-scoped batching (per [§1](#1-acquisition-method-by-source-type)) are what keep the pipeline's *ongoing* cost proportional to what actually changed upstream, not to the catalog's total size — the same principle already applied at a smaller scale in [`rules/index/RULE_INDEX.yaml`](../ai-retrieval/RULE_INDEX_SPEC.md#6-index-format--sharding)'s sharding design, generalized here.
