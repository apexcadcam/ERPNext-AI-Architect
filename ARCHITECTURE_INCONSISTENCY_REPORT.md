# ARCHITECTURE INCONSISTENCY REPORT

**Status:** Review only. No architecture document has been modified. No code has been modified. Nothing in this report has been committed.
**Raised during:** Sprint 2 ("Knowledge Factory") implementation planning, on branch `review/sprint2-knowledge-factory`.
**Subject:** Whether **Validation** runs before or after **Extraction** in the Knowledge Pipeline — the frozen architecture asserts both, in different documents.

---

## 1. Exact Conflicting Documents

| Ref | Document | Asserts |
|---|---|---|
| A | [`docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md`](docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md), § 2 ("The Pipeline, End to End") | Validation runs **before** Extraction. |
| B | [`docs/runtime/PIPELINE_ENGINE.md`](docs/runtime/PIPELINE_ENGINE.md), § 4 ("Existing Pipelines as Pipeline Definitions"), closing paragraph | Extraction runs **before** Validation. |
| C | [`docs/studio/STUDIO_EVENT_MODEL.md`](docs/studio/STUDIO_EVENT_MODEL.md), § 2 ("Event Catalog"), "Knowledge Factory Status" | Extraction runs **before** Validation (agrees with B). |
| D | [`docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md`](docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md), Authority line, and §§ 1 and 5 | Validation's own stated scope only makes sense **after** Extraction (agrees with B/C by implication, contradicts A). |

Document A is the single clearest assertion of "Validation before Extraction." Documents B, C, and D are three independent, separately-authored passages that all assert or imply "Extraction before Validation." This is not one document against one document — it is one document against three.

---

## 2. Exact Quoted Sections

### A — `KNOWLEDGE_ACQUISITION_ARCHITECTURE.md` § 2

```
Deduplication  ──▶  Knowledge Document (KD)                 ─┘
    │
    ▼
Validation                                                  ─┐
    │  [8 gates: schema → dup → version-conflict →           │ KNOWLEDGE_VALIDATION_SPEC.md
    │   source-verify → trust-verify → engineering-review →  │
    │   human-approval → confidence-scoring]                 │
    ▼                                                        ─┘
Knowledge Extraction                                        ─┐
    │  [per source-type: docs, code, issues, PRs, release    │ KNOWLEDGE_EXTRACTION_SPEC.md
    │   notes, forum, marketplace, tutorials, video, talks]  │
    ▼                                                        │
Pattern Extraction                                           │
    │  [2nd pass: recurring shape across ≥2 artifacts]       │
    ▼                                                        ─┘
```

The diagram places `Validation` directly beneath `Knowledge Document (KD)` and directly above `Knowledge Extraction` — an unambiguous top-to-bottom sequence of Deduplication → Validation → Extraction → Pattern Extraction.

### B — `PIPELINE_ENGINE.md` § 4, closing paragraph

> "The task's illustrative example (**Discover → Download → Parse → Normalize → Extract → Validate → Persist → Graph → Embed → Index**) is not itself registered as a Pipeline Definition — it is a *composite* view spanning all five definitions above end to end, exactly the shape [`docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md § 2`](../knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md#2-the-pipeline-end-to-end)'s own diagram already draws across multiple frozen documents."

This sentence explicitly lists `Extract` before `Validate`, while simultaneously citing Document A's diagram as "already draw[ing]" the same shape — the two are cited as equivalent by the document that contains the contradiction.

### C — `STUDIO_EVENT_MODEL.md` § 2, "Knowledge Factory Status"

> "*(Studio-level grouping term for **Extraction → Pattern Extraction → Conflict Resolution → Validation** — no new Runtime module.)*"

Validation is named explicitly last in this ordered list, not first.

### D — `KNOWLEDGE_VALIDATION_SPEC.md`, Authority line and §§ 1, 5

Authority line:

> "**Authority:** Subordinate to [KNOWLEDGE_ACQUISITION_ARCHITECTURE.md](KNOWLEDGE_ACQUISITION_ARCHITECTURE.md). **Gates every artifact produced by [KNOWLEDGE_EXTRACTION_SPEC.md](KNOWLEDGE_EXTRACTION_SPEC.md)** before it may enter the [Knowledge Graph](KNOWLEDGE_GRAPH_SPEC.md)."

