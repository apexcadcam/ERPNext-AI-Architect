# KNOWLEDGE CONFLICT RESOLUTION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). Resolves `Knowledge Conflict` artifacts created by [KNOWLEDGE_VALIDATION_SPEC.md § 3](KNOWLEDGE_VALIDATION_SPEC.md#3-version-conflict-detection). Distinct from, and a generalization one layer below, [docs/ai-retrieval/RULE_INDEX_SPEC.md § 3](../ai-retrieval/RULE_INDEX_SPEC.md#3-resolve-conflicts), which resolves conflicts *between two already-Stable Engineering Rules specifically* — this document resolves conflicts among raw, pre-rule claims.
**Scope:** A deterministic precedence hierarchy, and the five specific scenarios the task names.

---

## 1. The Precedence Hierarchy

When two claims scoped to the same version genuinely disagree, precedence is decided by this fixed order — never by confidence score alone, because confidence measures *how sure extraction is*, not *how authoritative the source is*, and the two must not be conflated:

1. **Official source code, current queried version** — the ground truth, per [KNOWLEDGE_SOURCE_CATALOG.md `KS-0003`/`KS-0004`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#ks-0003--frappefrappe-github-repository).
2. **Merged Pull Request, most recent, matching the change in question** — the record of *why* the code is what it is.
3. **Official Documentation, version-matched** — authoritative *description* of the code, one step removed from the code itself.
4. **Official Release Notes/Changelog** — version-precise, but summary-level (see the LLM-summarization risk already flagged for `KS-0010`).
5. **Staff-authored Forum/Community reply, dated after the documentation's last update** — treated as *provisionally* higher than stale docs, never automatically higher than current docs.
6. **Community Forum consensus (accepted answer / high corroboration)**.
7. **Vetted Marketplace/long-tail code**, per the [Long-Tail Vetting Gate](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#13-long-tail-vetting-gate).
8. **Tutorials, individual blogs, conference talks**.
9. **Unvetted community content** — never authoritative alone; can corroborate, never override.

This ordering is the same Trust Score tiering already established in the [Knowledge Source Catalog](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md), restated here as an explicit precedence *procedure* rather than a scoring table — the catalog says how much to trust a source in general; this document says what to do when two trusted sources actually collide.

**When precedence alone cannot resolve** — two sources at the *same* precedence level, genuinely disagreeing, with no version difference — the conflict is **not guessed at**. It is held at `status: undecided` and escalated to [KNOWLEDGE_VALIDATION_SPEC.md § 7](KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate), using the exact same non-negotiable language already established in [RULE_INDEX_SPEC.md § 3](../ai-retrieval/RULE_INDEX_SPEC.md#3-resolve-conflicts): *"Undecided — surface to a human per AGENTS.md, do not resolve silently."*

---

## 2. Two Documentation Versions Disagree

**Not usually a real conflict.** If `KD_a.version.applies_to = v14` and `KD_b.version.applies_to = v15` state genuinely different behavior, this is not a contradiction — it is two version-scoped facts that are both true, each within its own scope. **Resolution:** both claims are retained as independently valid artifacts, linked by a `supersedes` edge (v15's claim `supersedes` v14's, for "current" queries) — never merged into one claim, and never is the older one deleted or demoted below its own version-scope's confidence.
**Becomes a real conflict only when:** the version scoping itself is ambiguous or missing (e.g., an `inferred`-confidence version tag per [KNOWLEDGE_PIPELINE.md § 4](KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)) — in that case, it is treated as same-version-until-proven-otherwise and enters the full conflict process.

---

## 3. Documentation Disagrees with Code

**Resolution:** code wins, always, without exception — precedence level 1 vs. level 3. The documentation claim is marked `superseded_by` the code-derived `Knowledge API`, and — because this specific mismatch means the *official documentation itself* is stale — a `Knowledge Conflict` record is still created and retained (status `resolved-deterministic`), not silently discarded, because a pattern of doc/code mismatches on a given documentation page is itself valuable signal for [KNOWLEDGE_REFRESH_POLICY.md](KNOWLEDGE_REFRESH_POLICY.md) to prioritize re-crawling that page sooner.

---

## 4. Forum Disagrees with Official Docs

**Resolution:** official docs win — **unless** the forum reply is staff-authored (per [`KS-0019`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#ks-0019--staff-tagged-maintainer-forum-replies)) **and** dated after the documentation's last confirmed update. In that specific case, the conflict is **not silently resolved either way** — it is flagged `docs-may-be-stale`, both claims are retained and surfaced together at retrieval time (never just the higher-precedence one hiding the newer staff statement), and routed to human review to confirm before either is treated as fully superseding the other. This is a deliberate departure from pure precedence-by-source-type, because a source-type hierarchy alone cannot distinguish "the forum is wrong" from "the docs haven't caught up yet" — only a human, or a subsequent doc update, can.

---

## 5. Marketplace Implementation Differs from Framework Recommendation

**Resolution:** the framework's own recommended pattern always wins as *the* recommended `Pattern` — this is non-negotiable, precedence level 1–3 vs. level 7. The marketplace implementation is never promoted to compete with it. It is retained, distinctly tagged `third-party-observed` (per [KNOWLEDGE_EXTRACTION_SPEC.md § 7](KNOWLEDGE_EXTRACTION_SPEC.md#7-marketplace-apps)), and surfaced only when explicitly relevant (e.g., "here is one third-party app's approach, differing from the recommended pattern in the following way") — never merged with, and never allowed to dilute the confidence of, the official recommendation.

---

## 6. A Merged PR Changes Previous Behavior

**Resolution:** this is not really a "conflict" in the disagreement sense — it is a **version transition**, handled identically to [§2](#2-two-documentation-versions-disagree): the new PR's resulting `Knowledge API`/`Pattern` is created fresh, version-scoped from the PR's merge point forward; the prior behavior's artifact gains a `superseded_by` edge to the new one and is retained, version-scoped up to the merge point, for historical/audit queries. **The one genuine conflict risk here:** if the PR's stated rationale contradicts a `Stable` `Engineering Rule`'s Good Pattern — this is not a documentation-layer conflict at all, it is a signal that the *rule itself* may need to re-enter Research, per [ENGINEERING_META_MODEL.md's Rule Lifecycle](../../ENGINEERING_META_MODEL.md#rule-lifecycle) ("A rule may re-enter Research from Stable if new evidence contradicts it"). This case is escalated directly to human review, exactly like [KNOWLEDGE_VALIDATION_SPEC.md § 6](KNOWLEDGE_VALIDATION_SPEC.md#6-engineering-review)'s Engineering Review escalation — a pipeline discovering that framework behavior has drifted out from under one of this project's own rules is exactly the kind of finding that must never be resolved automatically.

---

## 7. What This Document Never Does

Per [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md): this document never resolves a conflict by silently promoting a claim to `Engineering Rule` status, and never resolves a conflict touching a `Stable` rule without human review — those two constraints together are what keep "deterministic" from quietly becoming "deterministic, except for the cases that actually matter most."
