# CRAWLER FRAMEWORK ARCHITECTURE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [PROJECT_CHARTER.md](../../PROJECT_CHARTER.md) and [ENGINEERING_META_MODEL.md](../../ENGINEERING_META_MODEL.md). Sits *beneath* the [Knowledge Pipeline](../knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md), which is treated as frozen per this task's instruction — this document set does not redesign it, only gives its Acquisition stage a concrete, extensible execution architecture.
**Scope:** How bytes actually get from a `Knowledge Source` on the internet into a validated [`Knowledge Document`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#21-knowledge-document) — the mechanical layer, not the knowledge-judgment layer. No implementation, no code, no skeleton classes.

---

## 1. What This Is, and Isn't

This is the architecture for a **general-purpose crawling framework** — modular enough that adding the 49th source connector is exactly as easy as adding the 2nd, in the spirit of Scrapy's spider/middleware architecture or LangChain's document-loader ecosystem, but purpose-built for this project's specific downstream contract: everything it produces must be a valid [`Knowledge Document`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#21-knowledge-document), ready for [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md) to gate.

It is **not**: a redesign of [`KNOWLEDGE_PIPELINE.md`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md)'s Acquisition → Cleaning → Normalization → Deduplication stages (§2 reconciles the two explicitly), a knowledge-extraction system (extraction remains entirely owned by [`KNOWLEDGE_EXTRACTION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md), which this framework never touches), or a running system (nothing here has been built — no connector exists, no bytes have been fetched).

---

## 2. Relationship to the Existing, Frozen Architecture

### 2.1 Where this framework's output boundary is

The Crawler Framework's job ends the moment it has produced a structurally-valid, normalized `Knowledge Document` and emitted the event announcing it. Everything past that point — epistemic validation (trust, conflicts, confidence), knowledge extraction, the graph, embeddings, retrieval — is untouched, unre-derived, and remains exactly as specified in [`docs/knowledge-pipeline/`](../knowledge-pipeline/). This is a hard boundary, not a soft convention: **the Crawler Framework has no concept of "trust score," "confidence," or "conflict"** — those are judgments the [Knowledge Source Catalog](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) and [Knowledge Pipeline](../knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md) already own. A crawler that silently started making trust decisions would be exactly the "MCP holds no architectural judgment" invariant violated — see [§2.3](#23-why-no-new-knowledge-artifact-type-and-no-adr).

### 2.2 Mapping the crawler's lifecycle onto the Knowledge Pipeline's stages

The task's requested lifecycle (Discover → Queue → Download → Validate → Normalize → Parse → Extract Metadata → Persist Raw Document → Emit Pipeline Event) is a **finer-grained decomposition** of what [`KNOWLEDGE_PIPELINE.md § 0`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#0-stage-overview) already named at coarser grain. Neither renames nor contradicts the other:

| Crawler Framework stage | Realizes | Knowledge Pipeline stage |
|---|---|---|
| Discover, Queue, Download | | [Acquisition](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#2-acquisition-stage-1-detail) |
| Validate *(transport-level: well-formed response, correct content-type, not corrupted)* | | Not previously named at this grain — new, and deliberately **not** the same concept as `KNOWLEDGE_VALIDATION_SPEC.md`'s epistemic validation; see [§2.4](#24-two-different-things-named-validate) |
| Normalize, Parse | | [Cleaning](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#3-cleaning-stage-2-detail) + [Normalization](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail) |
| Extract Metadata *(document-level: title, author, publish date, URL, content-hash)* | | Populates the `Knowledge Document`'s own envelope fields — **not** [`KNOWLEDGE_EXTRACTION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md)'s knowledge-claim extraction, which runs later, on validated documents, and is out of this framework's scope entirely |
| Persist Raw Document | | New — [`KNOWLEDGE_PIPELINE.md`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md) described the *Knowledge Document* artifact but not its physical storage; [`STORAGE_LAYOUT.md`](STORAGE_LAYOUT.md) fills that gap |
| Emit Pipeline Event | | The concrete trigger for [`KNOWLEDGE_VALIDATION_SPEC.md § 1`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#1-schema-validation) — previously described only as "gates every artifact," now given an actual handoff mechanism |
| *(cross-document, cross-connector near-duplicate detection)* | | Remains [`Deduplication`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#5-deduplication-stage-4-detail)'s job, run *after* Persist, across documents from potentially different connectors — the Crawler Framework's own [`CACHE_STRATEGY.md`](CACHE_STRATEGY.md) only prevents re-fetching *unchanged* content from the *same* source, a different and narrower concern |

Full stage-by-stage contracts: [`CRAWLER_PIPELINE.md`](CRAWLER_PIPELINE.md).

### 2.3 Why no new Knowledge Artifact type, and no ADR

A Source Connector fetches; it never judges. That is precisely the role [`ENGINEERING_META_MODEL.md` entries 20–21](../../ENGINEERING_META_MODEL.md#20-mcp-mcp) (`MCP`/`Tool`) already define: *"MCP only executes Tools; it holds no architectural judgment of its own... never generates or modifies Rules, Skills, or Agents."* A Source Connector is, structurally, a `Tool` — an individually invocable, permission-scoped, mechanical capability — and the Crawler Framework as a whole is structurally an `MCP`-shaped execution boundary. Reusing that existing pair, rather than minting a competing "Connector" artifact type in the Knowledge Artifact Catalog, is a direct application of [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md) and [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md)'s established discipline — but unlike those two, this is not a contested choice with a rejected alternative worth recording formally: `MCP`/`Tool` already fit without adjustment, so no ADR is written for it. What *is* new and reserved is the concrete storage location for what a connector produces — see [`STORAGE_LAYOUT.md`](STORAGE_LAYOUT.md) and the small, additive folder-mapping refinement it makes to [`ENGINEERING_META_MODEL.md`](../../ENGINEERING_META_MODEL.md).

### 2.4 Two different things named "Validate"

To prevent exactly the kind of silent ambiguity this project's own Design Principles warn against: **Crawler-level Validate** ([`CRAWLER_PIPELINE.md § 4`](CRAWLER_PIPELINE.md#4-validate)) asks *"is this a complete, well-formed, uncorrupted download of the expected content-type?"* — a transport/structural question, answerable without understanding a word of the content. **Knowledge-level Validate** ([`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md)) asks *"should this claim be trusted?"* — an epistemic question, answerable only after extraction. A document can pass the first and still fail the second; a document that fails the first never reaches the second at all.

---

## 3. Non-Functional Requirements, and Where Each Is Addressed

| Requirement | Primarily addressed in |
|---|---|
| **Extensible** | [`CRAWLER_PLUGIN_SYSTEM.md`](CRAWLER_PLUGIN_SYSTEM.md) — a new source requires no edits to shared code |
| **Deterministic** | [`CRAWLER_PIPELINE.md`](CRAWLER_PIPELINE.md)'s fixed stage contracts; [`PARSER_SPEC.md`](PARSER_SPEC.md)'s pure-function parsing rule |
| **Observable** | [`OBSERVABILITY.md`](OBSERVABILITY.md) |
| **Testable** | [`TESTING_STRATEGY.md`](TESTING_STRATEGY.md) |
| **Version-aware** | [`VERSIONING_POLICY.md`](VERSIONING_POLICY.md); content version-tagging inherited unchanged from [`KNOWLEDGE_PIPELINE.md § 4`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail) |
| **Source-agnostic** | [`SOURCE_CONNECTOR_SPEC.md`](SOURCE_CONNECTOR_SPEC.md)'s single fixed contract every connector implements regardless of source type |
| **High-performance** | [`RATE_LIMITING.md`](RATE_LIMITING.md), [`CACHE_STRATEGY.md`](CACHE_STRATEGY.md) — never doing work that's already been done |
| **Fault-tolerant** | [`RETRY_POLICY.md`](RETRY_POLICY.md), [`ERROR_HANDLING.md`](ERROR_HANDLING.md) |
| **AI-ready** | Every produced artifact is a schema-valid `Knowledge Document` on the first try — no post-hoc reshaping needed before [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md) can gate it |

---

## 4. Document Map

| Document | Answers |
|---|---|
| [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md) | This document. |
| [CRAWLER_PIPELINE.md](CRAWLER_PIPELINE.md) | What are the nine stages, and what exactly does each one consume and produce? |
| [CRAWLER_PLUGIN_SYSTEM.md](CRAWLER_PLUGIN_SYSTEM.md) | How is a new source added, with minimal changes to anything shared? |
| [SOURCE_CONNECTOR_SPEC.md](SOURCE_CONNECTOR_SPEC.md) | What must every connector declare, regardless of source type? |
| [STORAGE_LAYOUT.md](STORAGE_LAYOUT.md) | Where do raw HTML, PDFs, images, JSON, metadata, and cache actually live? |
| [DOWNLOAD_POLICY.md](DOWNLOAD_POLICY.md) | How does downloading behave — concurrency, timeouts, redirects, robots.txt? |
| [PARSER_SPEC.md](PARSER_SPEC.md) | How is raw content turned into structured content, per format? |
| [RATE_LIMITING.md](RATE_LIMITING.md) | How is politeness and platform-quota compliance enforced, per host and globally? |
| [RETRY_POLICY.md](RETRY_POLICY.md) | What happens on a transient failure, and how many times is it retried? |
| [ERROR_HANDLING.md](ERROR_HANDLING.md) | How are failures categorized, and what does each category trigger? |
| [CACHE_STRATEGY.md](CACHE_STRATEGY.md) | How does the framework avoid re-fetching what hasn't changed, and resume after a crash? |
| [VERSIONING_POLICY.md](VERSIONING_POLICY.md) | How are connectors, parsers, and content versions tracked over time? |
| [OBSERVABILITY.md](OBSERVABILITY.md) | How is the running system's health and progress actually seen? |
| [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | How is correctness verified, per layer, without hitting live sources on every run? |

---

## 5. What Happens Next (Explicitly Out of Scope Here)

Per the task's own constraint, this document set is architecture only — no connector, no parser, no queue, no storage backend has been built. Implementation is separately-scoped future work, gated by the same Architecture Review discipline this repository already applies before a design becomes something built, per [`KNOWLEDGE_ACQUISITION_ARCHITECTURE.md § 6`](../knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md#6-what-happens-next-explicitly-out-of-scope-here).
