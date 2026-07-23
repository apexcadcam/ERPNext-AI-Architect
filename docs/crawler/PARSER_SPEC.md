# PARSER SPECIFICATION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). Governs [`CRAWLER_PIPELINE.md § 6`](CRAWLER_PIPELINE.md#6-parse)'s pluggable implementation.
**Scope:** How raw, normalized text becomes structured content — one parser per content-type, shared across every connector that produces that content-type. No code.

---

## 1. Parsers Are Keyed by Content-Type, Never by Connector

A parser is registered against a **content-type**, not a source — `text/html` has one parser, used by every HTML-producing connector regardless of which of the eight source types produced it. This is what [`CRAWLER_PLUGIN_SYSTEM.md § 3`](CRAWLER_PLUGIN_SYSTEM.md#3-what-a-new-connector-must-provide) means by "only if the source's content-type isn't already covered": a new documentation-site connector for a *tenth* documentation site needs zero new parser work, because `text/html` was solved once, by the first HTML source this framework ever crawled.

## 2. Required Parsers, by Content-Type

| Content-type | Structural output | Notes |
|---|---|---|
| `text/html` | Heading hierarchy, code blocks (with detected/declared language), tables, lists, link targets | Strips script/style/nav — the boundary between this and [`KNOWLEDGE_PIPELINE.md § 3`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#3-cleaning-stage-2-detail)'s Cleaning is: Cleaning removes noise from the byte stream, this parser imposes structure on what remains |
| Markdown (GitHub-flavored, Discourse-flavored) | Same shape as HTML's output — parsers for different Markdown dialects converge on one canonical structural representation, never two different downstream shapes for what is semantically the same document type |
| `application/json` (API responses — Discourse, Stack Exchange, GitHub, YouTube Data API) | Direct field mapping per the connector's declared schema — no heading/code-block inference needed, since the API already returns structure; this parser's job is normalizing *that* structure into the one canonical shape, not discovering structure that isn't there |
| `application/pdf` | Text extraction with page/section boundaries preserved as the nearest available proxy for heading hierarchy | Lowest-confidence structural output of any parser — PDFs frequently have no reliable semantic structure to extract, and this parser must say so explicitly (a low `structural_metadata` completeness flag) rather than fabricate headings that aren't really there |
| Video caption/transcript formats (SRT/VTT) | Timestamp-anchored text segments — directly feeds [`KNOWLEDGE_EXTRACTION_SPEC.md § 8`](../knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md#8-tutorials-videos-and-conference-talks)'s requirement that every video-derived claim anchor to an exact moment | No caption file, no parse — per that same section's "never extract... without an available transcript" rule, enforced here as a hard parser precondition, not a downstream extraction-time check |

## 3. Adding a Ninth Parser

Follows [`CRAWLER_PLUGIN_SYSTEM.md § 2`](CRAWLER_PLUGIN_SYSTEM.md#2-registration-not-modification)'s registration discipline exactly: a new parser registers itself against a content-type it doesn't yet cover, and becomes automatically available to every present and future connector declaring that content-type in [`SOURCE_CONNECTOR_SPEC.md § 1.6`](SOURCE_CONNECTOR_SPEC.md#16-supported-artifact-types) — no connector is ever edited to "pick up" a new parser; the binding is by content-type, resolved at Parse-stage runtime.

## 4. Determinism Requirement

A parser is a **pure function** of its input: identical `normalized_text` in, identical `structural_metadata` out, every time, with no hidden state (no "learns from previous documents," no external network calls mid-parse). This is what makes the framework's "Deterministic" non-functional requirement ([`CRAWLER_ARCHITECTURE.md § 3`](CRAWLER_ARCHITECTURE.md#3-non-functional-requirements-and-where-each-is-addressed)) concrete at this specific layer, and it is what makes [`TESTING_STRATEGY.md § Parser Tests`](TESTING_STRATEGY.md#2-parser-tests)'s golden-file testing approach valid at all — a non-deterministic parser cannot be golden-file tested.

## 5. Failure Mode

A parser that cannot make sense of its input (malformed HTML beyond reasonable recovery, a JSON payload not matching the connector's declared schema) fails explicitly into [`ERROR_HANDLING.md § Parsing`](ERROR_HANDLING.md#5-parsing) — it never emits a best-effort partial structure silently indistinguishable from a fully successful parse. A partial-but-flagged result is acceptable (e.g., "headings extracted, code-block language detection failed") only when the flag itself is part of `structural_metadata`, visible to every downstream consumer.
