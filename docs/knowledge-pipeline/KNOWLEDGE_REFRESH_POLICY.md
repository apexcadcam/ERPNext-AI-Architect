# KNOWLEDGE REFRESH POLICY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). Generalizes [`knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md § 12`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#12-suggested-refresh-cadence)'s per-*source* cadence table into per-source-*type* policy, and defines what happens to the graph, not just the crawl schedule, when a refresh finds something changed.
**Scope:** Refresh cadence by source type; staleness propagation through the graph; deprecation/retirement; breaking-change propagation.

---

## 1. Refresh Cadence by Source Type

| Cadence | Source types |
|---|---|
| **Continuous / event-driven** (webhook where available, else polled every run) | Official git repositories — source code, issues, merged PRs, commits (per [KNOWLEDGE_PIPELINE.md § 1](KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type)) |
| **Weekly** | Official documentation sites, official forum, engineering blog, app/marketplace directories |
| **Monthly** | Structured training platforms, curated "awesome" lists, Stack Exchange |
| **Per-release** (triggered by a new tag/release on the relevant repository, not by calendar time) | Release notes/changelogs themselves, and every first-party product repository's `Knowledge API` extraction — re-run in full against the new release, not merely polled on a fixed schedule |
| **Quarterly** | Video platform content, implementation-partner blogs (spot-check, not exhaustive re-crawl, per [KNOWLEDGE_SOURCE_CATALOG.md `KS-0025`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#ks-0025--implementation-partner-blogs-generic-category)) |
| **Annual / event-driven** | Conference talks, tied to the conference calendar |
| **On long-tail vetting gate re-check only** | Marketplace/long-tail apps — re-acquired on their own change, but re-*vetted* against [`§13`'s gate](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#13-long-tail-vetting-gate) no more than annually, since vetting status (license, adoption signal) changes slowly relative to code content |

This table is the source-*type* generalization; the catalog's own §12 remains authoritative for any named source's specific cadence where the two differ (e.g., a specific documentation page known to change unusually often may be scheduled more tightly than its type's default) — type-level policy is the default, not a ceiling.

---

## 2. Version Scoping

A refresh never overwrites a version-scoped artifact in place. When re-acquisition of a source finds changed content for what was previously understood as "the v15 behavior," the pipeline does not edit the existing `v15`-scoped artifact — it runs the full pipeline (Acquisition → ... → Validation) against the new content as if it were new, and [KNOWLEDGE_CONFLICT_RESOLUTION.md § 2](KNOWLEDGE_CONFLICT_RESOLUTION.md#2-two-documentation-versions-disagree)'s process decides whether this is a genuine same-version contradiction (rare — usually means the source itself corrected an error) or, far more commonly, evidence that what the source now calls "v15" has itself moved forward and the artifact's version scope needs updating. Refresh is never silent mutation of an existing fact — every change is a new artifact plus a graph edge, exactly as [KNOWLEDGE_GRAPH_SPEC.md § 4](KNOWLEDGE_GRAPH_SPEC.md#4-node-creation-and-update-rules) requires.

---

## 3. Staleness Propagation

When re-acquisition detects a source's content hash has changed (per [KNOWLEDGE_PIPELINE.md § 2](KNOWLEDGE_PIPELINE.md#2-acquisition-stage-1-detail)'s "never re-acquire unchanged content" rule — a changed hash is precisely the trigger), the following cascade runs, generalizing the `sync_state: stale` mechanism [`docs/ai-retrieval/RULE_METADATA_LIFECYCLE.md`](../ai-retrieval/RULE_METADATA_LIFECYCLE.md) already established for `Engineering Rule` metadata specifically:

1. The changed `Knowledge Document` is re-run through Cleaning → Normalization → Deduplication → Extraction → Validation as new content.
2. Every artifact previously extracted from the *old* version of that `KD` is marked `stale` (not deleted — the old artifact remains a valid historical record).
3. Every `Knowledge Graph Node` with an incoming `depends_on`, `implements`, or `extends` edge from a now-stale artifact is annotated `target-stale`, per [KNOWLEDGE_GRAPH_SPEC.md § 4](KNOWLEDGE_GRAPH_SPEC.md#4-node-creation-and-update-rules) — staleness is contagious along dependency edges, not contained to the single artifact that changed, because an agent relying on a dependent artifact needs to know its foundation shifted even if the dependent artifact's own text is unchanged.
4. `stale` artifacts remain retrievable ([RETRIEVAL_STRATEGY.md § 1](RETRIEVAL_STRATEGY.md#1-filtering) does not hard-exclude them) but are ranked below their non-stale equivalents and flagged in any result they appear in — the same "usable but visibly flagged" treatment [`RULE_METADATA_SPECIFICATION.md § 6`](../ai-retrieval/RULE_METADATA_SPECIFICATION.md#6-sync-and-validation) already applies to stale `RM` records.

---

## 4. Breaking-Change Propagation

Triggered specifically by [KNOWLEDGE_EXTRACTION_SPEC.md § 5](KNOWLEDGE_EXTRACTION_SPEC.md#5-release-notes)'s breaking-change extraction from release notes, or by a merged PR whose diff [KNOWLEDGE_EXTRACTION_SPEC.md § 4](KNOWLEDGE_EXTRACTION_SPEC.md#4-merged-pull-requests) tags as a behavior change:

1. The new behavior is extracted and validated as a fresh, version-scoped `Knowledge API`/`Pattern`, per [§2](#2-version-scoping).
2. The prior behavior's artifact gains a `supersedes`-target edge (i.e., the new one `supersedes` the old) and is retained for historical queries, per [KNOWLEDGE_GRAPH_SPEC.md § 3](KNOWLEDGE_GRAPH_SPEC.md#3-relationship-vocabulary).
3. [§3](#3-staleness-propagation)'s dependency-staleness cascade runs from the superseded artifact, exactly as for any other content change.
4. **The rule-specific check:** if any `stale`-cascaded artifact is `implements`-linked to, or was cited as `Evidence` for, a `Stable` `Engineering Rule`'s Good or Bad Pattern, this is escalated directly to human review per [KNOWLEDGE_VALIDATION_SPEC.md § 6](KNOWLEDGE_VALIDATION_SPEC.md#6-engineering-review) — a breaking change that touches the foundation of a `Stable` rule is a signal that the rule itself may need to re-enter Research, per [ENGINEERING_META_MODEL.md's Rule Lifecycle](../../ENGINEERING_META_MODEL.md#rule-lifecycle), never something the pipeline decides on its own.

---

## 5. Deprecation and Retirement

An artifact is deprecated, never deleted, when:

- Its `Knowledge Source` itself is retired (per [`Knowledge Source`'s own lifecycle](../../ENGINEERING_META_MODEL.md#24-knowledge-source-ks): "Retired if the source itself is discontinued") — every artifact whose provenance chain terminates at that source is bulk-marked `deprecated_by: source-retired`, and a single `Deprecation Notice` (`DEP`, the existing artifact type — not a new one, per [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md)'s reuse discipline) is filed covering the whole retired source rather than one per affected artifact.
- A specific artifact is explicitly superseded (per [§4](#4-breaking-change-propagation)) with no further ambiguity.
- Three consecutive refresh cycles ([KNOWLEDGE_PIPELINE.md § 2](KNOWLEDGE_PIPELINE.md#2-acquisition-stage-1-detail)'s source-health flag) fail to re-verify a source is still reachable — the source is flagged `unreachable`, not immediately deprecated (transient outages happen); deprecation follows only after a defined grace period with no successful re-acquisition.

**Retired artifacts remain in the graph permanently**, per this repository's existing Traceability principle applied graph-wide — `Deprecation Notice` points from the retired artifact to its replacement if one exists, exactly as the existing artifact type already specifies, and retired artifacts are excluded from [RETRIEVAL_STRATEGY.md § 1](RETRIEVAL_STRATEGY.md#1-filtering)'s default result set but remain queryable for audit and historical-mode retrieval.