§ 1, Schema Validation:

> "**Fails when:** a required envelope field is missing or malformed; `type` is not one of the defined artifact types; `source_references` is empty... **On failure:** rejected outright, logged as **an extraction-pipeline defect** (a schema failure indicates a bug in extraction, not a knowledge-quality problem) — routed to engineering triage..."

§ 5, Trust Verification:

> "**Checks:** does the artifact's originating `Knowledge Source`'s Trust Score... meet the minimum threshold **for this artifact `type`**?"
>
> | Artifact type | Minimum Trust Score to pass |
> |---|---|
> | Knowledge API | 80 |
> | Pattern (official-sourced) | 70 |
> | Best Practice | 50 |
> | Example | 40 |
> | Workflow | 60 |
> | Engineering Rule candidate draft | 80, and independent corroboration from ≥2 distinct sources |

`Knowledge API`, `Pattern`, `Best Practice`, `Example`, `Workflow`, and `Engineering Rule candidate` are not properties of a raw `Knowledge Document` — they are the artifact `type`s [`KNOWLEDGE_EXTRACTION_SPEC.md`](docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md) assigns during Extraction. A `Knowledge Document` has no `type` in this sense prior to Extraction running.

---

## 3. Why They Conflict

Document A's diagram places one `Validation` box between `Knowledge Document (KD)` and `Knowledge Extraction`, in that literal top-to-bottom order — Validation gates the raw, undifferentiated `Knowledge Document` before any content artifact has been pulled out of it.

Documents B, C, and D describe a different subject even though they use the same word "Validation": they describe validation of a **typed content artifact** (`Knowledge API`, `Pattern`, `Best Practice`, etc.) that Extraction produces. Document D's own Trust Verification table is keyed by artifact `type` — a value that does not exist until Extraction assigns it. Document D's Schema Validation stage explicitly attributes its own failures to "a bug in extraction," which presupposes extraction has already run by the time this gate executes. Document B's one-line composite pipeline example and Document C's explicit ordered list both place `Extract` textually before `Validate`.

The conflict is therefore not a matter of interpretation of ambiguous wording — it is two different, textually explicit orderings of the same two named stages, asserted in documents that both claim authority over (or subordination to) the same parent document (`KNOWLEDGE_ACQUISITION_ARCHITECTURE.md`), with the parent document itself being the one holding the outlying position.

---

## 4. Implementation Consequences of Each Interpretation

### Interpretation A — Validation runs before Extraction (per Document A's diagram)

- The `knowledge.validation` Pipeline Definition's input type is a raw `Knowledge Document`, not a typed content artifact.
- Document D's § 1 Schema Validation check ("`type` is not one of the defined artifact types") cannot mean an extraction-produced type, since none exists yet — it would have to be reinterpreted as validating the `Knowledge Document` envelope's own `type` field only, a narrower check than the text describes.
- Document D's § 5 Trust Verification per-artifact-type threshold table (`Knowledge API`: 80, `Pattern`: 70, etc.) cannot be applied as written, because the artifact has no `type` yet — this stage would need a different, not-yet-specified pre-extraction trust check, or the threshold table would need to be deferred to a second, post-extraction validation pass that Document A's diagram does not show.
- Document D's § 2 Duplicate Detection ("generalizing `KNOWLEDGE_PIPELINE.md § 5`'s document-level deduplication **to the artifact level**") would have nothing artifact-level to deduplicate against yet.
- `knowledge.validation` would need to run once, upstream of `knowledge.graph_build`, as a single coarse KD-level gate — matching Document A's diagram shape exactly, but leaving Document D's own artifact-type-keyed content only partially implementable at that point in the pipeline.

### Interpretation B — Extraction runs before Validation (per Documents B, C, D)

