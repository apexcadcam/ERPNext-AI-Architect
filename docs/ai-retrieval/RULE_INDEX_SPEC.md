# RULE INDEX SPECIFICATION

**Status:** Foundational
**Authority:** Subordinate to [RULE_METADATA_SPECIFICATION.md](RULE_METADATA_SPECIFICATION.md). Defines the **Rule Retrieval Index (`RIX`)** build artifact and the retrieval strategy an AI agent runs against it.
**Scope:** Applies to [`rules/index/RULE_INDEX.yaml`](../../rules/index/RULE_INDEX.yaml) and to any agent or tool that queries it.

---

## 0. Why this replaces "read every rule file"

[AGENTS.md](../../AGENTS.md)'s current mandatory procedure — read every file in `rules/` in full, in numeric order, before any proposal — is correct and sufficient at ten rules. It stops being sufficient once the rule count grows past what fits comfortably in a single reasoning pass: cost grows linearly with rule count, nothing ranks which rules actually matter to *this* proposal, and there is no mechanism to know that understanding one rule requires first understanding another. This document defines the replacement strategy: **retrieve, rank, expand dependencies, resolve conflicts, then reason** — against a compiled index instead of the raw file set.

This document does not itself change `AGENTS.md`. That is a separate, deliberate decision left for whenever `RIX` has been populated and validated against real proposals (see [ADR-0001 § Consequences](../../adr/ADR-0001-ai-retrieval-metadata-layer.md#consequences)).

---

## 1. Find Relevant Rules

Retrieval runs in two passes, cheapest first:

**Pass A — Deterministic signal matching.** Match the proposal's concrete details (file paths about to be touched, DocType operations, API calls, keywords in the proposal's own description) against every `RM` record's `ai_retrieval.applicability_signals`, discarding any match also present in that record's `ai_retrieval.negative_signals`. This pass is cheap, deterministic, and requires no embedding model — it is the first thing to run, and by itself is often enough for an unambiguous proposal (e.g., a proposal that literally touches a file under `apps/erpnext/` matches R001's signal for "editing a file under a vendor app path" immediately).

**Pass B — Semantic search.** Embed the proposal's description and compare it against every `RM` record's `ai_retrieval.embedding_text` (a deterministic concatenation of `title + semantic_summary + category + tags + keywords`, defined so that re-embedding is reproducible). This pass catches paraphrased or novel-wording proposals Pass A's exact signals miss — e.g., a proposal that says "I want to let each sales agent only see their own deals" without ever saying the words "permission" or "User Permission" should still surface R008 via `trigger_intents`/`semantic_summary` similarity.

Both passes run against every `category` by default; a proposal that is unambiguously scoped to one category (e.g., explicitly about a Print Format) may restrict Pass B to that category's shard first — see [§6](#6-index-format--sharding).

## 2. Rank Them

Candidates from both passes are merged and scored:

```
score = similarity_or_match_strength
      × ai_retrieval.confidence_weight
      × risk_boost(priority)
      × status_factor(status)
```

- **`risk_boost`** — `P0` (Critical) candidates are boosted above `P1`/`P2`/`P3` candidates at equal similarity, because a missed Critical rule is a worse failure than a missed Medium one. Exact multipliers are an implementation detail of the tooling, not fixed by this spec; the ordering guarantee (`P0` never ranks below an equally-similar `P1`+ at the same `status`) is what's normative.
- **`status_factor`** — `Stable` ranks above `Review` ranks above `Draft`; `Deprecated` is excluded from default results entirely (it is retrievable only by an explicit historical query, never surfaced as live guidance).
- A result compiled from a `stale`-marked `RM` record (see [RULE_METADATA_LIFECYCLE.md](RULE_METADATA_LIFECYCLE.md)) is still ranked and returned, but flagged `stale: true` in the result — the consuming agent must treat its structured fields as provisional and read `source_file` directly before finalizing a judgment based on it.

Only the top-ranked candidates actually need their full canonical rule file read; low-ranked candidates can be left as index-only context unless the reasoning chain in [§5](#5-build-reasoning-chains) pulls them in via a dependency edge.

## 3. Resolve Conflicts

When two retrieved rules both apply to the same proposal and their Good Patterns pull in different directions, consult the `conflicts` edge on either `RM` record:

1. If a `conflicts` entry exists between the two rules **with a decided `resolution`**, apply it as documented.
2. If a `conflicts` entry exists but `resolution` literally reads `"Undecided — surface to a human per AGENTS.md, do not resolve silently"`, or if no `conflicts` entry exists at all for a pairing that genuinely appears to contradict for this proposal — **do not guess**. This is the same standing instruction already in [AGENTS.md § Mandatory Procedure, step 3](../../AGENTS.md) and [PROJECT_CHARTER.md § AI First Principles](../../PROJECT_CHARTER.md#ai-first-principles): state the conflict explicitly and let a human decide. The retrieval layer's job is to make a real conflict *findable*, not to make the call itself.
3. Every resolved conflict discovered this way should be written back into both rules' `RM` records (`conflicts[].resolution`) so the same ambiguity is never re-litigated for the next proposal that hits it — this is the mechanism by which the index gets smarter with use without ever touching `rules/*.md` itself.

## 4. Follow Dependencies

A retrieved rule is not "understood" in isolation if its `dependencies` list is non-empty. Before finalizing which rules govern a proposal:

1. For every top-ranked rule, recursively pull in every rule named in its `dependencies` edges — regardless of whether that dependency independently ranked high enough to surface in [§1](#1-find-relevant-rules)–[§2](#2-rank-them) on its own. A dependency is required context, not merely related context.
2. Traversal is **cycle-safe**: if expanding dependencies revisits a rule already in the working set, stop expanding that branch rather than looping. A genuine dependency cycle between two `RM` records is itself a data-quality defect in those records and should be reported, not silently tolerated.
3. The result of this step is the **working rule set** — the full, expanded list of rules a proposal must actually be checked against, as opposed to the smaller list that merely ranked highest by similarity.

## 5. Build Reasoning Chains

The working rule set from [§4](#4-follow-dependencies) is topologically ordered by its `dependencies` edges (a rule that others depend on is checked, and understood, before the rules that depend on it) and presented as an ordered chain, e.g.:

```
Proposal touches: hooks.py doc_events + a new whitelisted Python module

Reasoning chain:
 1. R003 (Low-Code / Configuration Over Code) — checked first: does this need
    custom code at all, or does a Workflow/Client Script already cover it?
 2. R007 (Thin Hooks, Centralized Service Layer) — depends on R003's outcome:
    given custom code is justified, is the hook itself thin, with logic in a
    testable service layer?
 3. R009 (YAGNI) — checked alongside: is the proposed service-layer
    abstraction justified by a measured need, or speculative?
```

This ordered chain — not a flat, unordered list of "relevant rules" — is what an agent should actually reason against and, per [PROJECT_CHARTER.md § AI First Principles](../../PROJECT_CHARTER.md#ai-first-principles), surface in its own output before generating code: the chain itself is the auditable evidence that retrieval, not vibes, produced the agent's conclusion.

## 6. Index Format & Sharding

`rules/index/RULE_INDEX.yaml` is compiled from every `rules/metadata/*.rm.yaml`, never hand-edited:

```yaml
schema_version: "1.0.0"
generated_at: "<ISO-8601 timestamp>"
generated_from:
  rule_count: <int>
  metadata_records: ["RM-0001", "RM-0002", ...]
by_category:
  Architecture: ["R001", "R002", "R007", "R009", "R010"]
  Deployment: ["R004", "R005", "R006"]
  Permissions: ["R008"]
  Customization: ["R003"]
  # ... every populated category; an absent key means zero rules in it, not an error
by_tag:
  core-isolation: ["R001"]
  # ... one entry per tag observed across all RM records
dependency_graph:
  # rule_id -> [rule_ids it depends on], directed, per every RM.dependencies
  R007: ["R003"]
conflict_graph:
  # unordered pairs with at least one documented conflicts[] entry
  []
entries:
  # one compact projection per rule, enough for Pass A/B without opening
  # the full RM record unless the rule ranks high enough to need it
  - rule_id: "R001"
    status: Stable
    priority: P0
    category: Architecture
    tags: ["core-isolation", "upgrade-safety"]
    embedding_text: "..."
    applicability_signals: ["..."]
    sync_state: synced
```

**Scaling to hundreds of rules.** At ten rules, one file is trivial to load whole. This format is designed so that at scale the same structure splits without changing its shape: `by_category` becomes a manifest of pointers to `rules/index/by-category/<Category>.yaml` shards (one per category, each holding only that category's `entries`), and `entries` in the root file is dropped in favor of the shard files — a retrieval agent loads the root manifest plus only the shard(s) implicated by Pass A, never the full rule set. This repository is small enough today that sharding is documented behavior for a future regeneration, not something implemented in [rules/index/RULE_INDEX.yaml](../../rules/index/RULE_INDEX.yaml) as it stands — the single-file form currently in the repository is the correct, current-scale output, not a placeholder for the sharded form.

**Regeneration.** The index is rebuilt whenever any `RM` record changes. Until a generator script exists, regeneration is manual: re-derive every `by_*` grouping and `entries` projection directly from the current `rules/metadata/*.rm.yaml` files, in rule-number order, and bump `generated_at`.
