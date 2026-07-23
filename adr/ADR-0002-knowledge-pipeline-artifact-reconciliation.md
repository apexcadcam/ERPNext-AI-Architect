# ADR-0002: Reconcile the Knowledge Acquisition Pipeline's Artifact Types with the Existing Catalog

**Date:** 2026-07-23
**Status:** Accepted

## Context

The Knowledge Acquisition Pipeline task specified ten artifact types for a large-scale, mostly-automated acquisition/extraction/graph/retrieval system: `KS`, `KD`, `KR`, `KP`, `KA`, `KW`, `KE`, `KC`, `KB`, `KG`.

Cross-checking against [ENGINEERING_META_MODEL.md § Knowledge Artifact Catalog](../ENGINEERING_META_MODEL.md#knowledge-artifact-catalog) (31 entries after [ADR-0001](ADR-0001-ai-retrieval-metadata-layer.md)) found five direct or near-direct collisions:

| Requested | Existing | Collision |
|---|---|---|
| `KS` Knowledge Source | `Knowledge Source (KS)`, entry 24 | Exact match — same concept, same prefix. |
| `KP` Knowledge Pattern | `Pattern (PAT)` / `Anti-Pattern (AP)`, entries 8–9 | Same concept, different prefix. |
| `KB` Knowledge Best Practice | `Best Practice (BP)`, entry 11 | Same concept, different prefix. |
| `KE` Knowledge Example | `Example (EX)`, entry 18 | Same concept, different prefix. |
| `KW` Knowledge Workflow | `Workflow (WF)`, entry 22 | Same concept, different prefix. |
| `KR` Knowledge Rule | **`Engineering Rule (ER)`, entry 6** | Same concept, and the most load-bearing artifact type in the repository — see below. |

The `KR` collision is qualitatively different from the other four. `Engineering Rule` is this repository's declared **source of truth** ([PROJECT_CHARTER.md § Repository Philosophy](../PROJECT_CHARTER.md#repository-philosophy)), reaches `Stable` status only through a mandatory human-gated [Architecture Review](../ENGINEERING_META_MODEL.md#rule-lifecycle), and the Meta-Model's own invariants explicitly forbid silent duplication: *"If two artifacts say the same thing, one must be deprecated in favor of the other"* ([Design Principles: Minimal Duplication](../ENGINEERING_META_MODEL.md#design-principles)). A pipeline-native `KR` type, populated by automated extraction from crawled sources, would let rule-shaped knowledge accumulate outside the one gate this repository relies on to keep an AI agent's behavior actually correct — precisely the failure mode [ROADMAP.md](../ROADMAP.md) names: *"judgment encoded somewhere other than a Rule, invisible and unaudited."*

Three genuinely new concepts were also identified, with no existing equivalent: `KD` (a single acquired/cleaned/normalized unit of content, pre-extraction — distinct from `Reference`, which points at an external document rather than storing an internally-processed copy of one), `KA` (structured API/method/field-signature knowledge — DocType schemas, whitelisted methods, hook signatures — with no prior dedicated type), and `KC` (a detected disagreement between raw source claims, at the pipeline level — distinct from the `conflicts` field already added to `RM` records by ADR-0001, which is rule-to-rule only). `KG` (a graph-index node wrapping any other artifact for relationship traversal) is also new, structurally analogous to `RIX` from ADR-0001 but generalized across every artifact type instead of `Engineering Rule` alone.

## Decision

1. **`KS`, `KP`/`AP`, `KB`, `KE`, `KW` are reused as-is.** The pipeline produces instances of the existing types; no renamed duplicates are created.
2. **No `KR` type is created.** Anything the pipeline extracts that is rule-shaped (a falsifiable, general, checkable architectural claim) is routed as a **candidate** into the existing [Research → Engineering Rule lifecycle](../docs/ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle) — surfaced for human Architecture Review before it can ever reach `Stable`, exactly as any other proposed rule must. The pipeline may accelerate *drafting* a candidate; it may never substitute for the review gate. See [KNOWLEDGE_VALIDATION_SPEC.md § Human Approval Gate](../docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate).
3. **`KD`, `KA`, `KC`, `KG` are added** to the Meta-Model catalog as genuinely new artifact types, documented in [KNOWLEDGE_ARTIFACTS.md](../docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md) and appended additively to [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md) (catalog entries, naming standards, folder mapping) — no existing entry is edited or removed, the same discipline [ADR-0001](ADR-0001-ai-retrieval-metadata-layer.md) established.

## Consequences

- **Preserved:** `Engineering Rule` remains the sole source of truth; the pipeline is architecturally incapable of writing a "rule" the existing mandatory review never saw.
- **Preserved:** vocabulary stays singular — one name per concept across the whole repository, per [Design Principles: Single Source of Truth](../ENGINEERING_META_MODEL.md#design-principles).
- **Accepted:** the pipeline's own documents (`KNOWLEDGE_ARTIFACTS.md` onward) must consistently use `Pattern`/`Anti-Pattern`/`Best Practice`/`Example`/`Workflow`/`Knowledge Source` rather than the task's originally-proposed `KP`/`KB`/`KE`/`KW`/`KS` labels, to avoid reintroducing the same ambiguity this ADR resolves. This is a deliberate, visible departure from the literal task wording, made explicit here rather than silently substituted.
- **Follow-up, not performed here:** the existing `RM`/`RIX` layer (ADR-0001) is scoped to `Engineering Rule` alone. [KNOWLEDGE_GRAPH_SPEC.md](../docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md) and [RETRIEVAL_STRATEGY.md](../docs/knowledge-pipeline/RETRIEVAL_STRATEGY.md) generalize that pattern graph-wide; `RIX` becomes one artifact-type-scoped index feeding into the larger graph, not a competing structure. Reconciling the two into a single generation pipeline in practice is future, separately-scoped implementation work — this ADR and the documents it authorizes are architecture only.