- The `knowledge.validation` Pipeline Definition's input type is a typed content artifact (`Knowledge API`, `Pattern`, `Best Practice`, `Example`, `Workflow`, or an `Engineering Rule` candidate draft) produced by `knowledge.graph_build`'s Extraction stage.
- Document D's § 1 and § 5 gates apply exactly as written, with no reinterpretation needed.
- `knowledge.validation` would need to run once **per extracted artifact**, downstream of Extraction (and, per Document C's ordering, downstream of Pattern Extraction and Conflict Resolution as well) — not once per `Knowledge Document`.
- Document A's diagram would be read as a simplified, non-literal summary rather than a literal stage-execution order — meaning the one document that is the designated entry point for the whole pipeline (per its own line, "*read it first*") is the one whose literal reading has to be set aside.

---

## 5. Which Interpretation `SPRINT2_IMPLEMENTATION_PLAN.md` Currently Assumes

`SPRINT2_IMPLEMENTATION_PLAN.md` assumes **Interpretation B** — Extraction (and Pattern Extraction and Conflict Resolution) run before Validation. This is stated in that plan's § 6 ("Internal Architecture") and flagged as an open risk in its § 8 ("Risks").

---

## 6. Why That Assumption Was Chosen

Three independent passages (B, C, D) agree with each other and disagree with Document A; only Document A asserts the opposite order. Document D is additionally the most *specific* document on this exact question — it is the document whose entire subject is what Validation does and to what it applies, whereas Document A's diagram is a summary-level entry point spanning ten subordinate documents in one figure. Document D's own content (a per-artifact-type threshold table, a "bug in extraction" failure attribution) is difficult to satisfy under Interpretation A without silently narrowing what Document D says. Weighing three agreeing, specific passages against one outlying, summary-level diagram is the basis for the plan's working assumption — this is a documented judgment call for planning purposes only, not a claim that Document A is wrong.

---

## 7. Components That Would Change Depending on the Decision

| Component | Under Interpretation A | Under Interpretation B (current plan assumption) |
|---|---|---|
| `knowledge.validation` Pipeline Definition — input type | `Knowledge Document` | Typed content artifact (`Knowledge API`, `Pattern`, `Best Practice`, `Example`, `Workflow`, rule candidate draft) |
| `knowledge.validation` Pipeline Definition — invocation cardinality | Once per `Knowledge Document` | Once per extracted artifact (potentially several per source `Knowledge Document`) |
| Composed pipeline ordering in the `PipelineEngine` | `knowledge.formation` → `knowledge.validation` → `knowledge.graph_build` | `knowledge.formation` → `knowledge.graph_build` (Extraction, Pattern Extraction, Conflict Resolution) → `knowledge.validation` |
| Document D § 1 Schema Validation's "`type` is not one of the defined artifact types" check | Reinterpreted as a KD-envelope-only check | Applies as written, against the extracted artifact's actual type |
| Document D § 5 Trust Verification's per-artifact-type threshold table | Not directly applicable at this point; a separate mechanism would be needed | Applies as written |
| Document D § 2 Duplicate Detection's artifact-level dedup | Not directly applicable at this point | Applies as written |
| `ExtractorModule` / `ValidatorModule` capability wiring and `StageCallable` signatures | Validator's stage callables accept `Knowledge Document` | Validator's stage callables accept `Artifact` |
| Artifact status/lifecycle (`draft`, `pending-conflict-resolution`, etc., per the plan's § 8 note) | Applies to `Knowledge Document`s pre-typing | Applies to typed artifacts post-extraction |
| Event ordering in `STUDIO_EVENT_MODEL.md`'s "Knowledge Factory Status" (`ArtifactCreated`, `ConflictDetected`, `ValidationCompleted`) | `ValidationCompleted` would need to fire before any `ArtifactCreated` for that document | Matches the catalog's own listed order — `ArtifactCreated` before `ValidationCompleted` |
| Test fixtures in `tests/knowledge/` (per the plan's § 10) | Fixture `Knowledge Document`s fed directly to Validator tests | Fixture typed artifacts fed to Validator tests; `Knowledge Document` fixtures feed Extractor tests instead |
| Sprint 2 file structure's `knowledge/pipelines/definitions.py` (per the plan's § 12) | `knowledge.validation` defined and composed ahead of `knowledge.graph_build` | `knowledge.validation` defined and composed after `knowledge.graph_build`'s in-scope stages |

---

## 8. No Recommendation

This report does not recommend which interpretation is correct. Both are defensible readings of currently-frozen text; resolving which one the architecture actually intends is outside the scope of Sprint 2 planning and outside the scope of this report.

---

**Human architecture decision required before implementation.**
