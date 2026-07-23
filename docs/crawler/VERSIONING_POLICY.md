# VERSIONING POLICY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md).
**Scope:** Two genuinely different things this document must not let blur together: versioning of the **framework's own software components** (connectors, parsers, schemas), and the framework's role in capturing **version-awareness of crawled content** (which ERPNext/Frappe release a fact applies to). The second is already specified by [`KNOWLEDGE_PIPELINE.md § 4`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail) and unchanged here — this document only says which crawler stage is responsible for populating it faithfully.

---

## 1. Component Versioning (the Framework's Own)

| Component | Versioning scheme | Why it matters |
|---|---|---|
| **Connector** | Semver against [`SOURCE_CONNECTOR_SPEC.md`](SOURCE_CONNECTOR_SPEC.md)'s contract — a MAJOR bump means the contract itself changed incompatibly (rare, since the contract is fixed framework-wide); a MINOR/PATCH bump is a connector-internal change (a fixed discovery-strategy bug, an adjusted rate-limit declaration) | Every `Knowledge Document`'s provenance records the exact connector version that produced it ([`KNOWLEDGE_ARTIFACTS.md § 1`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#1-the-common-envelope)'s `metadata.extractor_version`) — reproducing *why* a document looks the way it does requires knowing which connector version ran, not just which connector |
| **Parser** | Semver against its content-type's expected structural output shape — a MAJOR bump changes what `structural_metadata` looks like for that content-type | A parser version bump is exactly the trigger for [§3](#3-re-processing-on-parser-upgrade) below; tracking it is what makes re-processing targeted instead of "reparse everything, just in case" |
| **Crawl Item schema** ([`CRAWLER_PIPELINE.md § 0`](CRAWLER_PIPELINE.md#0-the-crawl-item--one-contract-nine-consumers)) | Semver, framework-wide, single version number | A MAJOR bump here is the rare, deliberate event requiring the same Architecture Review discipline as any other frozen-architecture change in this repository |

## 2. Compatibility Rule

A connector or parser declaring compatibility with Crawl Item schema version `N` may run unmodified against any `N.x` framework release; a framework MAJOR version bump requires every connector to explicitly re-declare compatibility (not silently assumed) before it is allowed to run — this is the same discipline [`docs/ai-retrieval/METADATA_SCHEMA.yaml`](../ai-retrieval/METADATA_SCHEMA.yaml)'s `schema_version` field already enforces one layer up, at the `Rule Metadata Record` level, applied here to the crawler's own internal contract.

## 3. Re-Processing on Parser Upgrade

When a parser's version bumps, every `Knowledge Document` previously produced using the old parser version is **not** automatically invalidated — it is flagged eligible for re-parse, and re-parsing runs opportunistically (next scheduled refresh, per [`KNOWLEDGE_REFRESH_POLICY.md § 1`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#1-refresh-cadence-by-source-type)) rather than triggering an immediate mass re-crawl. If the re-parse produces a materially different `structural_metadata`, the outcome is treated exactly like any other content change per [`KNOWLEDGE_REFRESH_POLICY.md § 3`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#3-staleness-propagation)'s staleness cascade — a parser upgrade is, from the Knowledge Pipeline's point of view, indistinguishable from the source itself changing, and is deliberately handled through the exact same mechanism rather than a second, parallel one.

## 4. Content Version-Awareness — Responsibility, Not Redesign

[`CRAWLER_PIPELINE.md § 7`](CRAWLER_PIPELINE.md#7-extract-metadata) (Extract Metadata) is the one stage responsible for populating the `explicit`/`stated`/`inferred` version-confidence band [`KNOWLEDGE_PIPELINE.md § 4`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail) already defines. This document adds nothing to that definition — it only confirms which stage owns the responsibility, so a future connector implementer knows exactly where in the pipeline version-tagging happens rather than having to infer it.

## 5. What This Document Deliberately Does Not Version

`Knowledge Source` Trust Scores, `Knowledge Document` content itself, and anything in [`knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) — those remain outside the Crawler Framework's authority entirely, per [`CRAWLER_ARCHITECTURE.md § 2.1`](CRAWLER_ARCHITECTURE.md#21-where-this-frameworks-output-boundary-is).
