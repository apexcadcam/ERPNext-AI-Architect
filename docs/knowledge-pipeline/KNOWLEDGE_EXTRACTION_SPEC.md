# KNOWLEDGE EXTRACTION SPECIFICATION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). Consumes validated `Knowledge Document`s from [KNOWLEDGE_PIPELINE.md](KNOWLEDGE_PIPELINE.md); produces the content-bearing artifacts defined in [KNOWLEDGE_ARTIFACTS.md](KNOWLEDGE_ARTIFACTS.md).
**Scope:** What, exactly, gets extracted from each of the ten source types the task specifies — and, as important, what is deliberately never extracted from each.

---

## 0. Extraction Discipline

Every extraction step must produce an artifact whose `source_references` ([KNOWLEDGE_ARTIFACTS.md § 1](KNOWLEDGE_ARTIFACTS.md#1-the-common-envelope)) dereferences to the exact span of the source `Knowledge Document` the claim came from — never a paraphrase with no anchor back to specific text. An extraction step that cannot point at the exact source span for a claim has not extracted knowledge; it has generated a claim, which is exactly the "no hallucinated knowledge" failure this specification exists to prevent. This is the same discipline already established for `Rule Metadata Record`s' `source_anchor` fields ([docs/ai-retrieval/METADATA_SCHEMA.yaml](../ai-retrieval/METADATA_SCHEMA.yaml)), generalized to the whole pipeline.

---

## 1. Official Documentation

**Extract:**
- Conceptual definitions and terminology (→ `Knowledge API` when defining a formal interface; otherwise informational context attached to whichever artifact references it)
- Canonical step-by-step procedures (→ `Workflow`)
- Field/parameter specifications, including type, required/optional, default value (→ `Knowledge API`)
- Worked code examples shown inline (→ `Example`, `implements`-linked to the `Knowledge API`/`Pattern` it demonstrates)
- Version-scoped feature descriptions, with the URL version segment stamped per [KNOWLEDGE_PIPELINE.md § 4](KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)
- Explicit warnings/caveats ("this field is deprecated as of vNN") — high-priority, feeds `deprecated_by` edges directly

**Never extract:** marketing/positioning language (present in KS-0012/KS-0013 per the catalog); cross-page navigational text.

---

## 2. Official Source Code

**Extract:**
- DocType JSON schema definitions — every field's name, type, options, constraints (→ `Knowledge API`, highest-confidence source for this artifact type)
- `@frappe.whitelist()` method signatures, including decorator arguments (`allow_guest`, etc.) (→ `Knowledge API`)
- Hook registration patterns in `hooks.py` (`doc_events`, `override_doctype_class`, `override_whitelisted_methods`) (→ `Knowledge API` for the exact hook contract; → `Pattern` when the same hook-usage shape recurs across the codebase, per [§9](#9-pattern-extraction-as-a-distinguished-sub-stage))
- Permission-check logic structure (→ `Pattern`, cross-referenced against [R008](../../rules/R008-native-permission-system-over-custom-checks.md))
- Docstrings and inline comments explaining a non-obvious constraint or workaround — the single highest-value extraction target in source code, because this is exactly the kind of tacit rationale [PROJECT_CHARTER.md](../../PROJECT_CHARTER.md) says otherwise "lives in one engineer's head" (here: one maintainer's head, externalized as a comment) (→ attached as rationale context on the `Knowledge API`/`Pattern` it explains)

**Never extract:** implementation detail with no external-facing contract (a private helper function's internals) as if it were a public `Knowledge API` — internal-only code is context for understanding a `Pattern`, never itself presented as a stable interface.

---

## 3. GitHub Issues

**Extract, and only from issues in a resolved state:**
- The failure description and reproduction steps, from issues **closed with a linked, merged fix PR** (→ `Example`, tagged `verified-fixed`)
- The maintainer's stated root cause, when present in the resolution thread (→ context attached to the linked `Knowledge API`/`Pattern`)
- A workaround explicitly endorsed by a maintainer before the real fix shipped (→ `Pattern`, tagged `interim-workaround`, superseded once the fix's `Knowledge API` delta is extracted from the merged PR)

**Never extract as fact:**
- Claims from **open** or **`wontfix`**-closed issues — these are reports, not confirmed facts; if extracted at all, they are tagged `unconfirmed-report` and excluded from default retrieval confidence, never presented with the same weight as a verified-fixed issue.
- An issue title alone, decontextualized from its resolution.

---

## 4. Merged Pull Requests

**Extract:**
- The diff itself — the ground-truth "what changed" (→ `Knowledge API` delta: old signature `superseded_by` new signature)
- The PR description's stated rationale (→ candidate rationale text for a `Pattern` or, when general and falsifiable enough, an `Engineering Rule` draft candidate per [§2.9 of KNOWLEDGE_ARTIFACTS.md](KNOWLEDGE_ARTIFACTS.md#29-engineering-rule-candidate-not-a-pipeline-native-type))
- Review-thread objections and their resolutions — the single highest-value extraction target in this entire specification for *why* something is done one way and not another, because this is where a maintainer's tacit judgment becomes visible and dated, unlike a retrospective blog post
- Before/after behavior, when the PR description or linked issue makes it explicit

**Never extract:** rationale from an **unmerged or closed-without-merge** PR as if it were adopted guidance — a rejected PR's discussion can be extracted as a documented "considered and rejected" `Knowledge Conflict` entry (valuable — it tells you what *not* to propose), never as an accepted `Pattern`.

---

## 5. Release Notes

**Extract:**
- Version-tagged change summaries (→ feeds `Knowledge Graph` version edges directly)
- **Breaking-change flags specifically** — these trigger [KNOWLEDGE_REFRESH_POLICY.md § 4](KNOWLEDGE_REFRESH_POLICY.md#4-breaking-change-propagation)'s cascading staleness walk the moment they're extracted, before any other processing
- Deprecation announcements (→ `deprecated_by` edge from the old `Knowledge API`/`Pattern` to its replacement, or to nothing if removed outright)

**Never extract:** release-note *prose* as the final word on a substantive technical claim without a pointer to the underlying PR — per [KNOWLEDGE_SOURCE_CATALOG.md `KS-0010`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#ks-0010--github-releases--changelogs)'s documented risk that release-note text is partly LLM-summarized. Extraction must carry the linked PR/issue reference alongside the release-note claim, not instead of it.

---

## 6. Forum Discussions

**Extract, per-post, never per-thread:**
- A question paired with its **accepted answer**, or its **highest-vote, staff-authored answer** where no formal acceptance mechanism applies (→ `Best Practice`, or `Example` for a narrow how-to)
- A staff-authored architectural explanation, whether or not it's the "accepted" answer, tagged with the author's identified staff status per [KS-0019](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#ks-0019--staff-tagged-maintainer-forum-replies) (→ `Pattern`, high confidence)

**Handle explicitly as conflict material, not silently discard:**
- Threads with multiple, mutually-contradicting answers and no clear resolution (→ `Knowledge Conflict`, status `open`, per [KNOWLEDGE_CONFLICT_RESOLUTION.md](KNOWLEDGE_CONFLICT_RESOLUTION.md))

**Never extract:** an unanswered question, or a reply with no corroboration and no staff authorship, as a standalone fact.

---

## 7. Marketplace Apps

**Extract only from apps that have passed the [Long-Tail Vetting Gate](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#13-long-tail-vetting-gate):**
- App manifest metadata: declared framework-version compatibility, category, license (→ `Knowledge API`-adjacent metadata, not a content claim)
- **Structural patterns only** — how the app is organized, how it registers hooks, how it structures its service layer (→ `Pattern`, tagged `third-party-observed`, always lower confidence than the same pattern found in an official `frappe/*` repo)

**Never extract:**
- Business logic or proprietary implementation detail specific to the app's own domain (not this project's concern, and often not meant to be read as general guidance)
- Anything from an app that failed the vetting gate — no exception, regardless of how instructive the code looks; an unvetted source's confidence ceiling is defined in [KNOWLEDGE_VALIDATION_SPEC.md § 5](KNOWLEDGE_VALIDATION_SPEC.md#5-trust-verification) specifically to prevent this.

---

## 8. Tutorials, Videos, and Conference Talks

**Extract:**
- Step sequences presented as a procedure (→ `Workflow`, always tagged lower-confidence than an official-documentation `Workflow` and cross-checked against [KS-0001](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#ks-0001--frappe-unified-documentation-hub)/source before promotion to higher confidence)
- Worked examples demonstrated on-screen or in a transcript (→ `Example`)
- For video/conference content specifically: extraction is transcript-derived text only, **timestamp-anchored** so every claim's `source_references` points at an exact moment in the recording, not "the video" as an undifferentiated whole

**Explicit tagging requirement for conference talks:** every extracted claim is tagged `vision-roadmap` or `technical-deep-dive` at extraction time, per [KNOWLEDGE_SOURCE_CATALOG.md `KS-0024`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#ks-0024--frappeverse--erpnext-conference-talks)'s documented skew toward promotional framing — `vision-roadmap`-tagged content is excluded from default technical retrieval.

**Never extract:** a claim from a video with no available captions/transcript (no auto-generated-transcript fallback, to avoid compounding transcription-error risk with extraction-error risk); a claim whose only evidence is "it was said in the video" without a specific timestamp.

---

## 9. Pattern Extraction as a Distinguished Sub-Stage

Requested separately in the task's OBJECTIVE pipeline (`Knowledge Extraction ↓ Pattern Extraction`), Pattern Extraction is not a different source-reading step — it is a **second pass over already-extracted `Knowledge API`, `Example`, and `Workflow` artifacts**, looking specifically for a solution shape that recurs across **two or more independent artifacts**, per `Pattern`'s existing "when to create" bar ([ENGINEERING_META_MODEL.md entry 8](../../ENGINEERING_META_MODEL.md#8-pattern-pat)). A shape observed exactly once, in exactly one source, is retained as an `Example` and never promoted to `Pattern` on its own — this is what keeps `Pattern` extraction from manufacturing false generality out of a single anecdote, the same discipline `Best Practice`'s "when NOT to create" already states for its own promotion bar.

**Anti-Pattern extraction** runs the identical process against `Knowledge Conflict` entries and `unconfirmed-report`/`interim-workaround`-tagged `Example`s specifically — a recurring *bad* shape, evidenced by recurring problem reports rather than recurring success.
