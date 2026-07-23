# KNOWLEDGE VALIDATION SPECIFICATION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). Gates every artifact produced by [KNOWLEDGE_EXTRACTION_SPEC.md](KNOWLEDGE_EXTRACTION_SPEC.md) before it may enter the [Knowledge Graph](KNOWLEDGE_GRAPH_SPEC.md).
**Scope:** Eight validation stages, run in a fixed order, each a genuine gate — an artifact that fails any stage is retained (never deleted) with a `rejected` status and the specific stage/reason, per this repository's Traceability principle.

---

## 0. Why Order Is Fixed, Not Parallel

Later stages assume earlier ones already passed — Trust Verification ([§5](#5-trust-verification)) is meaningless to run against an artifact that hasn't yet passed Duplicate Detection ([§2](#2-duplicate-detection)), because a duplicate's trust is a property of whichever copy wins deduplication, not of the copy being discarded. The eight stages therefore run strictly in the order below, and an artifact that fails any stage does not proceed to the next one.

---

## 1. Schema Validation

**Checks:** the artifact's envelope and content payload conform to [KNOWLEDGE_ARTIFACTS.md](KNOWLEDGE_ARTIFACTS.md)'s definition for its declared `type`, and `metadata.artifact_schema_version` matches a schema version this validator knows about.
**Fails when:** a required envelope field is missing or malformed; `type` is not one of the defined artifact types; `source_references` is empty (an artifact with no source reference cannot pass this stage under any circumstance — this is the primary structural anti-hallucination check).
**On failure:** rejected outright, logged as an extraction-pipeline defect (a schema failure indicates a bug in extraction, not a knowledge-quality problem) — routed to engineering triage, not to [§7](#7-human-approval-gate).

## 2. Duplicate Detection

**Checks:** semantic and exact-match comparison against every existing artifact of the same `type`, generalizing [KNOWLEDGE_PIPELINE.md § 5](KNOWLEDGE_PIPELINE.md#5-deduplication-stage-4-detail)'s document-level deduplication to the artifact level (two different `Knowledge Document`s can still yield the same `Knowledge API` fact).
**Fails when:** an artifact is an exact or near-exact restatement of an existing, already-validated artifact.
**On failure:** not rejected — merged. The new artifact's `source_references` are appended to the existing artifact's provenance (a second, independent source corroborating the same fact strengthens confidence, per [§8](#8-confidence-scoring)) and no new artifact is created.

## 3. Version Conflict Detection

**Checks:** does this artifact's claim, scoped to `version.applies_to`, contradict an existing validated artifact scoped to the *same* version?
**Fails when:** yes, and the two artifacts are not resolvable by simple version-precedence (different `applies_to` values would mean no real conflict — see [KNOWLEDGE_CONFLICT_RESOLUTION.md § 2](KNOWLEDGE_CONFLICT_RESOLUTION.md#2-two-documentation-versions-disagree)).
**On failure:** a `Knowledge Conflict` artifact is created linking both claims, and **both** the new and existing artifact are held at `pending-conflict-resolution` status — neither proceeds to [§4](#4-source-verification) until [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md) resolves the conflict, deterministically or via human review.

## 4. Source Verification

**Checks:** does every `source_references` entry actually dereference to real, retrievable content, at the claimed source, containing the claimed span? This stage re-fetches (or re-checks a cached copy against) the cited source and confirms the extracted claim is genuinely present there.
**Fails when:** the source is unreachable, the cited span doesn't contain what the artifact claims it contains, or the source has since been edited such that the claim is no longer present.
**On failure:** rejected, routed to engineering triage — this is the second, and most direct, anti-hallucination check: an artifact cannot pass Source Verification by asserting a source reference; the reference must actually check out.

## 5. Trust Verification

**Checks:** does the artifact's originating `Knowledge Source`'s Trust Score (per [KNOWLEDGE_SOURCE_CATALOG.md](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md)) meet the minimum threshold for this artifact `type`?

| Artifact type | Minimum Trust Score to pass |
|---|---|
| Knowledge API | 80 (official code/docs only — no exceptions) |
| Pattern (official-sourced) | 70 |
| Pattern (third-party-observed, per the vetting gate) | 50, and always capped below official-sourced Pattern confidence regardless of corroboration count |
| Best Practice | 50 |
| Example | 40 |
| Workflow | 60 |
| Engineering Rule candidate draft | 80, **and** independent corroboration from ≥2 distinct sources — a single high-trust source is necessary but not sufficient to draft a rule candidate |

**Fails when:** below threshold.
**On failure:** not necessarily rejected — demoted. An artifact below threshold for its extracted `type` is retained at a lower-confidence type where one applies (e.g., a `Best Practice` candidate from a Trust-30 source is retained as a tagged `low-confidence` `Example` instead, never silently dropped, never silently promoted past its actual evidentiary weight).

## 6. Engineering Review

**Checks:** an automated, pattern-based sanity pass — does this artifact silently contradict an existing `Stable` `Engineering Rule`'s Good/Bad Pattern? Does a proposed `Pattern` structurally resemble a Bad Pattern already named in `rules/`?
**Fails when:** yes to either.
**On failure:** **not rejected — escalated.** A candidate that contradicts a `Stable` rule is exactly the case [PROJECT_CHARTER.md § AI First Principles](../../PROJECT_CHARTER.md#ai-first-principles) already governs: *"Refuse silently overriding a rule... surface the conflict explicitly and let a human decide."* Escalated directly to [§7](#7-human-approval-gate) regardless of its confidence score, bypassing the normal risk-tiered routing below.

## 7. Human Approval Gate

**Not every artifact needs a human.** At the scale this pipeline is designed for, requiring human review of every artifact would itself violate [R009 — YAGNI](../../rules/R009-yagni-no-speculative-infrastructure.md)'s standing principle against unjustified process overhead. Human approval is **mandatory** only for:

1. Any **Engineering Rule candidate draft** — routed into the existing [Research → Engineering Rule lifecycle](../ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle)'s Architecture Review step, per [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md). No automated process may set `Status: Stable` on any candidate, ever.
2. Any artifact escalated by [§6](#6-engineering-review) for contradicting a `Stable` rule.
3. Any `Knowledge Conflict` that [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md)'s deterministic precedence rules cannot resolve.
4. Any artifact whose [§8](#8-confidence-scoring) composite score falls in the ambiguous band (0.4–0.6) after all prior stages — too confident to discard outright, not confident enough to auto-approve.

**Everything else** — `Knowledge API` extracted directly from official source with a clean provenance chain, `Example`s from vetted high-trust sources, corroborated `Best Practice`s with no conflict or contradiction detected — proceeds through an **automated approval path**, subject to periodic audit sampling (a random sample of auto-approved artifacts reviewed on a fixed cadence, per [KNOWLEDGE_REFRESH_POLICY.md](KNOWLEDGE_REFRESH_POLICY.md), to catch systemic extraction defects the deterministic gates above didn't catch individually).

## 8. Confidence Scoring

**Formula:** `confidence = source_trust_normalized × extraction_confidence × corroboration_multiplier × recency_factor`, clamped to `[0.0, 1.0]`.

- `source_trust_normalized` — the originating `Knowledge Source`'s Trust Score ÷ 100.
- `extraction_confidence` — how mechanically certain the extraction method was (e.g., a `Knowledge API` parsed directly from a DocType JSON schema: 1.0; a `Workflow` inferred from an unstructured video transcript: 0.6).
- `corroboration_multiplier` — 1.0 for a single source, increasing (capped at 1.3) with each additional *independent* source corroborating the same claim via [§2](#2-duplicate-detection)'s merge path — independence matters: three mirrors of the same original blog post do not multiply confidence three times.
- `recency_factor` — 1.0 for content matching the current framework version; decays for content scoped to an older version still being actively queried (a historical-version query intentionally uses a `recency_factor` of 1.0 for *that* version instead — recency is always relative to the query's target version, never absolute).

This score becomes the artifact's `confidence` field ([KNOWLEDGE_ARTIFACTS.md § 1](KNOWLEDGE_ARTIFACTS.md#1-the-common-envelope)) and is the primary input to [RETRIEVAL_STRATEGY.md § 2](RETRIEVAL_STRATEGY.md#2-ranking)'s ranking formula — never hand-adjusted after computation, only recomputed in full when an input changes.
