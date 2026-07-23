# knowledge-sources/

## Purpose

Registers the external bodies of knowledge this repository draws on, per the `Knowledge Source` (`KS`) artifact type defined in [ENGINEERING_META_MODEL.md § Knowledge Artifact Catalog, entry 24](../ENGINEERING_META_MODEL.md#24-knowledge-source-ks). A `Knowledge Source` is a whole external source (a documentation site, a forum, a repository), tracked for provenance and staleness — as distinct from `Reference` (`REF`), which points at one specific document within such a source.

## What belongs inside

[KNOWLEDGE_SOURCE_CATALOG.md](KNOWLEDGE_SOURCE_CATALOG.md) — the full ERPNext/Frappe knowledge source catalog: every source this project could draw on, evaluated, scored, tiered, and sequenced into an acquisition roadmap.

## A deliberate deviation from the folder mapping's literal form, noted here

[ENGINEERING_META_MODEL.md § Repository Folder Mapping](../ENGINEERING_META_MODEL.md#repository-folder-mapping) shows this folder holding one file per source (`KS-####.md`). At the catalog's current size (~48 sources), a single registry document is more maintainable and more readable as the deliverable it actually is — a catalog to be read top to bottom, cross-referenced, and re-scored as a whole — than 48 near-empty files would be. Every source inside the catalog still carries its own stable `KS-####` ID per [Naming Standards](../ENGINEERING_META_MODEL.md#naming-standards), so nothing about identity or cross-referencing is lost. This is a file-granularity judgment call, not an architecture change (`knowledge-sources/` was already reserved and empty; nothing frozen is touched) — it does not require an ADR, unlike [ADR-0001](../adr/ADR-0001-ai-retrieval-metadata-layer.md)'s addition of new artifact types. A source is worth splitting into its own `KS-NNNN.md` file once it needs detail this catalog can't hold cleanly — e.g., a per-version staleness history — not before.

## What does NOT belong inside

Actual extracted knowledge (facts, rules, code patterns) drawn *from* these sources — that belongs in `research/`, `rules/`, or wherever the [Knowledge Hierarchy](../ENGINEERING_META_MODEL.md#knowledge-hierarchy) routes it once extraction begins. This folder only tracks *where* knowledge may come from and how much to trust it — extraction is explicitly out of scope for the catalog itself.

## Lifecycle

Per the `Knowledge Source` artifact type: Registered → Actively cited → Reviewed periodically for continued relevance → Retired if the source itself is discontinued. See the catalog's own [Suggested Refresh Cadence](KNOWLEDGE_SOURCE_CATALOG.md#12-suggested-refresh-cadence) section for how often each entry should be re-verified.
