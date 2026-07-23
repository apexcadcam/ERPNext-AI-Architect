# ERPNEXT KNOWLEDGE SOURCE CATALOG

**Status:** Foundational — Source Identification Complete, Extraction Not Started
**Artifact type:** [Knowledge Source (`KS`)](../ENGINEERING_META_MODEL.md#24-knowledge-source-ks) registry — see [README.md](README.md) for why this is one document rather than 48 files.
**Scope:** Identifies, evaluates, tiers, and sequences every external source this project should draw on to build an ERPNext/Frappe AI Architect. **This document extracts no knowledge.** No rule, pattern, or fact from any source below has been pulled into `rules/` or `research/` as part of producing this catalog — that is explicitly future, separately-scoped work (see [§8](#8-knowledge-acquisition-roadmap)).
**Research date:** 2026-07-23. Every quantitative figure (star count, member count, release cadence) below is a snapshot taken on this date via live web search, not a fixed fact — see [§14](#14-verification--currency-disclaimer).

---

## 0. Executive Summary

48 sources identified across 5 tiers. Of these:

- **13 are Tier 1 (Official)** — the load-bearing foundation of any RAG system built on this catalog. Two of the thirteen (`KS-0002`, `KS-0012`) are demoted to low priority despite official origin, for reasons stated in their profiles — officiality alone does not earn trust in this catalog.
- **7 are Tier 2 (Engineering)** — the highest-signal-per-token sources for *why* the framework behaves as it does, not just *that* it does.
- **6 are Tier 3 (Community)**, aggressively filtered — two additional categories of community blog were investigated and explicitly excluded (`KS-0026`) rather than padded into the catalog for volume.
- **5 are Tier 4 (Q&A/Chat)**, one of which (`KS-0031`, Discord) is a **hard no** — see [§10](#10-sources-that-should-never-be-used).
- **17 are Tier 5 (Code)** — the largest tier, because production-grade reference implementations are this project's single highest-value input, per [PROJECT_CHARTER.md's Core Engineering Philosophy](../PROJECT_CHARTER.md#core-engineering-philosophy).

**The single most important finding:** this project already has, in `frappe/hrms`, `frappe/crm`, and six other first-party Frappe Technologies products, a set of **production-grade, officially-maintained, idiomatic Frappe applications** that are more valuable than any blog, forum thread, or third-party tutorial in this catalog. Any acquisition roadmap that crawls community content before fully mining these is mis-sequenced.

---

## 1. Methodology

### 1.1 Two scores, not one

Every source carries two numbers:

- **Trust Score (0–100)** — the single holistic number used for ranking, matrices, and crawl ordering. `Trust Score = round(Knowledge Reliability Score) ± a stated adjustment for a risk factor the eight KRS dimensions don't capture` (legal/ToS crawling risk, namespace-collision risk, marketing bias, extraction difficulty). The adjustment is stated explicitly wherever it is non-zero; where absent, `Trust Score = KRS`.
- **Knowledge Reliability Score (KRS, 0–100)** — computed from eight dimensions the task requires (Officiality, Engineering Quality, Community Reputation, Freshness, Maintenance, Consistency, Adoption, Accuracy), each scored 0–10, summed (max 80), and scaled ×1.25. The full eight-dimension breakdown is shown for the eight highest-weight sources as a worked example of the method; every other source states the resulting KRS with a one-line rationale referencing the same eight dimensions, to keep the catalog readable at 48 entries.

### 1.2 Tiering

Tiers group sources by **kind of authority**, not by score — a Tier 3 source can outscore a weak Tier 1 source (see `KS-0002` vs. `KS-0021`). Tier is about *what kind of claim this source can make*; Trust Score is about *how much to believe it*.

### 1.3 Standing critical stance

Per this catalog's constraints: no source below Trust Score 50 is recommended for unsupervised RAG ingestion regardless of tier, no source is included solely because it exists (two categories of low-value blog were investigated and explicitly rejected — see `KS-0026`), and every "official" label is checked against actual evidence of Frappe Technologies operation or authorship, not assumed from a plausible-sounding domain name.

---

## 2. Tier 1 — Official Sources

| ID | Name | Trust | KRS | Priority |
|---|---|---|---|---|
| KS-0001 | Frappe Unified Documentation Hub | 92 | 90 | P0 |
| KS-0002 | Legacy ERPNext Docs (docs.erpnext.com) | 55 | 55 | P2 |
| KS-0003 | `frappe/frappe` GitHub Repository | 98 | 95 | P0 |
| KS-0004 | `frappe/erpnext` GitHub Repository | 98 | 95 | P0 |
| KS-0005 | Frappe Forum (discuss.frappe.io) | 78 | 78 | P1 |
| KS-0006 | Frappe School | 85 | 83 | P1 |
| KS-0007 | Frappe YouTube Channel (@frappetech) | 80 | 78 | P2 |
| KS-0008 | Frappe Cloud Documentation | 88 | 86 | P1 |
| KS-0009 | Frappe Engineering Blog | 90 | 88 | P0 |
| KS-0010 | GitHub Releases / Changelogs | 93 | 90 | P0 |
| KS-0011 | Frappe Architecture Handbook | 82 | 80 | P1 |
| KS-0012 | frappeframework.com (marketing landing) | 45 | 45 | P3 |
| KS-0013 | frappe.io/erpnext/articles | 60 | 60 | P2 |

### KS-0001 — Frappe Unified Documentation Hub

| Field | Value |
|---|---|
| URL | `https://docs.frappe.io/` (framework: `/framework`, ERPNext: `/erpnext/vNN`, Cloud: `/cloud`, Wiki: `/wiki`) |
| Type | Official documentation |
| Description | Frappe Technologies' consolidated documentation hub covering the Framework, ERPNext (versioned per major release, e.g. `v13`, `v14`), Frappe Cloud, and a general wiki section. Appears to be the successor to the deprecated `frappe/frappe_docs` GitHub repo. |
| Maintainer | Frappe Technologies Pvt. Ltd. |
| Community Size | N/A (documentation site, not a community) |
| Update Frequency | Continuous, tracks release cadence (see KS-0003/KS-0004 — near-weekly point releases) |
| Coverage | Framework fundamentals, ERPNext modules per version, Cloud operations, general concepts |
| Why Trusted | Company-operated, first-party, the `frappe_docs` GitHub repo explicitly redirects contributors here ("[DEPRECATED]... please don't raise new contributions here") — a clear signal this is the current canonical home. |
| Risks | Version fragmentation: ERPNext docs are versioned per major release (`v12`, `v13`, `v14`...) and older version pages remain live and indexable, creating real risk of a RAG system retrieving instructions for a version 2–3 majors behind current without realizing it. Always capture and surface the version path segment. |
| Can AI safely learn from it? | Yes, with mandatory version-tagging of every ingested chunk. |
| Recommended Priority | **P0** — primary documentation foundation. |

### KS-0002 — Legacy ERPNext Docs (docs.erpnext.com)

| Field | Value |
|---|---|
| URL | `https://docs.erpnext.com/` |
| Type | Documentation (legacy/parallel) |
| Description | A separately-hosted ERPNext user manual (e.g. `docs.erpnext.com/docs/user/manual/en/doctype`) that appears to predate, and now runs in parallel with, the `docs.frappe.io/erpnext/vNN` structure. |
| Maintainer | Frappe Technologies Pvt. Ltd. (same org, different, seemingly older, hosting path) |
| Community Size | N/A |
| Update Frequency | Unclear — could not confirm whether this domain receives the same update cadence as `docs.frappe.io`. |
| Coverage | User-facing manual content, overlapping with KS-0001's ERPNext section |
| Why Trusted | Frappe-operated domain, real content confirmed live. |
| Risks | **Two parallel documentation domains for the same product is itself a data-quality risk** — if this catalog cannot determine which is authoritative for a given topic at ingestion time, a RAG system built from both risks surfacing contradictory or version-mismatched answers for the same question. Treat as secondary/cross-check only until this is resolved by direct comparison. |
| Can AI safely learn from it? | Partial — cross-check every extracted fact against KS-0001 before trusting; do not ingest as an independent source of truth. |
| Recommended Priority | **P2** — useful for cross-validation, not as a primary crawl target. |

### KS-0003 — `frappe/frappe` GitHub Repository

| Field | Value |
|---|---|
| URL | `https://github.com/frappe/frappe` |
| Type | Source code (ground truth) |
| Description | The Frappe Framework's own source — the DocType engine, permission system, hooks system, ORM, and everything every ERPNext behavior is ultimately built on. |
| Maintainer | Frappe Technologies Pvt. Ltd. + open-source contributors |
| Community Size | ~10.5k GitHub stars, ~5.1k forks (snapshot 2026-07-23) |
| Update Frequency | Near-weekly point releases confirmed (v16.1.0 → v16.2.0 in one week during Jan 2026; v15.x line still receiving releases in parallel) |
| Coverage | The entire framework: ORM, permissions, hooks, background jobs, REST API, desk UI, realtime, caching |
| Why Trusted | This *is* the behavior — not a description of it. When documentation and source code disagree, source code is correct by definition. |
| Risks | Requires engineering competence to read correctly; a naive keyword-match extraction from source risks pulling internal implementation detail out of context and presenting it as public-API guidance. |
| Can AI safely learn from it? | Yes — the single highest-ground-truth source in this entire catalog. |
| Recommended Priority | **P0** — non-negotiable foundation. |

### KS-0004 — `frappe/erpnext` GitHub Repository

| Field | Value |
|---|---|
| URL | `https://github.com/frappe/erpnext` |
| Type | Source code (ground truth) |
| Description | ERPNext's own source: every standard DocType, business logic module, and report the "native-first" discovery process (see [R002](../rules/R002-native-first-discovery.md)) depends on knowing about. |
| Maintainer | Frappe Technologies Pvt. Ltd. + open-source contributors |
| Community Size | ~37.2k GitHub stars (snapshot 2026-07-23) — the ecosystem's largest single repository by adoption signal |
| Update Frequency | Tracks `frappe/frappe`'s near-weekly cadence |
| Coverage | Every standard ERPNext module: Accounts, Selling, Buying, Stock, Manufacturing, Projects, Support, Assets, HR (legacy pre-v14 portions) |
| Why Trusted | Ground truth for "does ERPNext already solve this" — the exact question R002 requires answering before any custom structure is built. |
| Risks | Same extraction-context risk as KS-0003; additionally, large legacy modules retain old patterns not representative of current best practice — date every extracted pattern against the commit/release it came from. |
| Can AI safely learn from it? | Yes. |
| Recommended Priority | **P0**. |

### KS-0005 — Frappe Forum (discuss.frappe.io)

| Field | Value |
|---|---|
| URL | `https://discuss.frappe.io/` |
| Type | Official community platform |
| Description | Frappe Technologies-operated Discourse forum, split into Framework, ERPNext, Working Groups, and regional-community categories. |
| Maintainer | Platform operated by Frappe Technologies; content authored by community + staff |
| Community Size | 22,000+ registered users self-reported in a forum post found during research (unverified live) |
| Update Frequency | Continuous, high daily volume |
| Coverage | Troubleshooting, feature discussion, working-group coordination, announcements |
| Why Trusted | Official venue; staff (including apparent core maintainers) participate directly and are usually identifiable by badge/role in-thread. |
| Risks | **Content quality is bimodal, not uniform** — a staff-authored architectural answer and an unverified guess from a first-time poster live in the same thread format. Trust must be assigned per-post (staff-tagged > accepted-solution > high-vote > untagged), never per-forum. |
| Can AI safely learn from it? | Yes, with per-post trust weighting — never bulk-ingest a whole thread as uniformly authoritative. |
| Recommended Priority | **P1**. |

### KS-0006 — Frappe School

| Field | Value |
|---|---|
| URL | `https://frappe.school/` (also `school.frappe.io`, marketing page at `frappe.io/school`) |
| Type | Official structured training |
| Description | Frappe Technologies' course platform — video + quiz + exercise courses on Framework fundamentals and ERPNext, including a free "Frappe Framework Low-code Course for Beginners" and paid certification tracks. |
| Maintainer | Frappe Technologies Pvt. Ltd. |
| Community Size | N/A (course catalog, not a discussion community) |
| Update Frequency | New courses added periodically; unclear cadence |
| Coverage | Framework basics, app creation, client/server scripting, print formats, reports, webforms, dashboards, e-commerce |
| Why Trusted | First-party, structured, built "by maintainers and the community" per Frappe's own description; courses are pedagogically sequenced rather than being scattered reference fragments. |
| Risks | Video-first format complicates text extraction; course content may lag behind the very latest framework version. |
| Can AI safely learn from it? | Yes, once transcribed; treat as excellent for onboarding-style knowledge (concept sequencing), secondary to KS-0001/KS-0003 for precise current API detail. |
| Recommended Priority | **P1**. |

### KS-0007 — Frappe YouTube Channel (@frappetech)

| Field | Value |
|---|---|
| URL | `https://www.youtube.com/@frappetech` |
| Type | Official video content |
| Description | Frappe Technologies' official channel: product demos, conference talk recordings, feature walkthroughs. |
| Maintainer | Frappe Technologies Pvt. Ltd. |
| Community Size | Not independently verified this session — verify subscriber count live before final ranking |
| Update Frequency | Tied to product releases and conference events (e.g. Frappeverse recordings) |
| Coverage | Product demos, release walkthroughs, conference talks |
| Why Trusted | Official channel handle confirmed via search; distinguishable from several unrelated/unofficial "Frappe"-named channels also found in search results (a real namespace-confusion risk on this platform, milder than KS-0031's). |
| Risks | Namespace confusion with unrelated channels (`Frappé`, `ERPNext` legacy channel, third-party "Learn ERPNext" channels of unverified quality) — always resolve to the exact handle, never search-match on the word "Frappe" alone. Demo content skews toward feature showcase over precise technical reference. |
| Can AI safely learn from it? | Yes, via transcript extraction, restricted to the confirmed `@frappetech` handle. |
| Recommended Priority | **P2**. |

### KS-0008 — Frappe Cloud Documentation

| Field | Value |
|---|---|
| URL | `https://frappecloud.com/docs`, mirrored at `https://docs.frappe.io/cloud` |
| Type | Official documentation |
| Description | Documentation for Frappe Cloud, the official managed hosting platform for Frappe/ERPNext (built on `frappe/press`, KS-0046). |
| Maintainer | Frappe Technologies Pvt. Ltd. |
| Community Size | N/A |
| Update Frequency | Tracks Frappe Cloud platform releases |
| Coverage | Site deployment, scaling, backups, self-hosted/hybrid cloud setup, marketplace app installation |
| Why Trusted | First-party, operational documentation for the company's own hosting product. |
| Risks | Cloud-specific — some guidance (managed backups, one-click scaling) does not transfer to self-hosted `bench` deployments; scope every extracted fact to "Frappe Cloud" vs. "self-hosted" explicitly. |
| Can AI safely learn from it? | Yes, scoped to deployment/hosting topics. |
| Recommended Priority | **P1**. |

### KS-0009 — Frappe Engineering Blog

| Field | Value |
|---|---|
| URL | `https://frappe.io/blog/engineering` |
| Type | Official technical blog |
| Description | Frappe Technologies' engineering-focused blog channel, distinct from the general/marketing blog — genuine deep-dive posts confirmed during research: "Reducing Memory Footprint of Frappe Framework" (10–35% memory reduction reported), "Evolving Frappe's ORM for Security and Flexibility," "Writing Composable Software," "Announcing Version 16," "Frappe Studio: Behind the Scenes." |
| Maintainer | Frappe Technologies Pvt. Ltd. engineering staff |
| Community Size | N/A |
| Update Frequency | Irregular, tied to significant engineering milestones (not a fixed cadence) |
| Coverage | Architecture decisions, performance work, security changes, major version rationale |
| Why Trusted | Written by the people who made the changes, about changes verifiable against KS-0003/KS-0010; this is as close to a first-party "engineering rationale" source as exists in this ecosystem, filling the gap left by the absent formal RFC process (see KS-0020). |
| Risks | Retrospective narrative can be more polished/less caveated than the messier real decision process (visible in PR discussions, KS-0016) — treat as the *stated* rationale, cross-check against actual PR discussion for contested decisions. |
| Can AI safely learn from it? | Yes. |
| Recommended Priority | **P0** for architecture/rationale-type knowledge specifically. |

### KS-0010 — GitHub Releases / Changelogs

| Field | Value |
|---|---|
| URL | `https://github.com/frappe/frappe/releases`, `https://github.com/frappe/erpnext/releases` |
| Type | Official changelog |
| Description | Per-version release notes for both repositories. Confirmed active: v16.1.0 (2026-01-13), v16.2.0 (2026-01-20), v15.98.0 (2026-01-27) all observed in a single research pass — evidence of near-weekly release cadence across two parallel major-version lines. |
| Maintainer | Frappe Technologies Pvt. Ltd. (automated release tooling) |
| Community Size | N/A |
| Update Frequency | Near-weekly (confirmed) |
| Coverage | Every merged change, categorized, per release |
| Why Trusted | Directly derived from merged code; version-precise by construction (every entry is inherently dated and versioned, solving the staleness problem KS-0001/KS-0002 have). |
| Risks | **A specific, material risk found during this research:** release-note generation now appears to use an LLM to summarize the underlying PRs/issues, per language on the releases page itself ("may contain typical errors and inaccuracies"). Treat release-note *prose* as a pointer to the real PR, not as the ground truth itself — the PR (KS-0016) is the ground truth. |
| Can AI safely learn from it? | Yes, for version-tagging and change discovery; verify substantive claims against the linked PR before treating as fact. |
| Recommended Priority | **P0** — best available source for "what changed, when." |

### KS-0011 — Frappe Architecture Handbook

| Field | Value |
|---|---|
| URL | Hosted as a forum topic: `https://discuss.frappe.io/t/frappe-architecture-handbook/162995` |
| Type | Official (staff-authored) architecture reference |
| Description | A dedicated architecture-explanation document surfaced on the official forum — the closest thing found to a single "how the framework is actually put together" reference. |
| Maintainer | Frappe Technologies Pvt. Ltd. (forum-hosted, not a standalone doc site) |
| Community Size | N/A |
| Update Frequency | Unknown — could not confirm revision cadence |
| Coverage | Cross-cutting framework architecture (not module-specific) |
| Why Trusted | Staff-authored, purpose-built as an architecture reference rather than incidental forum discussion. |
| Risks | Hosted as a forum post rather than versioned documentation — no visible revision history; unclear how it's kept current against KS-0003. |
| Can AI safely learn from it? | Yes, with an explicit "last verified against source" date attached at ingestion. |
| Recommended Priority | **P1**. |

### KS-0012 — frappeframework.com (marketing landing)

| Field | Value |
|---|---|
| URL | `https://frappeframework.com/homepage` |
| Type | Marketing/landing page |
| Description | The Framework's public-facing marketing site. Search results show this domain now functions largely as a landing page pointing into `docs.frappe.io`, rather than hosting distinct documentation content of its own. |
| Maintainer | Frappe Technologies Pvt. Ltd. |
| Community Size | N/A |
| Update Frequency | Low — marketing content, not documentation |
| Coverage | Feature overview, positioning, links out to real docs |
| Why Trusted | Official domain. |
| Risks | Low standalone knowledge value — largely redundant with KS-0001; a naive crawler that treats domain-name similarity as a proxy for documentation depth would waste budget here. |
| Can AI safely learn from it? | Yes, but low-value; skip in favor of KS-0001. |
| Recommended Priority | **P3**. |

### KS-0013 — frappe.io/erpnext/articles

| Field | Value |
|---|---|
| URL | `https://frappe.io/erpnext/articles` |
| Type | Official product blog/articles |
| Description | Frappe's ERPNext-specific article section — product-and-feature-oriented content, more marketing-adjacent than KS-0009's engineering blog. |
| Maintainer | Frappe Technologies Pvt. Ltd. |
| Community Size | N/A |
| Update Frequency | Unclear |
| Coverage | Feature explainers, use-case framing |
| Why Trusted | Official, but written for prospective customers, not engineers. |
| Risks | Marketing framing over engineering precision; verify any technical claim against KS-0001/KS-0003/KS-0004. |
| Can AI safely learn from it? | Partial — useful for business-context/use-case framing, not for technical accuracy. |
| Recommended Priority | **P2**. |

---

## 3. Tier 2 — Engineering Sources

| ID | Name | Trust | KRS | Priority |
|---|---|---|---|---|
| KS-0014 | `frappe/frappe` GitHub Issues | 85 | 83 | P0 |
| KS-0015 | `frappe/erpnext` GitHub Issues | 85 | 83 | P0 |
| KS-0016 | `frappe/frappe` merged Pull Requests | 92 | 90 | P0 |
| KS-0017 | GitHub Discussions (frappe-ui, builder, helpdesk, wiki) | 75 | 74 | P2 |
| KS-0018 | Commit History (`frappe/frappe`, `frappe/erpnext`) | 90 | 88 | P0 |
| KS-0019 | Staff-tagged Forum Replies | 88 | 85 | P1 |
| KS-0020 | De facto RFC substitute (Architecture Handbook + major discussion threads) | 78 | 76 | P2 |

### KS-0014/KS-0015 — GitHub Issues (`frappe/frappe`, `frappe/erpnext`)

**Description:** Bug reports, feature requests, and their resolution threads on both core repositories.
**Maintainer:** Community-filed, Frappe Technologies staff triage and close.
**Update Frequency:** Continuous, high volume.
**Coverage:** Real-world failure modes, edge cases, and confirmed/rejected feature proposals — exactly the kind of "what actually breaks and why" knowledge a lean prose rule can't hold on its own.
**Why Trusted:** Issues that reach `closed: fixed` with a linked, merged PR are as close to verified ground truth as this ecosystem produces; the failure mode being described is real, not theoretical.
**Risks:** An open, unconfirmed, or `wontfix`-closed issue is *not* the same evidentiary weight as one closed by a merged fix — an extraction pipeline that doesn't distinguish these will manufacture false "known issues." Never ingest an issue's *title* alone; the resolution status is load-bearing.
**Can AI safely learn from it?** Yes, filtered strictly to issues with a clear resolution state, each tagged with that state at ingestion.
**Recommended Priority:** **P0**.

### KS-0016 — `frappe/frappe` Merged Pull Requests

**Description:** The actual accepted code changes, plus their review discussion — the record of not just *what* changed but *what the maintainers pushed back on before accepting it*.
**Maintainer:** Community + staff authorship, staff review/merge.
**Update Frequency:** Continuous, tracks the near-weekly release cadence.
**Coverage:** Every accepted change, with its review trail.
**Why Trusted:** This is where engineering judgment is actually exercised and visible — a maintainer requesting changes because a pattern violates an unwritten convention is exactly the kind of tacit knowledge this project exists to make explicit (see [PROJECT_CHARTER.md — Why this project exists](../PROJECT_CHARTER.md#why-this-project-exists)).
**Risks:** High volume, uneven signal density — most PRs are small and unremarkable; the valuable ones are architecturally significant PRs with substantive review threads, which require judgment (human or a well-tuned filter) to identify.
**Can AI safely learn from it?** Yes — arguably this catalog's second-highest-value source after the source code itself, for *rationale* specifically.
**Recommended Priority:** **P0**.

### KS-0017 — GitHub Discussions (frappe-ui, builder, helpdesk, wiki)

**Description:** GitHub's native Discussions feature, confirmed enabled on several first-party product repos (`frappe/frappe-ui`, `frappe/builder`, `frappe/helpdesk`, `frappe/wiki`) with General/Q&A/Show-and-Tell categories.
**Maintainer:** Platform-provided, staff + community participation.
**Update Frequency:** Lower volume than Issues/PRs, product-dependent.
**Coverage:** Usage questions, design discussion, community showcases for the newer product-line repos specifically.
**Why Trusted:** Direct maintainer engagement on official repos.
**Risks:** Not confirmed enabled on `frappe/frappe` or `frappe/erpnext` themselves (search results were inconclusive for the two flagship repos specifically) — do not assume this source covers the core framework/ERPNext without re-verifying.
**Can AI safely learn from it?** Yes, for the confirmed product repos.
**Recommended Priority:** **P2**.

### KS-0018 — Commit History (`frappe/frappe`, `frappe/erpnext`)

**Description:** Raw `git log`/`git blame` history — the most granular record of change, often more precise than a PR's summary description for pinpointing exactly when and why a specific line changed.
**Maintainer:** N/A (derived directly from repository history).
**Update Frequency:** Continuous.
**Coverage:** Line-level change history across the entire codebase lifetime.
**Why Trusted:** As authoritative as KS-0003 itself — it *is* KS-0003's history.
**Risks:** Commit messages vary wildly in quality; some are terse to the point of uselessness without the linked PR/issue for context.
**Can AI safely learn from it?** Yes, best used to *corroborate* a claim found elsewhere (a PR, an issue) rather than as a standalone starting point.
**Recommended Priority:** **P0**.

### KS-0019 — Staff-tagged Maintainer Forum Replies

**Description:** The subset of KS-0005 (Frappe Forum) posts authored by identifiable Frappe Technologies staff — distinguished here as its own entry because its trust profile is meaningfully different from the forum at large.
**Maintainer:** Frappe Technologies staff, posting informally.
**Update Frequency:** Continuous, embedded in ordinary forum activity.
**Coverage:** Direct answers to specific technical questions, often more precise and current than static documentation.
**Why Trusted:** Comes directly from the people who built the system, frequently addressing exactly the kind of "is this the intended way to do X" question this project's rules exist to answer.
**Risks:** Identifying staff reliably requires a maintained roster or reliable badge-based detection — a false-positive "staff" attribution would wrongly elevate an ordinary community answer to authoritative status.
**Can AI safely learn from it?** Yes, contingent on reliable staff identification at extraction time.
**Recommended Priority:** **P1**.

### KS-0020 — De Facto RFC Substitute

**Description:** This research found **no formal, dedicated RFC repository or process** for Frappe Framework (unlike, e.g., Rust RFCs or Python PEPs) — architectural proposals appear to surface through large PR discussions (KS-0016), the Architecture Handbook (KS-0011), and the Engineering Blog (KS-0009) instead.
**Maintainer:** N/A — a composite, not a single source.
**Update Frequency:** N/A.
**Coverage:** Major architectural decisions, when they happen to surface in one of the above channels.
**Why Trusted:** Each component source is independently trustworthy; the composite is weaker than a true RFC archive would be, because there's no guarantee every significant decision surfaces in a discoverable place at all.
**Risks:** **This is a real, structural gap in the ecosystem's own knowledge availability**, not a discovery failure on this catalog's part — worth stating plainly rather than papering over with an invented RFC source that doesn't exist.
**Can AI safely learn from it?** Yes, treated explicitly as a lower-confidence composite, never presented to an end user as "the RFC."
**Recommended Priority:** **P2**.

---

## 4. Tier 3 — Community Sources

| ID | Name | Trust | KRS | Priority |
|---|---|---|---|---|
| KS-0021 | `gavindsouza/awesome-frappe` | 72 | 70 | P1 |
| KS-0022 | `anndream/awesome-erpnext` | 55 | 55 | P2 |
| KS-0023 | Gavin D'souza's technical blog (gavv.in/blog) | 68 | 66 | P2 |
| KS-0024 | Frappeverse / ERPNext Conference talks | 75 | 73 | P2 |
| KS-0025 | Implementation-partner blogs (generic category) | 30 | 32 | P3 |
| KS-0026 | Third-party SEO "ERPNext guide" blogs | 20 | 22 | P4 — excluded |

### KS-0021 — `gavindsouza/awesome-frappe`

**URL:** `https://github.com/gavindsouza/awesome-frappe`
**Description:** A curated "awesome list" of Frappe Framework resources — apps, tools, hosting platforms, hardware/IoT integrations, educational resources — actively maintained (232+ commits confirmed at research time).
**Maintainer:** Gavin D'souza. **Correction against an initial assumption:** the repository itself carries **no confirmed statement of Frappe Technologies employment or official core-maintainer status** — it explicitly disclaims that listed projects are "vetted nor endorsed by the contributors." It has been shared approvingly by Frappe Technologies' own LinkedIn account, which is real, independent corroboration, but is not the same claim as official authorship.
**Community Size:** Not independently quantified beyond commit count.
**Update Frequency:** Actively maintained (232+ commits observed).
**Coverage:** Broad ecosystem map — the best single *discovery* index found in this research for what exists beyond the first-party repos.
**Why Trusted:** Long-standing, actively maintained, externally corroborated by Frappe's own promotion of it — but its own disclaimer means it is a map, not a quality certification.
**Risks:** Do not treat inclusion in this list as a trust signal for a listed project — the list's own text says the opposite.
**Can AI safely learn from it?** Yes, as a *discovery index* — every project it points to still needs independent evaluation before ingestion (see [§13, Long-Tail Vetting Gate](#13-long-tail-vetting-gate)).
**Recommended Priority:** **P1** as a discovery tool.

### KS-0022 — `anndream/awesome-erpnext`

**URL:** `https://github.com/anndream/awesome-erpnext`
**Description:** A second, smaller curated ERPNext-specific resource list.
**Maintainer:** GitHub user `anndream`, no confirmed official affiliation.
**Community Size / Update Frequency:** Not confirmed during this research — activity level and last-commit date should be checked live before relying on it.
**Coverage:** ERPNext-specific resources, narrower scope than KS-0021.
**Why Trusted:** Real, existing repository; lower corroboration than KS-0021 (no confirmed external endorsement found).
**Risks:** Unverified maintenance currency — an "awesome list" that has gone stale is actively misleading (dead links, deprecated tools presented as current).
**Can AI safely learn from it?** Yes, only after confirming recent activity.
**Recommended Priority:** **P2**.

### KS-0023 — Gavin D'souza's Technical Blog

**URL:** `https://gavv.in/blog/` (confirmed post: "How does the Frappe Framework work?")
**Description:** An individual practitioner's deep-dive technical writing on Frappe Framework internals.
**Maintainer:** Gavin D'souza (same individual as KS-0021's maintainer — a recognized, active figure in the Frappe ecosystem based on the corroboration described above, though not confirmed as Frappe Technologies staff).
**Community Size:** N/A (personal blog).
**Update Frequency:** Unknown, likely infrequent (personal blog cadence).
**Coverage:** Deep architectural explanation, at least one post confirmed substantive.
**Why Trusted:** Demonstrated technical depth in the one post reviewed; author's standing in the ecosystem (per KS-0021's external corroboration) supports above-average credibility for an individual blog.
**Risks:** Single-author opinion and interpretation, not an official statement — treat any claim here as "one knowledgeable practitioner's understanding," cross-check against KS-0003/KS-0009 before treating as fact.
**Can AI safely learn from it?** Yes, as expert commentary, explicitly labeled as non-official.
**Recommended Priority:** **P2**.

### KS-0024 — Frappeverse / ERPNext Conference Talks

**URL:** Event pages at `frappe.io/events/`; recordings expected via KS-0007 (YouTube)
**Description:** Frappe Technologies' annual flagship conference (recent naming: "Frappeverse"; earlier: "ERPNext Conference"). Frappeverse India 2025 confirmed: Mumbai, 11–12 September 2025, 1,500+ attendees from 40+ countries.
**Maintainer:** Frappe Technologies Pvt. Ltd. (event organizer); talks given by staff, partners, and community members.
**Community Size:** 1,500+ attendees (2025 event, self-reported).
**Update Frequency:** Annual.
**Coverage:** Product roadmap, community case studies, occasional deep technical talks.
**Why Trusted:** Official event; real attendance scale is corroborating evidence of ecosystem health, not just marketing claim.
**Risks:** Conference-talk content skews toward vision/roadmap/case-study framing over precise technical reference; quality varies by individual speaker.
**Can AI safely learn from it?** Yes, once recordings are transcribed, filtered for genuinely technical (vs. purely promotional) sessions.
**Recommended Priority:** **P2**.

### KS-0025 — Implementation-Partner Blogs (generic category)

**Representative examples found:** Magneto IT Solutions, Matiyas, Golive Solutions, Invento Software — ERPNext implementation/consulting companies publishing "best practices" content.
**Maintainer:** Various commercial ERPNext implementation partners.
**Community Size / Update Frequency:** Varies by company.
**Coverage:** Implementation methodology, partner-selection advice, generic best-practice guidance.
**Why Trusted:** Real, operating businesses in the ecosystem with practical implementation experience.
**Risks:** **This content reads as SEO-optimized lead generation, not engineering documentation** — generic advice ("start with core modules," "customize minimally") repeated near-identically across many such sites, with no verifiable evidence behind specific claims, no code, no version-specificity. Per this catalog's constraint to be extremely critical and prefer engineering evidence over opinion, this category is deliberately not scored higher despite the companies being real and legitimate businesses.
**Can AI safely learn from it?** Partial, and only with mandatory human spot-check per article before ingestion — never bulk-crawl this category.
**Recommended Priority:** **P3**.

### KS-0026 — Third-Party SEO "ERPNext Guide/Review" Blogs — **Investigated and Rejected**

**Representative examples found during research:** sites publishing "ERPNext in 2026: The Definitive Guide," "ERPNext Deep Dive 2026," "ERPNext Review 2026," and similarly-titled content-marketing pages.
**Assessment:** This category was actively searched for and evaluated, not overlooked. It is included in the catalog specifically to document that it was considered and rejected, per the instruction to be extremely critical and never recommend low-quality blogs. These pages show hallmarks of programmatic/templated content marketing: near-identical structure across unrelated domains, generic feature-list restatement without engineering depth, and no evidence of hands-on technical verification.
**Can AI safely learn from it?** **No — excluded from ingestion by default.**
**Recommended Priority:** **P4 — do not crawl.**

---

## 5. Tier 4 — Q&A / Chat Sources

| ID | Name | Trust | KRS | Priority |
|---|---|---|---|---|
| KS-0027 | Stack Overflow (tags: `frappe`, `erpnext`) | 65 | 64 | P2 |
| KS-0028 | Telegram (Official ERPNext Developers + community groups) | 45 | 42 | P3 |
| KS-0029 | Reddit | 25 | 25 | P4 |
| KS-0030 | Discord | 5 | 5 | **P4 — never use** |
| KS-0031 | LinkedIn posts/articles | 30 | 30 | P3 |

### KS-0027 — Stack Overflow

**URL:** `stackoverflow.com/questions/tagged/frappe`, `stackoverflow.com/questions/tagged/erpnext`
**Description:** Standard Stack Overflow tags for both technologies.
**Maintainer:** Stack Exchange Inc. (platform); community-authored content.
**Community Size:** Not independently quantified; tag volume noted as modest relative to mainstream frameworks (no exact count confirmed).
**Update Frequency:** Ongoing, lower volume than the official forum (KS-0005) based on available evidence.
**Coverage:** Point-in-time technical problems and their accepted solutions.
**Why Trusted:** Platform's voting/acceptance mechanism provides a real (if imperfect) quality signal absent from raw forum posts.
**Risks:** Answers frequently go stale as the framework evolves (an accepted answer for ERPNext v10 may be actively wrong for v15); lower community density than the official forum means more unanswered/low-quality questions proportionally.
**Can AI safely learn from it?** Yes, filtered to accepted answers with recent activity, version-checked before trusting.
**Recommended Priority:** **P2**.

### KS-0028 — Telegram

**URL:** Referenced via forum thread `discuss.frappe.io/t/official-erpnext-developers-telegram/45763`; exact group invite link not independently verified this session.
**Description:** Real-time chat groups, including one identified in forum discussion as the "Official ERPNext Developers" group, plus various unofficial community/opportunity groups.
**Maintainer:** Mixed — at least one group referenced as "official" on the forum; others explicitly community-run.
**Community Size:** Not independently quantified.
**Update Frequency:** Real-time, high message volume, low durability.
**Coverage:** Live troubleshooting, informal peer support.
**Why Trusted:** Real, active peer community; "official" labeling for at least one group traceable to a forum announcement.
**Risks:** Ephemeral, largely unindexed and unsearchable at scale, no accuracy moderation, and materially harder to attribute/verify claims than any other source in this catalog. High value for a human needing live help; poor fit for durable RAG ingestion without substantial custom tooling.
**Can AI safely learn from it?** Partial — only with dedicated scraping infrastructure and heavy per-message trust filtering; not recommended as a first-wave source.
**Recommended Priority:** **P3**.

### KS-0029 — Reddit

**Description:** No actively-populated, well-established dedicated ERPNext/Frappe subreddit was confirmed during this research; search results returned only general ERPNext explainer content, not evidence of a thriving dedicated community.
**Maintainer:** N/A (nothing confirmed to exist at sufficient scale).
**Community Size / Update Frequency:** Unconfirmed / likely low.
**Coverage:** Unconfirmed.
**Why Trusted:** N/A.
**Risks:** Building any part of a knowledge pipeline around an unconfirmed community risks wasted crawl budget on a source that may not have meaningful content.
**Can AI safely learn from it?** No — insufficient evidence of a reliable, substantial source existing to recommend it.
**Recommended Priority:** **P4** — do not prioritize; re-evaluate only if a specific, active subreddit is later confirmed.

### KS-0030 — Discord — **NEVER USE**

**Description:** No official Frappe/ERPNext Discord server was confirmed to exist. A community forum thread ("Discord Server to chat and help each other") proposes one informally, but this is a suggestion, not confirmation of an established, official, or even substantially active server.
**The critical finding:** the dominant search results for "Frappe Discord" resolve to an **entirely unrelated Roblox café-roleplay community** ("Frappé Café," ~59,800 members, founded 2013) — a serious namespace collision. Any automated or careless attempt to "find the Frappe Discord and crawl it" is at high risk of ingesting off-topic Roblox roleplay content into an ERPNext knowledge base.
**Can AI safely learn from it?** **No.**
**Recommended Priority:** **P4 — never use.** If an official Frappe/ERPNext Discord is confirmed to exist in the future (verify via `discuss.frappe.io` or `frappe.io` directly, never via platform search on the word "Frappe" alone), re-evaluate as a new entry rather than reviving this one.

### KS-0031 — LinkedIn Posts/Articles

**Description:** Frappe Technologies' official company page plus individual practitioners' posts/articles.
**Maintainer:** Mixed — company page (official) vs. individual users (unofficial).
**Community Size / Update Frequency:** Not quantified; platform posts are ongoing.
**Coverage:** Announcements (company page), anecdotal implementation experience (individuals).
**Why Trusted:** Company-page announcements are a legitimate, low-noise official channel.
**Risks:** Individual posts are inherently promotional (personal/company branding), rarely peer-reviewed or corrected, and the platform is not built for durable technical reference retrieval.
**Can AI safely learn from it?** Partial — company-page announcements only by default; individual posts excluded unless a specific post is independently vetted.
**Recommended Priority:** **P3**.

---

## 6. Tier 5 — Code Sources (Ranked by Code Quality)

Ranked highest-value first. All `frappe/*` entries are official, production-grade, and represent this catalog's single most valuable knowledge category per [§0](#0-executive-summary).

| Rank | ID | Repository | Trust | KRS | Stars (snapshot) | Priority |
|---|---|---|---|---|---|---|
| 1 | KS-0033 | `frappe/hrms` | 93 | 92 | ~8.2k | P0 |
| 2 | KS-0034 | `frappe/crm` | 90 | 88 | ~3k | P0 |
| 3 | KS-0043 | `frappe/frappe-ui` | 88 | 86 | not confirmed | P0/P1 |
| 4 | KS-0044 | `frappe/bench` | 90 | 88 | not confirmed | P0 |
| 5 | KS-0035 | `frappe/lms` | 85 | 84 | ~3.1k | P1 |
| 6 | KS-0036 | `frappe/helpdesk` | 85 | 84 | ~3.3k | P1 |
| 7 | KS-0037 | `frappe/insights` | 85 | 83 | not confirmed | P1 |
| 8 | KS-0045 | `frappe/frappe_docker` | 85 | 83 | ~2.47k | P1 |
| 9 | KS-0038 | `frappe/books` | 82 | 80 | not confirmed | P1 |
| 10 | KS-0032 | Frappe Gems directory | 80 | 78 | 300+ apps indexed | P1 (discovery) |
| 11 | KS-0039 | `frappe/drive` | 80 | 78 | not confirmed | P2 |
| 12 | KS-0040 | `frappe/gameplan` | 80 | 78 | not confirmed | P2 |
| 13 | KS-0041 | `frappe/builder` | 80 | 78 | not confirmed | P2 |
| 14 | KS-0042 | `frappe/wiki` | 78 | 76 | not confirmed | P2 |
| 15 | KS-0046 | `frappe/press` | 65 | 64 | not confirmed | P2 |
| 16 | KS-0047 | Long-tail third-party apps (via topics) | variable, 15–70 per repo | — | — | P2 (discovery), per-repo gate |
| 17 | KS-0048 | Frappe Cloud Marketplace | 78 | 76 | 300+ apps listed | P1 (discovery) |

### KS-0033 — `frappe/hrms`

**URL:** `https://github.com/frappe/hrms`
**Description:** Frappe's official, full-featured HR and Payroll product — spun out of ERPNext core as its own product from v14 onward. Described as covering 13+ modules.
**Why highest-ranked:** This is the single best available reference for "what does a large, production-grade, idiomatic custom Frappe app look like, built by the people who built the framework itself." It directly demonstrates the extension patterns [R001](../rules/R001-core-isolation-non-invasive-extension.md), [R007](../rules/R007-thin-hooks-centralized-service-layer.md), and [R010](../rules/R010-one-doctype-one-responsibility.md) already codify, at real scale.
**Risks:** Large surface area — extraction should target specific, well-bounded patterns (a single DocType's structure, a single service module) rather than treating the whole app as one undifferentiated blob.
**Can AI safely learn from it?** Yes, this catalog's top code-source recommendation.
**Recommended Priority:** **P0**.

### KS-0034 — `frappe/crm`

**URL:** `https://github.com/frappe/crm`
**Description:** Official, fully-featured open-source CRM, built on the modern Frappe UI/Vue stack, designed to integrate with ERPNext.
**Why valuable:** The best available reference for the *current-generation* frontend architecture (Frappe UI patterns) as opposed to legacy Desk-era JS patterns still common in older ERPNext modules.
**Risks:** Represents newer architectural conventions that may diverge from older parts of `frappe/erpnext` itself — when the two disagree, treat `frappe/crm` as more representative of current best practice, not `frappe/erpnext`'s oldest modules.
**Can AI safely learn from it?** Yes.
**Recommended Priority:** **P0**.

### KS-0035 through KS-0042 — Remaining First-Party Product Apps

`frappe/lms` (Learning Management), `frappe/helpdesk` (Customer Service), `frappe/insights` (BI/Analytics), `frappe/books` (Accounting), `frappe/drive` (Document storage/collaboration), `frappe/gameplan` (Team collaboration), `frappe/builder` (No-code site builder), `frappe/wiki` (Documentation/wiki app) — all official, all open-source, all built on the same framework this project targets.

**Common profile:** Maintainer Frappe Technologies Pvt. Ltd.; update frequency active but lower than the two flagship repos; coverage is product-specific; trust derives from official first-party authorship; shared risk is that each represents one product's specific domain, so patterns should be generalized carefully rather than assumed universal.
**Can AI safely learn from them?** Yes, all of them.
**Recommended Priority:** **P1–P2**, sequenced by product maturity/star count as shown in the ranking table.

### KS-0043 — `frappe/frappe-ui`

**URL:** `https://github.com/frappe/frappe-ui`
**Description:** The official component/utility library for rapid UI development on Frappe — the shared foundation `frappe/crm`, `frappe/helpdesk`, and other modern-stack products are built from. Has GitHub Discussions enabled with active categories (General, Q&A, Show and Tell).
**Why valuable:** The single canonical reference for current frontend conventions across the entire modern Frappe product line.
**Can AI safely learn from it?** Yes.
**Recommended Priority:** **P0/P1**.

### KS-0044 — `frappe/bench`

**URL:** `https://github.com/frappe/bench`
**Description:** The official CLI for managing multi-tenant Frappe deployments — the tool every `bench get-app`/`bench install-app`/`bench migrate` reference in [R005](../rules/R005-idempotent-upgrade-safe-deployment.md) and [R006](../rules/R006-full-reproducibility-fixtures-and-patches.md) actually is.
**Why valuable:** Ground truth for deployment/installation mechanics this project's own rules already depend on being correct.
**Can AI safely learn from it?** Yes.
**Recommended Priority:** **P0**.

### KS-0045 — `frappe/frappe_docker`

**URL:** Referenced via Frappe Gems listing; canonical location under the `frappe` GitHub org.
**Description:** Official Docker-based deployment reference. ~2,466 stars, ~2,639 forks confirmed — notably more forks than stars, suggesting heavy fork-and-adapt usage typical of infrastructure templates.
**Why valuable:** Canonical containerized deployment pattern.
**Can AI safely learn from it?** Yes.
**Recommended Priority:** **P1**.

### KS-0032 — Frappe Gems Directory

**URL:** `https://frappegems.com/`
**Description:** An automated, third-party-built directory that scans GitHub hourly for repositories carrying Frappe-related topics, validates them as genuine Frappe apps, detects framework-version compatibility from branch names, and catalogs maintenance-status metadata. 300+ apps indexed at research time.
**Maintainer:** Nesscale Solutions Pvt Ltd (third-party, not Frappe Technologies).
**Why valuable:** This is a **discovery and triage layer**, not a content source in itself — its value is systematically surfacing the long tail of third-party apps (KS-0047) with built-in freshness (hourly scans) and maintenance-status signal, which no purely manual "awesome list" can match at this update frequency.
**Risks:** Indexes apps of wildly variable quality; inclusion in the directory is a discoverability signal, not a quality certification — same caveat as KS-0021.
**Can AI safely learn from it?** Yes, as a discovery/triage index feeding the vetting gate in [§13](#13-long-tail-vetting-gate).
**Recommended Priority:** **P1** (as discovery infrastructure).

### KS-0046 — `frappe/press`

**URL:** `https://github.com/frappe/press`
**Description:** The actual codebase powering Frappe Cloud — Frappe's own multi-tenant SaaS hosting platform.
**Why lower-ranked despite being official:** Represents advanced, cloud-provider-specific, multi-tenant-at-scale infrastructure patterns that are not representative of a typical single-tenant self-hosted custom-app project — the exact opposite of this project's usual target scenario.
**Can AI safely learn from it?** Yes, but scope every extracted pattern explicitly as "Frappe Cloud-specific," not general guidance.
**Recommended Priority:** **P2**.

### KS-0047 — Long-Tail Third-Party Apps (via GitHub topics `erpnext-app`/`frappe-app`, surfaced through KS-0032/KS-0021)

**Description:** The large, variable-quality population of community-built custom apps discoverable through the two indexes above.
**Why not individually scored:** A single trust number cannot honestly represent a population ranging from carefully-engineered, actively-maintained apps to unmaintained student projects — assigning one score here would itself be a data-quality failure of this catalog.
**Recommended treatment:** A mandatory per-repo vetting gate before any individual long-tail app is promoted into this catalog as a named entry — see [§13](#13-long-tail-vetting-gate).
**Recommended Priority:** **P2** for discovery; individual promotion only after vetting.

### KS-0048 — Frappe Cloud Marketplace

**URL:** `https://cloud.frappe.io/marketplace/apps/...` (per-app pages, e.g. `.../erpnext_telegram_integration`)
**Description:** Frappe Cloud's official app marketplace — distinct from KS-0032 in that marketplace listing implies a submission/review relationship with Frappe Technologies (installability directly into managed Frappe Cloud sites), giving a different, arguably stronger quality signal than an auto-scanned GitHub topic.
**Maintainer:** Platform operated by Frappe Technologies; individual apps published by their own third-party authors.
**Why valuable:** A pre-filtered subset of the long tail with real production-installation signal (apps installable directly by paying Frappe Cloud customers).
**Risks:** Marketplace presence is a platform-compatibility and packaging signal, not necessarily a code-quality guarantee — still apply the vetting gate before treating any specific marketplace app as a reference implementation.
**Can AI safely learn from it?** Yes, as a higher-confidence subset of the long tail.
**Recommended Priority:** **P1** (as discovery infrastructure, alongside KS-0032).

---

## 7. Trust Matrix

Cross-tier view, sorted by Trust Score, top 20 shown in full; see per-tier tables above for the complete 48.

| Trust | ID | Source | Tier | AI-Safe? |
|---|---|---|---|---|
| 98 | KS-0003 | `frappe/frappe` source | 1 | Yes |
| 98 | KS-0004 | `frappe/erpnext` source | 1 | Yes |
| 93 | KS-0010 | GitHub Releases/Changelogs | 1 | Yes (verify prose vs. PR) |
| 93 | KS-0033 | `frappe/hrms` | 5 | Yes |
| 92 | KS-0001 | Frappe Doc Hub | 1 | Yes (version-tag) |
| 92 | KS-0016 | `frappe/frappe` merged PRs | 2 | Yes |
| 90 | KS-0009 | Frappe Engineering Blog | 1 | Yes |
| 90 | KS-0018 | Commit History | 2 | Yes (corroborating) |
| 90 | KS-0034 | `frappe/crm` | 5 | Yes |
| 90 | KS-0044 | `frappe/bench` | 5 | Yes |
| 88 | KS-0008 | Frappe Cloud Docs | 1 | Yes (scoped) |
| 88 | KS-0019 | Staff forum replies | 2 | Yes (needs staff ID) |
| 88 | KS-0043 | `frappe/frappe-ui` | 5 | Yes |
| 85 | KS-0006 | Frappe School | 1 | Yes (transcribe) |
| 85 | KS-0014 | `frappe/frappe` Issues | 2 | Yes (filtered) |
| 85 | KS-0015 | `frappe/erpnext` Issues | 2 | Yes (filtered) |
| 85 | KS-0035 | `frappe/lms` | 5 | Yes |
| 85 | KS-0036 | `frappe/helpdesk` | 5 | Yes |
| 85 | KS-0037 | `frappe/insights` | 5 | Yes |
| 85 | KS-0045 | `frappe/frappe_docker` | 5 | Yes |

**Bottom of the matrix, for visibility:**

| Trust | ID | Source | Tier | AI-Safe? |
|---|---|---|---|---|
| 30 | KS-0025 | Implementation-partner blogs | 3 | Partial, spot-check only |
| 30 | KS-0031 | LinkedIn individual posts | 4 | Partial, company page only |
| 25 | KS-0029 | Reddit | 4 | No (unconfirmed community) |
| 20 | KS-0026 | SEO "ERPNext guide" blogs | 3 | **No — excluded** |
| 5 | KS-0030 | Discord | 4 | **No — never use** |

---

## 8. Knowledge Acquisition Roadmap

Four phases. Each phase is a *precondition* for meaningfully starting the next, mirroring the discipline already established in this repository's [Research → Rule → Skill → Agent pipeline](../ROADMAP.md#phase-2--knowledge-engineering) — extraction should not race ahead of foundation-laying, the same way Skills aren't built ahead of Rules.

**Phase A — Ground Truth Foundation.** Sources: KS-0001, KS-0003, KS-0004, KS-0010, KS-0018 (Tier 1 core docs + both flagship source repos + changelogs + commit history). Goal: establish an unambiguous, version-tagged baseline of *what the framework and ERPNext actually are and do*, before any interpretive or community content is ingested that could otherwise be taken at face value without a ground-truth anchor to check it against.

**Phase B — Engineering Rationale.** Sources: KS-0016, KS-0009, KS-0011, KS-0014, KS-0015, KS-0019, KS-0020. Goal: layer in *why* — the PR discussions, engineering blog posts, architecture handbook, and resolved issues that explain the reasoning behind Phase A's facts. This phase is exactly what this project's own Rule format ([Rationale](../docs/ENGINEERING_RULE_SPECIFICATION.md#3-rule-structure) field) needs to be well-sourced rather than asserted.

**Phase C — Production-Grade Reference Implementations.** Sources: all of Tier 5's official `frappe/*` products (KS-0032 through KS-0046, excluding the long tail), ranked per [§6](#6-tier-5--code-sources-ranked-by-code-quality). Goal: mine real, idiomatic, at-scale application code for the concrete patterns Rules' Good/Bad Pattern sections need, and that templates/skills will eventually scaffold from.

**Phase D — Community Corroboration and Gap-Filling.** Sources: KS-0005 (forum, general), KS-0021, KS-0006, KS-0008, KS-0024, KS-0027, and vetted long-tail apps per [§13](#13-long-tail-vetting-gate). Goal: fill gaps Phases A–C left open, and corroborate (or surface contradictions with) the ground-truth foundation — never to introduce claims Phase A/B/C can't verify.

**Explicitly out of scope for this roadmap:** KS-0026, KS-0029, KS-0030 are not phased in at all — see [§10](#10-sources-that-should-never-be-used).

---

## 9. Which Sources Should Be Crawled First

The **first-wave crawl set** (Phase A + the highest-priority items of Phase B/C), in priority order:

1. `KS-0003` — `frappe/frappe` source
2. `KS-0004` — `frappe/erpnext` source
3. `KS-0001` — Frappe Documentation Hub
4. `KS-0010` — GitHub Releases/Changelogs
5. `KS-0016` — `frappe/frappe` merged PRs
6. `KS-0018` — Commit history
7. `KS-0009` — Frappe Engineering Blog
8. `KS-0033` — `frappe/hrms`
9. `KS-0034` — `frappe/crm`
10. `KS-0044` — `frappe/bench`

These ten alone cover: exact current framework/ERPNext behavior, why it evolved that way, and two gold-standard reference implementations — sufficient to bootstrap a first, defensible version of the knowledge base before any community or Q&A content is touched at all.

---

## 10. Sources That Should Never Be Used

| ID | Source | Reason |
|---|---|---|
| KS-0030 | Discord | No confirmed official server exists; the name resolves almost entirely to an unrelated Roblox roleplay community (~59,800 members). Ingesting under this name risks contaminating the knowledge base with off-topic content. |
| KS-0026 | Third-party SEO "ERPNext guide/review" blogs | Investigated and rejected: templated content-marketing structure, no engineering depth, no verifiable technical claims. |

**Conditionally excluded (not a hard "never," but excluded by default pending stronger evidence):**

| ID | Source | Condition for reconsideration |
|---|---|---|
| KS-0029 | Reddit | Re-evaluate only if a specific, actively-populated subreddit is independently confirmed to exist. |
| KS-0028 | Telegram | Excluded from default RAG ingestion (not from human use) until dedicated scraping/trust-filtering tooling exists. |
| KS-0031 | LinkedIn individual posts | Excluded by default; a specific post may be individually vetted and cited as `Reference` (`REF`), never bulk-ingested. |

---

## 11. Recommended Crawl Order

Full sequencing across all four roadmap phases, source IDs only (see [§8](#8-knowledge-acquisition-roadmap) for phase rationale, per-source profiles above for detail):

```
Phase A:  KS-0003 → KS-0004 → KS-0001 → KS-0010 → KS-0018

Phase B:  KS-0016 → KS-0014 → KS-0015 → KS-0009 → KS-0011 → KS-0019 → KS-0020

Phase C:  KS-0033 → KS-0034 → KS-0043 → KS-0044 → KS-0045 →
          KS-0035 → KS-0036 → KS-0037 → KS-0038 →
          KS-0039 → KS-0040 → KS-0041 → KS-0042 → KS-0046

Phase D:  KS-0005 → KS-0021 → KS-0032 → KS-0048 → KS-0006 → KS-0008 →
          KS-0007 → KS-0013 → KS-0024 → KS-0027 → KS-0022 → KS-0023 →
          KS-0002 → KS-0012 → KS-0025 → (vetted KS-0047 entries, individually, as they pass §13)

Excluded entirely: KS-0026, KS-0030
Conditionally excluded: KS-0028, KS-0029, KS-0031
```

---

## 12. Suggested Refresh Cadence

| Cadence | Sources |
|---|---|
| **Continuous / live-tracked** (re-check on every crawl run) | KS-0003, KS-0004, KS-0010, KS-0018, KS-0014, KS-0015, KS-0016 — these change with every merge; a RAG index built from a stale snapshot of active source code is actively dangerous. |
| **Weekly** | KS-0001, KS-0005, KS-0009 (check for new posts), KS-0032, KS-0048 (both scan-based directories) |
| **Monthly** | KS-0006, KS-0008, KS-0011, KS-0019 (re-sample), KS-0021, KS-0022, KS-0027 |
| **Per-release (on any new major ERPNext/Frappe version)** | KS-0002 (re-check canonical-vs-KS-0001 status), all Tier 5 `frappe/*` product repos, KS-0046 |
| **Quarterly** | KS-0007, KS-0013, KS-0025 (re-spot-check the category, not exhaustive re-crawl) |
| **Annual / event-driven** | KS-0024 (tied to the Frappeverse event calendar) |
| **On-demand only, never scheduled** | KS-0012 (low-value, crawl once, recheck rarely), conditionally-excluded Tier 4 sources if ever promoted out of exclusion |

---

## 13. Long-Tail Vetting Gate

Before any individual repository surfaced via KS-0032 (Frappe Gems), KS-0021 (awesome-frappe), or KS-0048 (Frappe Cloud Marketplace) is promoted from "discovered" to a named, trusted entry in this catalog, it must pass all of the following:

1. **Confirmed Frappe/ERPNext app** — not merely topic-tagged; verify it actually installs as a Frappe app (has a valid `hooks.py`, is structured as a real bench app).
2. **Active maintenance** — a commit within the last 12 months, or an explicit, credible statement of stability (e.g., "feature-complete, maintenance mode") from the maintainer.
3. **Non-trivial adoption signal** — real stars/forks/issues activity, or confirmed production use referenced by the maintainer or a third party, not just existence.
4. **License clarity** — an OSI-recognized open-source license, unambiguous enough to know what can legally be learned from and referenced.
5. **No core-isolation violations on inspection** — a spot-check confirming the app doesn't itself violate [R001](../rules/R001-core-isolation-non-invasive-extension.md) (e.g., ships patched vendor-app files) — an app that violates this project's own foundational rule should not be held up as a reference example of good practice, regardless of its popularity.

A repository failing any of these five remains discoverable (via KS-0032/KS-0021/KS-0048 themselves) but is not promoted to an individually-cataloged, trusted source.

---

## 14. Verification & Currency Disclaimer

Every quantitative figure in this catalog (star counts, fork counts, member counts, release dates) was gathered via live web search on **2026-07-23** and represents a single snapshot, not a continuously-tracked metric. Several figures could not be independently confirmed during this research pass and are explicitly marked "not confirmed" rather than estimated — this catalog does not fabricate a plausible-sounding number where none was found, per this project's standing evidence discipline (see [docs/ENGINEERING_RULE_SPECIFICATION.md § 2](../docs/ENGINEERING_RULE_SPECIFICATION.md#2-responsibilities) on unevidenced claims not qualifying as trustworthy input).

Before this catalog is used as the input to an actual crawl/ingestion pipeline: re-verify GitHub star/fork counts via the GitHub API directly (cheap, exact, live), re-confirm forum/Telegram member counts via their own platforms if those numbers become decision-relevant, and re-check that KS-0002's relationship to KS-0001 has not been clarified or resolved since this catalog was written (official communication may eventually state one is canonical and the other deprecated).

---

## 15. What This Catalog Deliberately Does Not Do

Per the task's own scope: **no knowledge has been extracted** from any source above into this repository's `rules/` or `research/`. This catalog answers "where should we look, and how much should we trust what we find" — not "what did we find." Extraction is separately-scoped future work, to be conducted per source, starting with Phase A, following this repository's existing [Research → Engineering Rule](../docs/ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle) pipeline rather than dumping raw source content directly into a rule.
