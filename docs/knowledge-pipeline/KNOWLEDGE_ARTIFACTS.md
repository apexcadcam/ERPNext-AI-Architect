# KNOWLEDGE ARTIFACTS

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [ENGINEERING_META_MODEL.md](../../ENGINEERING_META_MODEL.md) and [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md), which explains why this document uses `Pattern`/`Best Practice`/`Example`/`Workflow`/`Knowledge Source` rather than the `KP`/`KB`/`KE`/`KW`/`KS` labels, and why no `KR` type exists.
**Scope:** Defines the artifact types the [Knowledge Acquisition Pipeline](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md) produces and consumes, and the common schema envelope every one of them shares. This document specifies structure only — no extraction logic, no crawling code, no running system.

---

## 1. The Common Envelope

Every artifact this pipeline produces — regardless of type — carries the same nine fields, per the task's own requirement that every knowledge artifact have `ID, Metadata, Version, Provenance, Confidence, Source References, Tags, Dependencies, Relationships`. A type-specific **Content** payload sits inside this envelope; the envelope itself is what makes every artifact type uniformly traceable, queryable, and auditable regardless of what it actually claims.

| Field | Type | Description |
|---|---|---|
| `id` | string, `PREFIX-NNNN` | Stable, permanent, never reassigned or reused — per [Naming Standards](../../ENGINEERING_META_MODEL.md#naming-standards). |
| `type` | enum | One of the artifact types in [§2](#2-artifact-types). |
| `metadata` | object | `{ extracted_at, extraction_method, extractor_version, artifact_schema_version }` — when and how this envelope was produced, distinct from when the underlying knowledge was true. |
| `version` | object | `{ artifact_version: semver of this record's own structure, applies_to: the ERPNext/Frappe version(s) the claim itself is scoped to }`. These are two different notions of "version" and must never be conflated — see [KNOWLEDGE_REFRESH_POLICY.md § Version Scoping](KNOWLEDGE_REFRESH_POLICY.md#2-version-scoping). |
| `provenance` | ordered list | The full chain from raw acquisition to this artifact: `Knowledge Source → Knowledge Document(s) → this artifact`, each link ID'd. No artifact may exist without a complete, unbroken provenance chain — an artifact whose chain terminates anywhere other than a cataloged `Knowledge Source` is invalid by construction. |
| `confidence` | number, 0.0–1.0 | Composite score from [KNOWLEDGE_VALIDATION_SPEC.md § Confidence Scoring](KNOWLEDGE_VALIDATION_SPEC.md#8-confidence-scoring) — never hand-set independently of that formula. |
| `source_references` | list | Direct pointers (URL + retrieval date + content hash) to every `Knowledge Source`/`Knowledge Document` this artifact's content field was derived from — the anti-hallucination anchor: a claim with no dereferenceable source reference must not exist in the graph. |
| `tags` | list of strings | Kebab-case facets, same discipline as [`RM.tags`](../ai-retrieval/METADATA_SCHEMA.yaml) — for index grouping, not free text. |
| `dependencies` | list of `{ id, relationship: depends_on, reason }` | The subset of `relationships` specifically typed `depends_on` — required context an agent must also load to correctly reason about this artifact. Broken out from `relationships` because dependency expansion ([RETRIEVAL_STRATEGY.md § 4](RETRIEVAL_STRATEGY.md#4-dependency-expansion)) is the single most frequently-queried relationship type. |
| `relationships` | list of `{ id, relationship, note }` | Every typed edge this artifact participates in — see [KNOWLEDGE_GRAPH_SPEC.md](KNOWLEDGE_GRAPH_SPEC.md) for the full relationship vocabulary (`depends_on`, `implements`, `extends`, `replaces`, `conflicts_with`, `related_to`, `deprecated_by`, `supersedes`, `references`). |

**Invariant:** `confidence`, `provenance`, and `source_references` are populated by the pipeline, never by an extraction step asserting them about itself — an artifact cannot self-certify its own trustworthiness, mirroring the existing `RM` layer's rule that a metadata record is non-authoritative over its own source.

---

## 2. Artifact Types

| Type | Status | Reused from | Notes |
|---|---|---|---|
| Knowledge Source | Reused, unchanged | `Knowledge Source (KS)`, Meta-Model entry 24 | Already fully specified and populated — see [knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md). |
| Knowledge Document | **New** | — | [§2.1](#21-knowledge-document) |
| Knowledge API | **New** | — | [§2.2](#22-knowledge-api) |
| Pattern / Anti-Pattern | Reused, unchanged | `Pattern (PAT)` / `Anti-Pattern (AP)`, entries 8–9 | [§2.3](#23-pattern--anti-pattern) |
| Best Practice | Reused, unchanged | `Best Practice (BP)`, entry 11 | [§2.4](#24-best-practice) |
| Example | Reused, unchanged | `Example (EX)`, entry 18 | [§2.5](#25-example) |
| Workflow | Reused, unchanged | `Workflow (WF)`, entry 22 | [§2.6](#26-workflow) |
| Knowledge Conflict | **New** | — | [§2.7](#27-knowledge-conflict) |
| Knowledge Graph Node | **New** | — | [§2.8](#28-knowledge-graph-node) |
| Engineering Rule candidate | Routed, not a new type | `Engineering Rule (ER)`, entry 6 | [§2.9](#29-engineering-rule-candidate-not-a-pipeline-native-type) |

### 2.1 Knowledge Document

**Content payload:** `{ raw_text, cleaned_text, format, language, structural_metadata (headings/sections/code-block boundaries) }`.
**Purpose:** Pipeline staging unit — see [ENGINEERING_META_MODEL.md entry 32](../../ENGINEERING_META_MODEL.md#32-knowledge-document-kd).
**Produced by:** Acquisition + Cleaning + Normalization + Deduplication stages ([KNOWLEDGE_PIPELINE.md §2–5](KNOWLEDGE_PIPELINE.md#2-acquisition-stage-1-detail)).
**Consumed by:** Extraction ([KNOWLEDGE_EXTRACTION_SPEC.md](KNOWLEDGE_EXTRACTION_SPEC.md)), producing every other content-bearing type below.
**`dependencies`/`relationships`:** `references` its `Knowledge Source`; no `depends_on` edges (a `KD` depends on nothing — it is closer to raw material than a claim).

### 2.2 Knowledge API

**Content payload:** `{ interface_kind: doctype-field | whitelisted-method | hook-signature | rest-endpoint, name, signature, parameters, return_shape, doctype_scope }`.
**Purpose:** Formal, checkable interface knowledge — see [ENGINEERING_META_MODEL.md entry 33](../../ENGINEERING_META_MODEL.md#33-knowledge-api-ka).
**Produced by:** Extraction from official source code (highest confidence) or official documentation (lower confidence unless cross-verified against source).
**`dependencies`/`relationships`:** `implements` edges to the `Knowledge Document` chunk defining it; `extends` edges when a `KA` represents an override/subclass of another `KA`; `deprecated_by` when a newer signature supersedes it.

### 2.3 Pattern / Anti-Pattern

**Content payload:** identical to the existing artifact type's definition in [ENGINEERING_META_MODEL.md entries 8–9](../../ENGINEERING_META_MODEL.md#8-pattern-pat) — a named, reusable solution shape (or its named bad mirror).
**Produced by:** Pattern Extraction, a distinguished sub-stage of extraction ([KNOWLEDGE_EXTRACTION_SPEC.md § Pattern Extraction](KNOWLEDGE_EXTRACTION_SPEC.md#9-pattern-extraction-as-a-distinguished-sub-stage)) that specifically looks for a solution shape repeated across ≥2 independent `Knowledge Document`s or `Knowledge API` usages, per the existing type's own "when to create" bar (used successfully more than once).
**`dependencies`/`relationships`:** `references` the `Knowledge API`(s) it's built from; `conflicts_with` a competing `Pattern` when two solution shapes address the same problem incompatibly.

### 2.4 Best Practice

**Content payload:** identical to [ENGINEERING_META_MODEL.md entry 11](../../ENGINEERING_META_MODEL.md#11-best-practice-bp) — a recommended, non-mandatory approach, below `Engineering Rule`'s evidence bar.
**Produced by:** Extraction, when a claim is well-corroborated (multiple independent sources agree) but not yet backed by `Production Incident`-grade evidence — see [ENGINEERING_META_MODEL.md's existing promotion edge](../../ENGINEERING_META_MODEL.md#repository-object-model): `Best Practice → is promoted to → Engineering Rule`, unchanged by this pipeline.
**`dependencies`/`relationships`:** `related_to` other `Best Practice`/`Pattern` entries; may later gain a `supersedes` edge from a promoted `Engineering Rule`.

### 2.5 Example

**Content payload:** identical to [ENGINEERING_META_MODEL.md entry 18](../../ENGINEERING_META_MODEL.md#18-example-ex) — a concrete illustration, explicitly non-authoritative.
**Produced by:** Extraction from Tutorials, official docs' worked examples, or vetted marketplace apps (see [KNOWLEDGE_EXTRACTION_SPEC.md](KNOWLEDGE_EXTRACTION_SPEC.md)).
**`dependencies`/`relationships`:** `implements` the `Pattern`/`Knowledge API` it illustrates.

### 2.6 Workflow

**Content payload:** identical to [ENGINEERING_META_MODEL.md entry 22](../../ENGINEERING_META_MODEL.md#22-workflow-wf) — a multi-step process description.
**Produced by:** Extraction from Tutorials and official docs' procedural sections specifically (step-numbered content), distinguished from `Pattern` (a solution shape) by being sequential/procedural rather than structural.
**`dependencies`/`relationships`:** `depends_on` the `Knowledge API`/`Pattern` each step invokes, in step order.

### 2.7 Knowledge Conflict

**Content payload:** `{ claim_a: artifact reference, claim_b: artifact reference, scope: version/context where both apply, precedence_outcome, status: open | resolved-deterministic | resolved-human | undecided }`.
**Purpose:** Detected pre-rule disagreement — see [ENGINEERING_META_MODEL.md entry 34](../../ENGINEERING_META_MODEL.md#34-knowledge-conflict-kc) and the full resolution design in [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md).
**Produced by:** Validation's version-conflict-detection stage ([KNOWLEDGE_VALIDATION_SPEC.md § 3](KNOWLEDGE_VALIDATION_SPEC.md#3-version-conflict-detection)).
**`dependencies`/`relationships`:** `conflicts_with` linking `claim_a` and `claim_b`; once resolved, the losing claim gains a `deprecated_by` or `superseded_by`-equivalent edge to the winning one, per precedence.

### 2.8 Knowledge Graph Node

**Content payload:** none of its own — `{ wraps: artifact id, edges: [...] }` only. See [ENGINEERING_META_MODEL.md entry 35](../../ENGINEERING_META_MODEL.md#35-knowledge-graph-node-kg) and [KNOWLEDGE_GRAPH_SPEC.md](KNOWLEDGE_GRAPH_SPEC.md).
**Produced by:** Automatically, one per artifact instance, whenever that instance gains its first relationship edge.
**`dependencies`/`relationships`:** *is* the relationships field, materialized as a traversable graph structure rather than a list embedded in the wrapped artifact.

### 2.9 Engineering Rule Candidate (not a pipeline-native type)

Per [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md), extraction never produces a `KR`. When a `Pattern` or `Best Practice` accumulates enough independent corroboration to look rule-shaped (falsifiable, general, checkable — the same bar [docs/ENGINEERING_RULE_SPECIFICATION.md § 5](../ENGINEERING_RULE_SPECIFICATION.md#5-rule-quality-standards) already sets), the pipeline drafts it using the existing [`templates/ENGINEERING_RULE_TEMPLATE.md`](../../templates/ENGINEERING_RULE_TEMPLATE.md), sets `Status: Draft`, and stops — it does not, and structurally cannot, set `Status: Stable` itself. See [KNOWLEDGE_VALIDATION_SPEC.md § 7](KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate).

---

## 3. Schema Versioning

Every envelope's `metadata.artifact_schema_version` is checked against this document's own version at validation time ([KNOWLEDGE_VALIDATION_SPEC.md § 1](KNOWLEDGE_VALIDATION_SPEC.md#1-schema-validation)). A schema change here is itself a change requiring the same additive discipline as [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md) and [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md) established — extend the envelope or add a type, never silently repurpose an existing field's meaning.
