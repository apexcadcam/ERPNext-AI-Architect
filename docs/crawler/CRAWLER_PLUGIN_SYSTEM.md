# CRAWLER PLUGIN SYSTEM

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). Governs how a new [Source Connector](SOURCE_CONNECTOR_SPEC.md) is added to the framework.
**Scope:** The plugin boundary — what a new source must provide, what it must never need to touch, and how the framework discovers it. No code, no skeleton classes.

---

## 1. One Folder, One Source, Zero Shared-Code Edits

```
crawler/                        [reserved path — not created by this document, see §5]
    core/                       # pipeline stages (CRAWLER_PIPELINE.md), queue, storage client — shared, never edited to add a source
    sources/
        frappe_docs/            # one connector: documentation-site type
        github/                 # one connector: git-repository type (covers KS-0003, KS-0004, and every first-party product repo)
        forum/                  # one connector: discourse-forum type
        youtube/                # one connector: video-platform type
        marketplace/            # one connector: app/marketplace-directory type
        <new_source>/           # adding source #50 looks exactly like adding source #6
```

Each `sources/<name>/` folder is **self-contained**: its own configuration, its own discovery-strategy logic, its own auth handling, its own declared parser bindings. Nothing under `core/` is aware that `<new_source>/` exists until it self-registers per [§2](#2-registration-not-modification).

---

## 2. Registration, Not Modification

A new connector becomes active by **declaring itself** against the fixed [`SOURCE_CONNECTOR_SPEC.md`](SOURCE_CONNECTOR_SPEC.md) contract and being discovered through a **manifest-based registry** — the framework enumerates `sources/*/` at startup (or from a registry file each connector contributes one entry to) and instantiates whatever satisfies the contract. Adding source #50 requires:

1. A new folder under `sources/`.
2. A manifest entry (or self-registration call, made once, inside that folder — never inside `core/`) declaring the connector's identity and which pipeline-stage implementations it supplies (its discovery strategy, and optionally a custom parser binding if [`PARSER_SPEC.md`](PARSER_SPEC.md)'s existing format parsers don't already cover its content-type).
3. Nothing else. **No shared file is edited.** No `if source == "github"` branch is ever added anywhere in `core/` — the moment such a branch would be needed, that is itself a defect in the plugin boundary, not a normal cost of adding a source.

This is the Open/Closed Principle applied at the architecture level: `core/` is closed for modification, `sources/` is open for extension — the same shape [`ENGINEERING_META_MODEL.md`](../../ENGINEERING_META_MODEL.md)'s own `MCP`/`Tool` split already models (a `Tool` is added by registering it to an `MCP`, never by editing the `MCP`'s own execution logic).

---

## 3. What a New Connector Must Provide

Exactly the fields [`SOURCE_CONNECTOR_SPEC.md`](SOURCE_CONNECTOR_SPEC.md) requires, and one thing per pipeline stage it customizes:

| Pipeline stage | Does every connector need its own? |
|---|---|
| Discover | **Yes, always** — the one truly source-specific stage (a sitemap walker, a paginated API client, a git-ref lister are all different) |
| Queue | No — shared, configured only by the connector's declared priority/rate-limit policy |
| Download | No — shared HTTP/git client, parameterized by the connector's [`DOWNLOAD_POLICY.md`](DOWNLOAD_POLICY.md) settings and [`SOURCE_CONNECTOR_SPEC.md`](SOURCE_CONNECTOR_SPEC.md)'s authentication declaration |
| Validate | No — shared, content-type-driven |
| Normalize, Parse | Only if the source's content-type isn't already covered by an existing [`PARSER_SPEC.md`](PARSER_SPEC.md) parser — a genuinely new format (e.g., the first video-transcript source) contributes one new parser, reusable by every future connector of the same content-type, never duplicated per-connector |
| Extract Metadata | No — shared, driven by declarative field-mapping in the connector's manifest (e.g., "title comes from this JSON path" / "this HTML selector") |
| Persist, Emit Event | No — entirely shared |

**In the common case — a new source whose content-type already has a parser — adding a connector means writing exactly one thing: its Discover strategy and its manifest.** This is the concrete, checkable meaning of "minimal code changes" the task requires.

---

## 4. What a New Connector Must Never Do

- Reach into another connector's state, configuration, or rate-limit budget.
- Bypass [`CRAWLER_PIPELINE.md`](CRAWLER_PIPELINE.md)'s stage sequence — a connector cannot skip Validate, or persist directly without going through the shared Persist stage, regardless of how "obviously fine" its content is.
- Assert its own trust score, confidence, or version-scoping override — those remain owned by [`knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) and [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md) respectively, per [`CRAWLER_ARCHITECTURE.md § 2.1`](CRAWLER_ARCHITECTURE.md#21-where-this-frameworks-output-boundary-is) — a connector that tried would be out of contract, not just bad practice.

---

## 5. Where This Actually Lives

`crawler/` is a **reserved, not-yet-created** top-level path, named exactly as the task's own example — this document does not create it, per the "no implementation" constraint. The one artifact this document set *does* create, additively, is the storage location crawled output lands in once a connector runs — see [`STORAGE_LAYOUT.md`](STORAGE_LAYOUT.md) and its small extension to [`ENGINEERING_META_MODEL.md`](../../ENGINEERING_META_MODEL.md)'s existing `knowledge-sources/pipeline/` reservation from [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md).

---

## 6. Mapping Today's 48 Sources onto Connector Count

Per [`KNOWLEDGE_PIPELINE.md § 1`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type), acquisition method is already defined **per source type**, not per individual source — so one `github` connector already covers `KS-0003`, `KS-0004`, and all fourteen other git-hosted sources; one `frappe_docs`-style documentation-site connector (generalized, not literally named after one source) covers every documentation-site source; and so on. Today's 48 cataloged sources require on the order of the eight source types already enumerated, not 48 separate connectors — the plugin system's real test is the *next* genuinely new source type (a source this catalog hasn't seen yet), which is exactly what [§3](#3-what-a-new-connector-must-provide)'s "write one Discover strategy" bar is designed to make cheap.
