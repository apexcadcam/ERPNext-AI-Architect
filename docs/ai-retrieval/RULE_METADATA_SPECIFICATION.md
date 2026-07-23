# RULE METADATA SPECIFICATION

**Status:** Foundational
**Authority:** Subordinate to [PROJECT_CHARTER.md](../../PROJECT_CHARTER.md), [ENGINEERING_META_MODEL.md](../../ENGINEERING_META_MODEL.md), and [docs/ENGINEERING_RULE_SPECIFICATION.md](../ENGINEERING_RULE_SPECIFICATION.md), which remain the authoritative definition of what an Engineering Rule *is*. This document specifies the **Rule Metadata Record (`RM`)** — a new, additive artifact type introduced by [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md) — and the **Rule Retrieval Index (`RIX`)** compiled from it.
**Scope:** Applies to every file in [`rules/metadata/`](../../rules/metadata/) and [`rules/index/`](../../rules/index/). Does not apply to, and never modifies, any file in `rules/` itself.

---

## 1. Purpose

**What is a Rule Metadata Record?** A machine-authored sidecar to exactly one `Engineering Rule` (`rules/RNNN-*.md`), holding the structured, retrieval-oriented facts that rule deliberately does not carry — category, tags, keywords, an RFC 2119 decomposition of its requirement, dependency and conflict graph edges, and hints for semantic and pattern-based search.

**Why it exists:** [docs/ENGINEERING_RULE_SPECIFICATION.md](../ENGINEERING_RULE_SPECIFICATION.md) keeps a Rule lean by design — 1–3 sentence sections, no field for metadata overflow — which is exactly right for a human reading ten rules end to end, and exactly wrong for an AI agent that needs to find the three rules (out of what may eventually be hundreds) relevant to one proposal, rank them, and know which other rules those three depend on. An `RM` record is where that second, machine-shaped need lives, without pulling the first need's document out of shape.

**How it differs from its neighbor:**

