# ADR-0001: Add an AI Retrieval Metadata Layer, Additive to the Frozen Rule Format

**Date:** 2026-07-23
**Status:** Accepted

## Context

[PROJECT_CHARTER.md § Architecture Freeze v1.0](../PROJECT_CHARTER.md#architecture-freeze-v10) declares the Engineering Rule format — plain Markdown, no frontmatter, lean 1–3 sentence sections, no field for evidence or metadata overflow (see [docs/ENGINEERING_RULE_SPECIFICATION.md](../docs/ENGINEERING_RULE_SPECIFICATION.md)) — stable, and states that changing it is "an exceptional event... driven by a genuine structural deficiency surfaced through real usage — never a theoretically cleaner idea arriving on its own."

A real deficiency exists: `AGENTS.md`'s mandatory procedure is "read every rule file in `rules/` in full, in numeric order." At ten rules this is cheap. At the scale this repository is explicitly designed for — [ROADMAP.md](../ROADMAP.md) Stage 1 is open-ended and Phase 2 has no rule-count ceiling — full serial reading does not scale: it burns context linearly with rule count, gives no mechanism to rank which rules actually bear on a given proposal, has no formal way to detect that two rules' Good Patterns conflict for the same proposal, and has no dependency graph telling an agent that understanding one rule requires first understanding another.

Two options were considered:

1. **Redesign the canonical Rule format** (add frontmatter, categories, tags, dependency/conflict fields directly to `rules/*.md`) — rejected. This would touch the frozen artifact directly, contradicts "Prefer improving engineering knowledge over redesigning repository architecture," and reintroduces exactly the section bloat `docs/ENGINEERING_RULE_SPECIFICATION.md §5` explicitly rejects ("Too verbose... any section contains... more than a short paragraph").
2. **Add a new, derived artifact type that indexes the canonical rules without modifying or duplicating them** — adopted. This is the extension path [ENGINEERING_META_MODEL.md § Design Principles: Extensibility](../ENGINEERING_META_MODEL.md#design-principles) already provides for: *"New artifact types may be added to this catalog, but only through the same rigor this document itself was produced under — proposed, reviewed, and recorded as an ADR."*

## Decision

Add two new artifact types to the Meta-Model catalog:

- **Rule Metadata Record (`RM`)** — one machine-authored sidecar file per Engineering Rule, holding exactly the structured, retrieval-oriented fields the canonical Rule does not and should not carry (category, tags, keywords, RFC 2119 requirement extraction, dependency/conflict graph edges, AI retrieval hints). An `RM` record never restates the canonical Rule's prose — every content field is either a pointer into the canonical file or genuinely new structure derived from it. `RM-NNNN` is ID-aligned to its rule (`RM-0001` ↔ `R001`), the same reconciliation already used for `ER-####`.
- **Rule Retrieval Index (`RIX`)** — a single generated build artifact, `rules/index/RULE_INDEX.yaml`, compiled from every `RM` record, that an AI agent queries directly instead of reading every rule file.

Both are documented in full in [docs/ai-retrieval/](../docs/ai-retrieval/) and templated in [templates/RULE_METADATA_TEMPLATE.md](../templates/RULE_METADATA_TEMPLATE.md). [ENGINEERING_META_MODEL.md](../ENGINEERING_META_MODEL.md) is amended additively (new catalog entries, naming-standard rows, folder-mapping rows) — no existing entry, rule, or section in it is edited or removed.

## Consequences

- **Accepted:** the repository now has two representations of rule-adjacent knowledge (canonical prose + derived metadata) that must be kept in sync. [RULE_METADATA_LIFECYCLE.md](../docs/ai-retrieval/RULE_METADATA_LIFECYCLE.md) defines the sync/staleness mechanism that bounds this cost.
- **Accepted:** `RM`/`RIX` are new artifact types an author must learn, on top of the existing 29. This is judged worthwhile because they are almost entirely machine-generated/validated, not hand-authored prose — the marginal authoring burden per rule is small.
- **Preserved:** `rules/*.md` is untouched, byte-for-byte, by this change. The Architecture Freeze holds — nothing about how a Rule is authored, reviewed, or read by a human changes.
- **Preserved:** Single Source of Truth. `RM` records are explicitly non-authoritative derivatives; if an `RM` field and its canonical rule ever disagree, the canonical rule wins and the `RM` record is stale, not the reverse (see [ENGINEERING_META_MODEL.md § Design Principles](../ENGINEERING_META_MODEL.md#design-principles)).
- **Follow-up, not performed here:** `AGENTS.md`'s mandatory procedure still says "read every rule file in full, in numeric order." Once `RIX` is populated and validated against real proposals, updating that procedure to use retrieval-then-expand instead of full serial reads is a natural next step — deliberately left to a separate, explicit decision rather than folded into this one.

## Alternatives Rejected

- **JSON instead of YAML for the metadata format** — rejected; see [RULE_METADATA_SPECIFICATION.md § Metadata Format](../docs/ai-retrieval/RULE_METADATA_SPECIFICATION.md#3-metadata-format) for the full comparison. Summary: JSON supports no comments and produces noisier diffs for a file type that is hand-reviewed even though machine-generated.
- **Embedding retrieval metadata as YAML frontmatter inside the existing `.md` rule files** — rejected; touches the frozen file format directly (same objection as option 1 above), and mixes a machine-generated, frequently-regenerated block with a human-authored, rarely-changed one in the same file.