| vs. | The difference |
|---|---|
| **Engineering Rule** | The Rule is authored by a human (or an AI agent under human review), changes rarely, and is the sole source of architectural truth — see [ENGINEERING_META_MODEL.md § Design Principles: Single Source of Truth](../../ENGINEERING_META_MODEL.md#design-principles). An `RM` record is derived, machine-generated/validated, changes whenever the schema or the source rule changes, and carries zero independent authority — if it disagrees with its source rule, it is wrong by definition, not a competing opinion. |

---

## 2. Responsibilities

**What belongs inside an `RM` record:** everything [METADATA_SCHEMA.yaml](METADATA_SCHEMA.yaml) declares — category, tags, keywords, intent, problem statement, an RFC 2119 requirement breakdown, pointers (never copies) to the source rule's Good/Bad Pattern blocks, dependency/conflict/replacement graph edges, AI retrieval hints, and the record's own revision history.

**What must never appear inside an `RM` record**, and where it belongs instead:

| Content type | Belongs in `RM`? | Where it belongs instead |
|---|---|---|
| The Rule statement, Rationale, Bad Pattern, or Good Pattern prose, copied or paraphrased | No | `rules/RNNN-*.md` — an `RM` field points at it (`source_anchor`) or restates it in a *deliberately different*, retrieval-oriented shape (`semantic_summary`, `requirements[].statement` as a decomposed clause) — it never reproduces the prose. |
| A new architectural claim the source rule does not already make | No | Nowhere in `RM`. If a real gap is found while authoring a record, that is a signal to revise the *rule* through the normal [Rule Lifecycle](../ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle) — never to smuggle the claim into its metadata. |
| A guessed conflict resolution | No | `conflicts[].resolution` must literally read `"Undecided — surface to a human per AGENTS.md, do not resolve silently"` until a human has actually decided precedence — see [RULE_INDEX_SPEC.md § Resolve Conflicts](RULE_INDEX_SPEC.md#3-resolve-conflicts). |
| An invented external reference | No | `references` is an empty array when no real citation exists (true for every Legacy Rule today) — never filled with a plausible-looking but unverified link. |

This mirrors, one layer down, the same discipline [docs/ENGINEERING_RULE_SPECIFICATION.md § 2](../ENGINEERING_RULE_SPECIFICATION.md#2-responsibilities) applies to Rules themselves: a clean separation between the authoritative statement and everything built to help find it.

---

## 3. Metadata Format

**Decision: YAML**, validated against [METADATA_SCHEMA.yaml](METADATA_SCHEMA.yaml) (a JSON Schema draft 2020-12 document, itself serialized as YAML).

| Format | Verdict | Why |
|---|---|---|
| **YAML** | **Chosen** | Comments are allowed (a generator or reviewer can annotate a field in place), multi-line strings are readable without escaping, nested arrays-of-objects (`requirements`, `dependencies`, `conflicts`) stay legible, and git diffs on YAML are line-oriented and reviewable — important for a file that is machine-generated but human-reviewed before commit. The rest of this repository's tooling (Python/Frappe) has first-class YAML support with no added dependency. |
| **JSON** | Rejected | No comments, and structurally identical content produces noisier diffs (trailing commas, quoting every key) for no retrieval benefit — the schema itself is still expressed as JSON Schema, so nothing about validation is lost by choosing YAML for the instances. |
| **TOML** | Rejected | Poor ergonomics for the deeply nested arrays-of-objects this schema requires (`requirements`, `good_examples`, `dependencies`, `conflicts`, `ai_retrieval`) — TOML's array-of-tables syntax gets substantially harder to read than YAML at this nesting depth. |
| **Hybrid (YAML frontmatter inside the `.md` rule file)** | Rejected | Considered and rejected in [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md) — it touches the frozen canonical Rule file format directly, which this entire layer exists to avoid. |

---

## 4. Record Structure

The canonical, enforceable definition of every field is [METADATA_SCHEMA.yaml](METADATA_SCHEMA.yaml). This section explains the *intent* behind the fields that don't already have an obvious source in the canonical rule.

| Field group | Source of truth | Notes |
|---|---|---|
| `rule_id`, `rule_er_id`, `title`, `source_file`, `status`, `risk_level` | Mirrored from `rules/RNNN-*.md` | Never set independently; regenerated whenever the source changes. |
| `priority` | Deterministic function of `risk_level` | `Critical`→`P0`, `High`→`P1`, `Medium`→`P2`, `Low`→`P3`. Exists purely so a retrieval index can sort numerically without re-deriving the mapping at query time. |
| `category` | New — assigned by the record's author | Exactly one of the fifteen categories in [§5](#5-rule-categories). Chosen to be the primary filing dimension; cross-cutting concerns go in `tags`, not by inventing a second category. |
| `tags`, `keywords` | New | `tags` is a small, controlled, kebab-case facet set for index grouping. `keywords` is free-text lexical search terms/synonyms — the words a human or agent might actually type, including ones that never appear verbatim in the rule's prose. |
| `intent`, `problem_statement` | New, derived | `intent` states the good outcome protected, in different wording from the rule's own Rationale. `problem_statement` is phrased as the situation an agent is *in* when the rule becomes relevant — this is what `trigger_intents` and semantic search actually match against. |
| `requirements` | Extracted from `## Rule` | The rule's prose statement decomposed into discrete RFC 2119-tagged clauses (`MUST`, `MUST_NOT`, `SHOULD`, `SHOULD_NOT`, `MAY`), each independently checkable and independently ID'd (`R0NN-REQ-1`, `R0NN-REQ-2`, ...). This is the field that makes future automated validation (a linter checking a proposal against individual clauses, not full prose) possible. Extraction must be conservative — a clause not clearly present in the source prose is not added. |
| `good_examples`, `bad_examples` | Pointers into `## Good Pattern` / `## Bad Pattern` | Never copies of the code blocks themselves — an anchor plus a one-line machine tag of what the example demonstrates. |
| `anti_patterns`, `exceptions_present`, `related_rules` | Mirrored from `## Related Anti-Patterns`, `## Exceptions`, `## Related Rules` | `exceptions_present` is a boolean fast-check; the actual exception text stays in the rule file. |
| `dependencies` | New | Directed edges: rules that must be loaded alongside this one for correct reasoning — a *subset* of `related_rules` specifically marked "requires understanding," used to build the reasoning chains in [RULE_INDEX_SPEC.md](RULE_INDEX_SPEC.md#4-follow-dependencies). |
| `conflicts` | New | Documented cases where two rules' Good Patterns cannot both be fully satisfied for the same proposal, with either a decided precedence or an explicit `"Undecided"` marker — see [§2](#2-responsibilities). |
| `replacement` | New | Fast-path index of supersession (`supersedes` / `superseded_by`). A full `DEP` (Deprecation Notice) artifact, when one exists, remains the authoritative record — this field just makes the fact queryable without reading one. |
| `references` | New, optional | External documentation links, only when a real one exists. Legitimately empty for every current Legacy Rule. |
| `ai_retrieval` | New | See [RULE_INDEX_SPEC.md § 1–2](RULE_INDEX_SPEC.md#1-find-relevant-rules) for how `semantic_summary`, `embedding_text`, `trigger_intents`, `applicability_signals`, `negative_signals`, and `confidence_weight` are actually used at query time. |
| `workflow_ref` | New, forward-looking | Nullable pointer to a future `DT-####` (Decision Tree) or `SK-####` (Skill). Correctly `null` for every rule today — [ROADMAP.md](../../ROADMAP.md) Stage 2+ has not started. Not a placeholder: `null` is a real, meaningful value here, distinct from "not yet considered." |
| `revision_history` | New | History of the `RM` record itself. The canonical rule's own history is `git log` on `source_file` — this field is never used to duplicate that. |

---

## 5. Rule Categories

Exactly one per record, from a fixed, closed enum (adding a sixteenth category is a schema change, requiring the same rigor as any other change to [METADATA_SCHEMA.yaml](METADATA_SCHEMA.yaml)):

| Category | Scope |
|---|---|
| **Architecture** | Structural decisions about how code, doctypes, and modules are organized and isolated. |
| **Customization** | How ERPNext's own configuration surface (fields, forms, workflows) is used to meet a requirement. |
| **Extension** | Framework-sanctioned extension points (hooks, overrides, whitelisted methods) as opposed to invention from scratch. |
| **Security** | Authentication, authorization boundaries, and data exposure — distinct from the mechanics of Permissions below. |
| **Performance** | Query cost, load behavior, and scaling characteristics. |
| **Database** | Schema, data modeling, and data-shape migration concerns. |
| **Permissions** | Frappe's role/user permission system specifically — who can see or do what. |
| **API** | Whitelisted methods, REST/RPC surface, and integration-facing contracts. |
| **Workflow** | Frappe's Workflow doctype and state-machine-driven processes. |
| **Reports** | Report Builder, Query Reports, and reporting-layer concerns. |
| **Deployment** | Install/migrate/upgrade mechanics, fixtures, patches, environment reproducibility. |
| **Testing** | Testability, test structure, and verification strategy. |
| **Printing** | Print Format and document-rendering concerns. |
| **Integrations** | Third-party system connectivity beyond Frappe's own API surface. |
| **UI/UX** | Desk/portal interface behavior not already covered by Customization. |

See [rules/metadata/](../../rules/metadata/) for how the ten founding rules are actually categorized — every one of R001–R010 has a populated, real `RM` record, not a hypothetical example.

---

## 6. Sync and Validation

An `RM` record is only trustworthy if it is known to still match its source rule. This is the job of `sync_state` (see [RULE_METADATA_LIFECYCLE.md](RULE_METADATA_LIFECYCLE.md)) and, once tooling exists, `source_content_hash`. A record whose `sync_state` is `stale` must still be usable for retrieval (better a slightly stale hit than a missed one) but must be visibly flagged as such in any `RIX` query result — an agent should treat a `stale` result's structured fields (category, requirements) as provisional and re-read the source rule directly before relying on them for a final decision.

---

## 7. Quality Standards

An `RM` record is **complete** when every required field in [METADATA_SCHEMA.yaml](METADATA_SCHEMA.yaml) validates, `requirements` covers every checkable clause in the source rule's `## Rule` section with none invented beyond it, and `conflicts` — even if empty — reflects an actual review against every rule in `related_rules` and `dependencies`, not an unchecked default.

An `RM` record is **rejected** when it fails schema validation, when any field restates rule prose instead of pointing at or restructuring it ([§2](#2-responsibilities)), or when `conflicts[].resolution` states a guessed precedence instead of a decided one or the literal `"Undecided"` marker.
