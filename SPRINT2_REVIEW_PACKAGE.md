# SPRINT 2 REVIEW PACKAGE — Knowledge Factory

**Branch:** `review/sprint2-knowledge-factory`
**Base:** `main` @ `v0.1.0-runtime-bootstrap` (`a251cb1`), plus `docs(architecture): align knowledge factory stage ordering` (`786ab6b`)
**Status:** Implementation frozen. This document is a complete, self-contained review package — no external context should be required to review Sprint 2 from this file alone.
**Commits under review:** `95e1572`, `a5f7625`, `9082736`, `e5d3cfc`, `e387dc1`, `8848032` (six commits, in that order)
**Test result at freeze:** 155 passed (82 Sprint 1 + 73 Sprint 2), `mypy --strict` clean on `knowledge/`, `plugins/`, `tests/knowledge/`, `ruff check`/`ruff format --check` clean on the same scope.

---

## 1. Repository Tree (Sprint 2 Additions Only)

```
knowledge/
├── __init__.py
├── artifacts/
│   ├── __init__.py
│   ├── envelope.py
│   ├── document.py
│   ├── api.py
│   ├── pattern.py
│   ├── best_practice.py
│   ├── example.py
│   ├── workflow.py
│   └── conflict.py
├── conflict/
│   ├── __init__.py
│   ├── resolution.py
│   ├── providers.py
│   ├── tags.py
│   └── stage.py
├── validation/
│   ├── __init__.py
│   ├── gates.py
│   ├── module.py
│   ├── approval.py
│   ├── confidence.py
│   ├── state.py
│   └── providers.py
├── extraction/
│   ├── __init__.py
│   ├── module.py
│   ├── stage.py
│   ├── rules.py
│   ├── pattern_extraction.py
│   └── ids.py
└── pipelines/
    ├── __init__.py
    └── definitions.py

plugins/
├── __init__.py
├── extractor/
│   ├── __init__.py
│   ├── module.yaml
│   └── module.py
└── validator/
    ├── __init__.py
    ├── module.yaml
    └── module.py

tests/knowledge/
├── __init__.py
├── conftest.py
├── test_artifacts.py
├── test_conflict_resolution.py
├── test_validation_gates.py
├── test_approval_gate.py
├── test_extraction.py
├── test_pattern_extraction.py
├── test_pipeline_integration.py
└── test_event_publication.py
```

**Modified (not added):** `pyproject.toml` — added `"knowledge"` and `"plugins"` to `[tool.hatch.build.targets.wheel].packages`. No other line changed. No `runtime/` file touched by any commit in this Sprint.

48 files added/modified in total, ~4,050 lines.

---

## 2. Every Added and Modified File

### `knowledge/__init__.py`
**Purpose:** Package docstring anchoring the Knowledge Factory to `docs/studio/STUDIO_EVENT_MODEL.md` §2's term.
**Public API:** None (docstring only).
**Dependencies:** None.

### `knowledge/artifacts/envelope.py`
**Purpose:** The common artifact envelope (`KNOWLEDGE_ARTIFACTS.md` §1) and its supporting types.
**Public API:** `ArtifactType` (enum: 8 members), `ARTIFACT_ID_PREFIXES` (dict), `ArtifactStatus` (enum: 6 members — `draft`/`validated`/`rejected`/`pending-conflict-resolution`/`pending-human-approval`/`superseded`), `ArtifactMetadata`, `ArtifactVersionInfo`, `ProvenanceLink`, `SourceReference`, `RelationshipType` (enum: 9 members), `RelationshipEdge`, `DependencyEdge`, `ArtifactEnvelope` (frozen pydantic `BaseModel`, includes a `model_validator` enforcing `id` prefix matches `type`).
**Dependencies:** `pydantic` only.

### `knowledge/artifacts/document.py`
**Purpose:** The `Knowledge Document` type (`KNOWLEDGE_ARTIFACTS.md` §2.1) — Extraction's input.
**Public API:** `KnowledgeDocumentContent` (`raw_text`, `cleaned_text`, `format`, `language`, `structural_metadata: dict[str, Any]`), `KnowledgeDocument(ArtifactEnvelope)`.
**Dependencies:** `knowledge.artifacts.envelope`.

### `knowledge/artifacts/api.py`
**Purpose:** The `Knowledge API` type (§2.2).
**Public API:** `KnowledgeAPIContent` (`interface_kind: Literal["doctype-field","whitelisted-method","hook-signature","rest-endpoint"]`, `name`, `signature`, `parameters`, `return_shape`, `doctype_scope`), `KnowledgeAPI(ArtifactEnvelope)`.
**Dependencies:** `knowledge.artifacts.envelope`.

### `knowledge/artifacts/pattern.py`
**Purpose:** The `Pattern`/`Anti-Pattern` types (§2.3).
**Public API:** `PatternContent` (`title`, `problem`, `solution_shape`, `third_party_observed`), `Pattern(ArtifactEnvelope)`, `AntiPattern(ArtifactEnvelope)` — both share `PatternContent`.
**Dependencies:** `knowledge.artifacts.envelope`.

### `knowledge/artifacts/best_practice.py`
**Purpose:** The `Best Practice` type (§2.4).
**Public API:** `BestPracticeContent` (`title`, `recommendation`, `scope`), `BestPractice(ArtifactEnvelope)`.
**Dependencies:** `knowledge.artifacts.envelope`.

### `knowledge/artifacts/example.py`
**Purpose:** The `Example` type (§2.5).
**Public API:** `ExampleContent` (`title`, `demonstrates`, `code_or_steps`), `Example(ArtifactEnvelope)`.
**Dependencies:** `knowledge.artifacts.envelope`.

### `knowledge/artifacts/workflow.py`
**Purpose:** The `Workflow` type (§2.6).
**Public API:** `WorkflowStep` (`order`, `description`, `invokes`), `WorkflowContent` (`title`, `steps`), `Workflow(ArtifactEnvelope)`.
**Dependencies:** `knowledge.artifacts.envelope`.

### `knowledge/artifacts/conflict.py`
**Purpose:** The `Knowledge Conflict` type (§2.7).
**Public API:** `KnowledgeConflictStatus` (enum: `open`/`resolved-deterministic`/`resolved-human`/`undecided`), `KnowledgeConflictContent` (`claim_a_id`, `claim_b_id`, `scope`, `precedence_outcome`, `conflict_status`), `KnowledgeConflict(ArtifactEnvelope)`.
**Dependencies:** `knowledge.artifacts.envelope`.

### `knowledge/artifacts/__init__.py`
**Purpose:** Public package surface; defines the `ContentArtifact` union.
**Public API:** Re-exports everything above, plus `ContentArtifact = KnowledgeAPI | Pattern | AntiPattern | BestPractice | Example | Workflow`.
**Dependencies:** All sibling modules in `knowledge/artifacts/`.

### `knowledge/conflict/resolution.py`
**Purpose:** The pure precedence-resolution algorithm (`KNOWLEDGE_CONFLICT_RESOLUTION.md`).
**Public API:** `PrecedenceTier` (`IntEnum`, 9 members), `ConflictClaim`, `ConflictCase`, `ConflictOutcomeKind` (enum, 5 members), `ConflictResolution`, `resolve_conflict(case: ConflictCase) -> ConflictResolution`.
**Dependencies:** `pydantic`, stdlib `enum`/`re`.

### `knowledge/conflict/tags.py`
**Purpose:** Shared string constants for tag-facet fields the frozen envelope has no dedicated field for.
**Public API:** `TAG_STAFF_AUTHORED`, `TAG_AFTER_DOCS_UPDATE`, `TAG_CONTRADICTS_STABLE_RULE`.
**Dependencies:** None.

### `knowledge/conflict/providers.py`
**Purpose:** The `PrecedenceProvider` seam and the artifact→`ConflictClaim` conversion helper.
**Public API:** `PRECEDENCE_PROVIDER_CAPABILITY` (`"knowledge.providers.precedence"`), `PrecedenceProvider` (`Protocol`, one method: `precedence_tier(artifact) -> PrecedenceTier`), `to_conflict_claim(artifact, precedence_provider) -> ConflictClaim`.
**Dependencies:** `knowledge.artifacts`, `knowledge.conflict.resolution`, `knowledge.conflict.tags`.

### `knowledge/conflict/stage.py`
**Purpose:** Two Pipeline Engine stage adapters over `resolve_conflict`.
**Public API:** `resolve_conflict_stage(case, context) -> (ConflictResolution, StageOutcome)`, `resolve_conflicts_in_batch(items, context, *, precedence_provider) -> (list[ContentArtifact | KnowledgeConflict], StageOutcome)`.
**Dependencies:** `knowledge.artifacts`, `knowledge.conflict.providers`, `knowledge.conflict.resolution`, `runtime.pipeline.engine`.

### `knowledge/conflict/__init__.py`
**Purpose:** Public package surface for conflict resolution.
**Public API:** Re-exports `TAG_AFTER_DOCS_UPDATE`, `TAG_CONTRADICTS_STABLE_RULE`, `TAG_STAFF_AUTHORED`, `ConflictCase`, `ConflictClaim`, `ConflictOutcomeKind`, `ConflictResolution`, `PrecedenceProvider`, `PrecedenceTier`, `resolve_conflict`, `resolve_conflict_stage`, `resolve_conflicts_in_batch`, `to_conflict_claim`.
**Dependencies:** All sibling modules in `knowledge/conflict/`.

### `knowledge/validation/gates.py`
**Purpose:** All eight Validation gates (`KNOWLEDGE_VALIDATION_SPEC.md` §§1-8).
**Public API:** `schema_validation`, `duplicate_detection`, `version_conflict_detection`, `source_verification`, `trust_verification`, `engineering_review`, `human_approval_gate`, `confidence_scoring` — each `(artifact, PipelineContext, ...) -> (artifact, StageOutcome)`. Also `KNOWN_ARTIFACT_SCHEMA_VERSIONS`, `TRUST_THRESHOLDS`, `THIRD_PARTY_PATTERN_TRUST_THRESHOLD`, `TAG_LOW_CONFIDENCE`.
**Dependencies:** `knowledge.artifacts`, `knowledge.conflict`, `knowledge.conflict.providers`, `knowledge.validation.approval`, `knowledge.validation.confidence`, `knowledge.validation.providers`, `knowledge.validation.state`, `runtime.events.bus`, `runtime.pipeline.engine`.

### `knowledge/validation/state.py`
**Purpose:** In-memory indices Duplicate Detection and Version Conflict Detection need.
**Public API:** `content_hash(artifact) -> str`, `KnowledgeStore` (`find_exact_duplicate`, `same_type_same_version`, `remember`).
**Dependencies:** `knowledge.artifacts`, stdlib `hashlib`.

### `knowledge/validation/confidence.py`
**Purpose:** The shared §8 confidence formula, used by both gate 7 (preview) and gate 8 (final).
**Public API:** `extraction_confidence(artifact) -> float`, `corroboration_multiplier(artifact) -> float`, `compute_confidence(trust_score, extraction_confidence_value, corroboration_multiplier_value, recency_factor=1.0) -> float`, `compute_confidence_for_artifact(artifact, trust_score_provider) -> float`.
**Dependencies:** `knowledge.artifacts`, `knowledge.validation.providers`.

### `knowledge/validation/approval.py`
**Purpose:** The Human Approval Gate's pending queue and its resolution entrypoint.
**Public API:** `ApprovalDecision` (enum: `approved`/`rejected`), `PendingApprovalStore` (`record`, `get`, `pending_ids`, `resolve`).
**Dependencies:** `knowledge.artifacts`, `knowledge.validation.confidence`, `knowledge.validation.providers`, `runtime.events.bus`.

### `knowledge/validation/providers.py`
**Purpose:** `SourceVerifier`/`TrustScoreProvider` seams (Source Verification, Trust Verification).
**Public API:** `SourceVerifier` (`Protocol`: `verify(artifact) -> bool`), `TrustScoreProvider` (`Protocol`: `trust_score(artifact) -> int`).
**Dependencies:** `knowledge.artifacts`.

### `knowledge/validation/module.py`
**Purpose:** `ValidatorModule` — wires the eight gates into the Container as capabilities.
**Public API:** `ValidatorModule(Module)` (class attributes `SOURCE_VERIFIER_CAPABILITY`, `TRUST_SCORE_PROVIDER_CAPABILITY`, `PRECEDENCE_PROVIDER_CAPABILITY`; public attribute `pending_approvals: PendingApprovalStore | None`); `EVENT_BUS_CAPABILITY`, `CAPABILITY_SCHEMA`, `CAPABILITY_DUPLICATE`, `CAPABILITY_VERSION_CONFLICT`, `CAPABILITY_SOURCE_VERIFY`, `CAPABILITY_TRUST_VERIFY`, `CAPABILITY_ENGINEERING_REVIEW`, `CAPABILITY_HUMAN_APPROVAL`, `CAPABILITY_CONFIDENCE_SCORE`.
**Dependencies:** `knowledge.conflict.providers`, `knowledge.validation.{gates,approval,providers,state}`, `runtime.container.di`, `runtime.modules.base`, `runtime.modules.manifest`.

### `knowledge/validation/__init__.py`
**Purpose:** Public package surface for the Validator.
**Public API:** Re-exports `ApprovalDecision`, `KnowledgeStore`, `PendingApprovalStore`, `PrecedenceProvider`, `SourceVerifier`, `TrustScoreProvider`, `ValidatorModule`.
**Dependencies:** All sibling modules plus `knowledge.conflict.providers`.

### `knowledge/extraction/ids.py`
**Purpose:** Sequential, correctly-prefixed ID issuance for produced artifacts.
**Public API:** `IdAllocator` (`next_id(artifact_type) -> str`).
**Dependencies:** `knowledge.artifacts`.

### `knowledge/extraction/rules.py`
**Purpose:** Extraction rules for Official Documentation (§1) and Official Source Code (§2).
**Public API:** `extract_from_official_documentation(document, *, id_allocator) -> list[ContentArtifact]`, `extract_from_official_source_code(document, *, id_allocator) -> list[ContentArtifact]`.
**Dependencies:** `knowledge.artifacts`, `knowledge.extraction.ids`.

### `knowledge/extraction/pattern_extraction.py`
**Purpose:** The Pattern Extraction second pass (§9).
**Public API:** `PATTERN_CANDIDATE_TAG_PREFIX`, `ANTI_PATTERN_CANDIDATE_TAG_PREFIX`, `extract_patterns(artifacts, context, *, id_allocator, event_bus=None) -> (list[ContentArtifact], StageOutcome)`.
**Dependencies:** `knowledge.artifacts`, `knowledge.extraction.ids`, `runtime.events.bus`, `runtime.pipeline.engine`.

### `knowledge/extraction/stage.py`
**Purpose:** The `knowledge.extract` stage — dispatches by `metadata.extraction_method`.
**Public API:** `extract(document, context, *, id_allocator, event_bus=None) -> (list[ContentArtifact], StageOutcome)`.
**Dependencies:** `knowledge.artifacts`, `knowledge.extraction.{ids,rules}`, `runtime.events.bus`, `runtime.pipeline.engine`.

### `knowledge/extraction/module.py`
**Purpose:** `ExtractorModule` — wires Extraction, Pattern Extraction, and batch Conflict Resolution into the Container.
**Public API:** `ExtractorModule(Module)` (class attribute `PRECEDENCE_PROVIDER_CAPABILITY`); `EVENT_BUS_CAPABILITY`, `CAPABILITY_EXTRACT`, `CAPABILITY_EXTRACT_PATTERNS`, `CAPABILITY_RESOLVE_CONFLICTS_BATCH`.
**Dependencies:** `knowledge.conflict.providers`, `knowledge.conflict.stage`, `knowledge.extraction.{ids,pattern_extraction,stage}`, `runtime.container.di`, `runtime.modules.base`.

### `knowledge/extraction/__init__.py`
**Purpose:** Public package surface for the Extractor.
**Public API:** Re-exports `ANTI_PATTERN_CANDIDATE_TAG_PREFIX`, `PATTERN_CANDIDATE_TAG_PREFIX`, `ExtractorModule`, `IdAllocator`, `extract`, `extract_patterns`.
**Dependencies:** All sibling modules.

### `knowledge/pipelines/definitions.py`
**Purpose:** The two `PipelineDefinition`s Sprint 2 registers.
**Public API:** `KNOWLEDGE_VALIDATION_PIPELINE`, `KNOWLEDGE_GRAPH_BUILD_PIPELINE`, `register_knowledge_pipelines(engine: PipelineEngine) -> None`.
**Dependencies:** `knowledge.extraction.module`, `knowledge.validation.module`, `runtime.pipeline.engine`.

### `knowledge/pipelines/__init__.py`
**Purpose:** Public package surface.
**Public API:** Re-exports `KNOWLEDGE_GRAPH_BUILD_PIPELINE`, `KNOWLEDGE_VALIDATION_PIPELINE`, `register_knowledge_pipelines`.
**Dependencies:** `knowledge.pipelines.definitions`.

### `plugins/extractor/module.yaml`
**Purpose:** Discoverable manifest for the real Extractor plugin.
**Public API:** N/A (data file). `capabilities_provided`: `knowledge.extract`, `knowledge.extract_patterns`, `knowledge.resolve_conflicts_batch`. `capabilities_required`: `[]`. `events_published`: `ArtifactCreated`.
**Dependencies:** N/A.

### `plugins/extractor/module.py`
**Purpose:** Thin `PluginRegistry` entry point.
**Public API:** `create(manifest: ModuleManifest) -> ExtractorModule`.
**Dependencies:** `knowledge.extraction`, `runtime.modules.manifest`.

### `plugins/validator/module.yaml`
**Purpose:** Discoverable manifest for the real Validator plugin.
**Public API:** N/A (data file). `capabilities_provided`: the eight `knowledge.validate.*` names. `capabilities_required`: `[]`. `events_published`: `ConflictDetected`, `ValidationCompleted`, `HumanApprovalRequested`, `HumanApprovalResolved`.
**Dependencies:** N/A.

### `plugins/validator/module.py`
**Purpose:** Thin `PluginRegistry` entry point.
**Public API:** `create(manifest: ModuleManifest) -> ValidatorModule`.
**Dependencies:** `knowledge.validation`, `runtime.modules.manifest`.

### `plugins/__init__.py`, `plugins/extractor/__init__.py`, `plugins/validator/__init__.py`
**Purpose:** Empty markers making `plugins/` a real Python package, purely so `mypy` can check `plugins/extractor/module.py` and `plugins/validator/module.py` together without a "Duplicate module named 'module'" collision. Has no effect on `PluginRegistry.discover()`/`instantiate()`, which loads by explicit file path via `importlib`, indifferent to `__init__.py` presence.
**Public API:** None.
**Dependencies:** None.

### `tests/knowledge/*`
See §13 for full per-file detail.

### `pyproject.toml` (modified)
**Change:** `[tool.hatch.build.targets.wheel].packages` extended from `["runtime", "knowledge"]` to `["runtime", "knowledge", "plugins"]` (the `"knowledge"` entry was added in the first Sprint 2 commit; `"plugins"` in the last). Packaging only — no dependency, tool config, or build-system change.

---

## 3. Knowledge Factory Architecture Walkthrough

The Knowledge Factory is the Studio-level grouping term `docs/studio/STUDIO_EVENT_MODEL.md` §2 defines as *"Extraction → Pattern Extraction → Conflict Resolution → Validation — no new Runtime module."* Sprint 2 implements exactly that shape as two Pipeline Definitions running on Sprint 1's unmodified `PipelineEngine`:

```
                    ┌─────────────────────────────────────────────┐
                    │         knowledge.graph_build                │
                    │                                               │
  KnowledgeDocument │  ┌───────────┐   ┌───────────────────┐  ┌───────────────────┐ │  list[ContentArtifact]
 ──────────────────►│  │ Extraction │──►│ Pattern Extraction │──►│ Conflict Resolution│ │──────────────────►
                    │  └───────────┘   └───────────────────┘  └───────────────────┘ │
                    └─────────────────────────────────────────────┘
                                                                          │
                                                                          │ one artifact
                                                                          ▼
                    ┌─────────────────────────────────────────────────────────────────────────────────┐
                    │                          knowledge.validation                                     │
                    │                                                                                    │
 ContentArtifact    │ ┌────────┐ ┌───────────┐ ┌────────────┐ ┌────────┐ ┌───────┐ ┌────────────┐ ┌──────────┐ ┌────────────┐│  ContentArtifact
────────────────────►│ │ Schema │►│ Duplicate │►│  Version   │►│ Source │►│ Trust │►│Engineering │►│  Human   │►│ Confidence ││───────────────►
                    │ │Validate│ │  Detect   │ │  Conflict  │ │ Verify │ │Verify │ │  Review    │ │ Approval │ │  Scoring   ││  (validated/
                    │ └────────┘ └───────────┘ └────────────┘ └────────┘ └───────┘ └────────────┘ └──────────┘ └────────────┘│   rejected/
                    └─────────────────────────────────────────────────────────────────────────────────┘   pending)
```

**What each layer owns:**

- **`knowledge/artifacts/`** — has no behavior. It is the shared vocabulary every other package speaks: the common envelope plus one Pydantic model per content-bearing type.
- **`knowledge/conflict/`** — has no lifecycle (not a `runtime.modules.base.Module`). It is a stateless library two different callers invoke: the Validator's own Version Conflict Detection gate (one `ConflictCase` at a time) and the graph_build Pipeline's Conflict Resolution stage (a whole batch at once).
- **`knowledge/extraction/`** — `ExtractorModule`, a real `Module`. Owns Extraction, Pattern Extraction, *and* (Sprint 2 decision, see §15) the batch Conflict Resolution stage.
- **`knowledge/validation/`** — `ValidatorModule`, a real `Module`. Owns all eight gates plus the Human Approval Gate's pending queue.
- **`knowledge/pipelines/`** — no behavior of its own; assembles the two `PipelineDefinition`s from the capability names the two modules above register.
- **`plugins/extractor/`, `plugins/validator/`** — the on-disk, discoverable form of the two modules, so `PluginRegistry.discover()`/`instantiate()` — the same path `runtime/boot.py` uses — actually finds them.

**What is explicitly not built** (see §14 for the full list with reasons): Knowledge Graph Node/Edge Materialization, a real Crawler, Embeddings, Retrieval, and 8 of the 10 `KNOWLEDGE_EXTRACTION_SPEC.md` source types.

---

## 4. Artifact Model

### The Common Envelope (`knowledge/artifacts/envelope.py`)

Every artifact — regardless of type — is an `ArtifactEnvelope` subclass carrying:

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Must start with the type's stable prefix (`KD-`, `KA-`, `PAT-`, `AP-`, `BP-`, `EX-`, `WF-`, `KC-`); enforced by a `model_validator`. |
| `type` | `ArtifactType` | Fixed per subclass via `Literal[...]`. |
| `metadata` | `ArtifactMetadata` | `extracted_at`, `extraction_method`, `extractor_version`, `artifact_schema_version` (default `"1.0.0"`). |
| `version` | `ArtifactVersionInfo` | `artifact_version` (structural) vs. `applies_to` (the claim's ERPNext/Frappe scope) — never conflated. `version_confidence`: `"explicit"`/`"stated"`/`"inferred"`. |
| `provenance` | `tuple[ProvenanceLink, ...]` | Chain back to the originating `Knowledge Document`. |
| `confidence` | `float`, `[0.0, 1.0]` | Pydantic-enforced range; set only by Confidence Scoring (gate 8) or `PendingApprovalStore.resolve()`. |
| `source_references` | `tuple[SourceReference, ...]` | `url`, `retrieved_at`, `content_hash`, optional `span`. |
| `tags` | `tuple[str, ...]` | Kebab-case facets — also this Sprint's seam for facts the envelope has no dedicated field for (see §15). |
| `dependencies` | `tuple[DependencyEdge, ...]` | The `depends_on`-typed subset of `relationships`. |
| `relationships` | `tuple[RelationshipEdge, ...]` | Full typed-edge vocabulary (9 relationship types, mirroring `KNOWLEDGE_GRAPH_SPEC.md` §3). |
| `status` | `ArtifactStatus` | Sprint-2-assembled: `draft`/`validated`/`rejected`/`pending-conflict-resolution`/`pending-human-approval`/`superseded`. Default `draft`. |

**Immutability:** `ArtifactEnvelope` is `frozen=True`. A status transition, tag addition, or any other change produces a *new* instance via `model_copy(update={...})`; nothing is ever mutated in place. This mirrors `KNOWLEDGE_GRAPH_SPEC.md` §4's "append, never overwrite" rule for graph edges, applied to the artifact itself.

**Deliberately permissive construction:** the schema layer does not enforce "must have ≥1 `source_reference`" or any other business rule — `KNOWLEDGE_VALIDATION_SPEC.md` §1 requires a failing artifact to be *retained* with a `rejected` status, not made un-constructible. All business-rule enforcement lives in `knowledge/validation/gates.py`.

### Content-Bearing Types

Six types extend `ArtifactEnvelope` with a type-specific `content` field and form the `ContentArtifact` union (`knowledge/artifacts/__init__.py`):

| Type | Prefix | Content fields |
|---|---|---|
| `KnowledgeAPI` | `KA` | `interface_kind`, `name`, `signature`, `parameters`, `return_shape`, `doctype_scope` |
| `Pattern` | `PAT` | `title`, `problem`, `solution_shape`, `third_party_observed` |
| `AntiPattern` | `AP` | (shares `PatternContent`) |
| `BestPractice` | `BP` | `title`, `recommendation`, `scope` |
| `Example` | `EX` | `title`, `demonstrates`, `code_or_steps` |
| `Workflow` | `WF` | `title`, `steps: tuple[WorkflowStep, ...]` |

Two more types exist outside the union: `KnowledgeDocument` (`KD` — Extraction's *input*, not a content artifact) and `KnowledgeConflict` (`KC` — Validation's *output* when a disagreement is detected).

Not modeled this Sprint: `Knowledge Source` (reused, unchanged, from `knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md`) and `Knowledge Graph Node` (belongs to the deferred Graph Materialization stage).

---

## 5. Extraction Flow

**Entry point:** `knowledge.extract` capability → `knowledge/extraction/stage.py::extract(document, context, *, id_allocator, event_bus=None)`.

**Dispatch:** by `document.metadata.extraction_method`, via a fixed dict (`_RULES_BY_EXTRACTION_METHOD`):

| `extraction_method` value | Rule function | Source |
|---|---|---|
| `"official_documentation"` | `extract_from_official_documentation` | `rules.py` |
| `"source_code"` | `extract_from_official_source_code` | `rules.py` |
| anything else | *(no rule)* | produces `[]` — not an error |

**Input contract (`KnowledgeDocument.content.structural_metadata`):** since Sprint 2 has no real Normalization stage, its own fixtures populate this dict directly, in the shape the rules expect:

```python
{
  "api_specs": [{"interface_kind", "name", "signature"?, "parameters"?,
                  "return_shape"?, "doctype_scope"?, "span"?}, ...],
  "procedures": [{"title", "steps": [{"order", "description", "invokes"?}], "span"?}, ...],
  "examples":   [{"title", "demonstrates", "code_or_steps", "span"?}, ...],
  "doctype_schemas":     [{same shape as api_specs}, ...],
  "whitelisted_methods": [{same shape as api_specs}, ...],
}
```

**`extract_from_official_documentation`** (§1): `api_specs` → `KnowledgeAPI`, `procedures` → `Workflow`, `examples` → `Example`.

**`extract_from_official_source_code`** (§2): both `doctype_schemas` and `whitelisted_methods` → `KnowledgeAPI` (same builder — a DocType field and a whitelisted method are structurally the same `KnowledgeAPIContent` shape, differing only in `interface_kind`).

**Per-artifact construction** (shared helpers `_build_knowledge_api`/`_build_workflow`/`_build_example`):
- `id` — from `IdAllocator.next_id(type)`, sequential per type (`KA-0001`, `KA-0002`, ...).
- `metadata` — `extracted_at`/`extraction_method` copied from the document; `extractor_version` hardcoded `"0.1.0"`.
- `provenance` — one `ProvenanceLink` back to the source `KnowledgeDocument.id`.
- `source_references` — one `SourceReference`, built from the document's *first* `source_reference` (url/retrieved_at/content_hash), with `span` taken from the per-item fixture dict's `"span"` key if present. This is the mechanism by which `KNOWLEDGE_EXTRACTION_SPEC.md` §0's "must point at the exact span" requirement is satisfied.
- `confidence` — left at the envelope default `0.0`; never set here (Validation's job).

**Event:** if an `EventBus` was supplied, `ArtifactCreated` is published once per produced artifact, payload `{"artifact_id": ..., "artifact_type": ...}`.

**Output:** `list[ContentArtifact]`, always `StageOutcome.SUCCESS` (an unsupported source type is a scope boundary, not a failure).

---

## 6. Pattern Extraction Design

**Entry point:** `knowledge.extract_patterns` capability → `knowledge/extraction/pattern_extraction.py::extract_patterns(artifacts, context, *, id_allocator, event_bus=None)`.

**The similarity problem, and why it's solved this way:** `KNOWLEDGE_EXTRACTION_SPEC.md` §9 asks for "a solution shape that recurs across two or more independent artifacts." Detecting that generically requires a semantic-similarity judgment — exactly what Embedding (out of scope this Sprint) would provide. Rather than fabricate a text-similarity heuristic that would silently overstate what the code actually does, Sprint 2 uses an **explicit, deterministic tag signal**: an extraction rule tags a candidate artifact `pattern-candidate:<shape-key>` or `anti-pattern-candidate:<shape-key>` (constants `PATTERN_CANDIDATE_TAG_PREFIX`/`ANTI_PATTERN_CANDIDATE_TAG_PREFIX`) — the same tag-facet convention `KNOWLEDGE_EXTRACTION_SPEC.md` itself already uses for `verified-fixed`/`interim-workaround`/`third-party-observed`.

**Algorithm (`_promote_recurring_shapes`, run twice — once per tag prefix):**
1. Group the incoming artifact list by shape-key (the tag suffix after the prefix), via `_shape_key`.
2. For each group, compute the set of *distinct* `provenance[].id` values across the group's members (`independent_sources`).
3. Promote to a new `Pattern`/`AntiPattern` only if **both** `len(group) >= 2` **and** `len(independent_sources) >= 2` (constant `_MINIMUM_INDEPENDENT_ARTIFACTS = 2`). Two same-shape artifacts from the *same* source document do **not** count as independent corroboration and are not promoted — this is `§9`'s "never manufactured from a single anecdote" bar, generalized from "one artifact" to "one source."

**Promoted artifact construction (`_build_pattern`):**
- `id` — freshly allocated (`PAT-000N`/`AP-000N`).
- `relationships` — one `REFERENCES` edge per group member, so the Pattern/Anti-Pattern is traceable back to the evidence that produced it.
- `source_references` — the concatenation of every group member's own `source_references` (full provenance retained, not summarized).
- `confidence` — left at `0.0`. Per `KNOWLEDGE_ARTIFACTS.md` §1's invariant ("confidence... never by an extraction step asserting them about itself"), Pattern Extraction never sets it; Confidence Scoring (gate 8) does, later, in the `knowledge.validation` pipeline.
- `metadata.extraction_method` — set to `"pattern_extraction"` (a distinct value from the source artifacts' own, so Confidence Scoring's `extraction_confidence()` heuristic scores it independently).

**Output:** the original `artifacts` list *plus* any newly-promoted Pattern/AntiPattern artifacts appended — nothing already present is removed or rewritten.

**Event:** `ArtifactCreated` published once per newly-promoted artifact (not for pass-through artifacts, which already got their own `ArtifactCreated` from the Extraction stage).

---

## 7. Conflict Resolution Algorithm

**Module:** `knowledge/conflict/resolution.py` (pure logic) + `knowledge/conflict/providers.py` (the `PrecedenceProvider` seam) + `knowledge/conflict/stage.py` (the two pipeline-facing wrappers).

### 7.1 Precedence Rules

`PrecedenceTier` is a 9-member `IntEnum`, lower value = higher authority, per `KNOWLEDGE_CONFLICT_RESOLUTION.md` §1:

```
1. OFFICIAL_SOURCE_CODE
2. MERGED_PULL_REQUEST
3. OFFICIAL_DOCUMENTATION
4. OFFICIAL_RELEASE_NOTES
5. STAFF_FORUM_REPLY
6. COMMUNITY_FORUM_CONSENSUS
7. VETTED_MARKETPLACE
8. TUTORIALS_BLOGS_TALKS
9. UNVETTED_COMMUNITY
```

`resolve_conflict(case: ConflictCase) -> ConflictResolution` checks, **in this fixed order** (each check narrower/more specific than the next, so a specific scenario is never shadowed by the general rule):

1. **§6 rule-contradiction escalation** (`_rule_contradiction`) — if either claim's `contradicts_stable_rule` flag is set, outcome is `ESCALATED_RULE_CONTRADICTION`, `requires_human_review=True`, **bypassing precedence entirely** — even a tier-1 (official source code) claim does not win here.
2. **§2/§6 version-scope check** (`_version_scoped_pair`) — if both claims have a non-`None`, *differing*, non-`"inferred"`-confidence `version_applies_to`, this is not a real conflict: outcome `BOTH_VALID_VERSION_SCOPED`, the newer version "wins" (is `winning_claim_id`) for current-version queries, the older is `losing_claim_id` — but per the reason text, "neither is deleted or demoted." (`_version_is_newer` does a best-effort numeric extraction via regex, falling back to lexicographic comparison.)
3. **§4 staff-forum-postdates-docs** (`_docs_vs_staff_forum`) — if one claim is `OFFICIAL_DOCUMENTATION` tier and the other is `staff_authored=True` **and** `authored_after_docs_last_update=True`, outcome is `FLAGGED_DOCS_MAY_BE_STALE`, `requires_human_review=True`, **no winner assigned** — this is a deliberate override of plain precedence (docs would otherwise beat forum outright).
4. **§1 general precedence** — if tiers differ, the lower tier wins: outcome `WINNER_BY_PRECEDENCE`.
5. **Fallback** — same tier, none of the above applied: outcome `UNDECIDED`, `requires_human_review=True`, reason text literally `"Undecided — surface to a human per AGENTS.md, do not resolve silently."`

### 7.2 Undecided Handling

`UNDECIDED` is never a distinguished error path — it is one of five ordinary `ConflictOutcomeKind` values, returned with no `winning_claim_id`/`losing_claim_id` and `requires_human_review=True`. Every caller (the Version Conflict Detection gate, the batch resolver) is required to branch on `requires_human_review`, not on outcome-kind pattern-matching, so `UNDECIDED`/`FLAGGED_DOCS_MAY_BE_STALE`/`ESCALATED_RULE_CONTRADICTION` are all handled identically at the call site (route to human), differing only in the `reason` text carried for audit.

### 7.3 Batch Behavior (`resolve_conflicts_in_batch`)

Used by `knowledge.graph_build`'s Conflict Resolution stage. Input: `list[ContentArtifact | KnowledgeConflict]` (Pattern Extraction's output, potentially containing raw `KnowledgeConflict` entries — see §14 for why none currently do).

1. Partition the input into `conflicts` (the `KnowledgeConflict` items) and `content_by_id` (everything else, keyed by `id`).
2. For each conflict: look up `claim_a`/`claim_b` by the `KnowledgeConflictContent.claim_a_id`/`claim_b_id` IDs in `content_by_id`.
   - If either is missing from this batch, the conflict is left in `unresolved` untouched — "nothing to resolve here," not an error.
   - Otherwise, build a `ConflictCase` via `to_conflict_claim` (which reads `precedence_tier` from the injected `PrecedenceProvider`, plus the tag-facet booleans from each artifact's `tags`) and call `resolve_conflict`.
   - If `requires_human_review` or no `losing_claim_id`, the conflict is left in `unresolved`.
   - Otherwise, the losing claim (looked up by `resolution.losing_claim_id`) is replaced in `content_by_id` with a copy carrying `status=SUPERSEDED`. The `KnowledgeConflict` itself is **dropped** from the output (its outcome is now recorded on the claim, not carried forward as a separate artifact).
3. Return `[*content_by_id.values(), *unresolved]` — every content artifact (winners unchanged, losers superseded) plus any conflicts that could not be resolved this batch.

**Nothing is ever silently discarded**: a deterministically-resolved conflict's outcome is recorded via `SUPERSEDED` status on the losing artifact; an unresolved one remains a `KnowledgeConflict` in the output, explicitly surfaced.

---

## 8. Validation Pipeline

**Fixed order** (`KNOWLEDGE_VALIDATION_SPEC.md` §0: "later stages assume earlier ones already passed"), all eight implemented in `knowledge/validation/gates.py`.

**Structural note applying to all eight:** `runtime.pipeline.engine.PipelineEngine` discards a run's `output` entirely when a stage returns `StageOutcome.FAILURE` — it cannot, by construction, hand back a rejected-but-retained artifact for inspection. Since `KNOWLEDGE_VALIDATION_SPEC.md`'s "never deleted, only rejected/superseded/pending, always retained" principle is non-negotiable, **every gate below always returns `StageOutcome.SUCCESS`** and encodes the real business outcome in `artifact.status`. "Stopping" a halted artifact from further processing is implemented as every subsequent gate checking `artifact.status in _PASSES_THROUGH` (`{REJECTED, SUPERSEDED, PENDING_CONFLICT_RESOLUTION, PENDING_HUMAN_APPROVAL}`) and passing it through byte-for-byte unchanged if so — never as an Engine-level abort.

### Gate 1 — Schema Validation (`schema_validation`)
**Checks:** (a) `source_references` is non-empty; (b) `metadata.artifact_schema_version` is in `KNOWN_ARTIFACT_SCHEMA_VERSIONS` (currently `{"1.0.0"}`).
**On failure:** `status → REJECTED`. Per spec, this represents an extraction-pipeline defect, not a knowledge-quality problem — it is never routed to the Human Approval Gate.
**On pass:** artifact returned unchanged.

### Gate 2 — Duplicate Detection (`duplicate_detection`)
**Checks:** exact content-hash match (`KnowledgeStore.find_exact_duplicate`, keyed by `(type, sha256(content.model_dump_json()))`) against every artifact previously seen by this `KnowledgeStore` instance.
**On no match:** the artifact is remembered in the store and returned unchanged.
**On match:** **not rejected — merged.** The *existing* artifact is returned (not the incoming one), with its `source_references` extended by the incoming artifact's references — corroboration, not duplication. Near-duplicate/semantic detection is out of scope (needs Embedding).

### Gate 3 — Version Conflict Detection (`version_conflict_detection`)
**Checks:** among artifacts already in the `KnowledgeStore` with the same `(type, version.applies_to)`, is there one with the same "claim identity" (`_claim_identity` — `content.name` or `content.title`) but a *different* "claim body" (`_claim_body` — the type-specific substantive fields: `KnowledgeAPI`'s `(signature, return_shape)`, `Pattern`/`AntiPattern`'s `solution_shape`, `BestPractice`'s `recommendation`, `Example`'s `code_or_steps`, `Workflow`'s ordered `(order, description)` tuple)?
**On no version scope (`applies_to is None`) or no match:** unchanged.
**On a genuine disagreement:** builds a `ConflictCase` (via `to_conflict_claim`, using the injected `PrecedenceProvider`) and calls `resolve_conflict`. Publishes `ConflictDetected` regardless of outcome. Then:
- `requires_human_review` → `status → PENDING_CONFLICT_RESOLUTION`.
- deterministic loser (this artifact loses) → `status → SUPERSEDED`.
- deterministic winner (this artifact wins) → continues validating, unchanged.

### Gate 4 — Source Verification (`source_verification`)
**Checks:** `source_verifier.verify(artifact)` (injected `SourceVerifier`, no default implementation — see §9/§14).
**On failure:** `status → REJECTED` — "the second, most direct anti-hallucination check."
**On pass:** unchanged.

### Gate 5 — Trust Verification (`trust_verification`)
**Checks:** `trust_score_provider.trust_score(artifact)` against `_trust_threshold_for(artifact)` — the per-type table:

| Artifact type | Threshold |
|---|---|
| `KnowledgeAPI` | 80 |
| `Pattern` (official) | 70 |
| `Pattern` (`third_party_observed=True`) | 50 |
| `AntiPattern` | 70 |
| `BestPractice` | 50 |
| `Example` | 40 |
| `Workflow` | 60 |

**On below-threshold:** **not rejected — demoted.** A `low-confidence` tag is added (idempotently — checked via `TAG_LOW_CONFIDENCE not in artifact.tags` first). Status is untouched. **Known narrowing from the literal spec text** — see §14.
**On at/above threshold:** unchanged.

### Gate 6 — Engineering Review (`engineering_review`)
**Checks:** is `TAG_CONTRADICTS_STABLE_RULE` present in `artifact.tags`?
**On present:** `status → PENDING_HUMAN_APPROVAL` — escalated straight to gate 7, "bypassing normal risk-tiered routing," per `PROJECT_CHARTER.md`'s AI First Principles (never resolved automatically).
**On absent:** unchanged. (No automated Bad-Pattern-matching against `rules/*.md` is implemented — the tag is the entire mechanism this Sprint provides; see §14.)

### Gate 7 — Human Approval Gate (`human_approval_gate`)
**Checks four conditions are evaluated as two:**
- `already_routed` — status already `PENDING_CONFLICT_RESOLUTION` or `PENDING_HUMAN_APPROVAL` (set by gates 3/6).
- `ambiguous_confidence` — `compute_confidence_for_artifact(artifact, trust_score_provider)` (the *same* formula gate 8 will later use — see §14's note on this being computed twice) falls in `[0.4, 0.6]`.
Condition 1 of the spec ("Engineering Rule candidate drafts") never applies — `ContentArtifact`'s union has no rule-candidate type (per `KNOWLEDGE_ARTIFACTS.md` §2.9, a candidate is a `rules/*.md`-shaped document, not a pipeline-native artifact).
**If neither condition holds:** unchanged — the automated approval path.
**If either holds:** `status → PENDING_HUMAN_APPROVAL`, recorded in `PendingApprovalStore`, `HumanApprovalRequested` published.

### Gate 8 — Confidence Scoring (`confidence_scoring`)
**Checks:** none — this is computation, not a gate in the reject/pass sense.
**Behavior:** if status is in `_PASSES_THROUGH` (already terminal or still pending), returned unchanged — a still-pending artifact is **not** finalized here; it is finalized later, out-of-band, by `PendingApprovalStore.resolve()`.
Otherwise: `confidence = compute_confidence_for_artifact(...)`, `status → VALIDATED`. This is what "passed validation" means. `ValidationCompleted` published, payload `{"artifact_id", "confidence"}`.

**Confidence formula** (`knowledge/validation/confidence.py`, `KNOWLEDGE_VALIDATION_SPEC.md` §8):
```
confidence = (trust_score / 100) × extraction_confidence × corroboration_multiplier × recency_factor
```
- `extraction_confidence` — looked up from `metadata.extraction_method` (`source_code`→1.0, `merged_pull_request`→0.9, `official_documentation`→0.85, `forum_reply`→0.65, `video_transcript`→0.6, default 0.75).
- `corroboration_multiplier` — `1.0 + 0.1 × (len(source_references) - 1)`, capped at `1.3`.
- `recency_factor` — hardcoded `1.0` (no live version registry this Sprint — see §14).
- Result clamped to `[0.0, 1.0]`.

---

## 9. Pipeline Definitions

Both defined in `knowledge/pipelines/definitions.py`, registered together by `register_knowledge_pipelines(engine)`.

### `knowledge.validation`
```python
PipelineDefinition(
    name="knowledge.validation",
    stages=(
        StageDefinition("schema_validation", CAPABILITY_SCHEMA),
        StageDefinition("duplicate_detection", CAPABILITY_DUPLICATE),
        StageDefinition("version_conflict_detection", CAPABILITY_VERSION_CONFLICT),
        StageDefinition("source_verification", CAPABILITY_SOURCE_VERIFY),
        StageDefinition("trust_verification", CAPABILITY_TRUST_VERIFY),
        StageDefinition("engineering_review", CAPABILITY_ENGINEERING_REVIEW),
        StageDefinition("human_approval_gate", CAPABILITY_HUMAN_APPROVAL),
        StageDefinition("confidence_scoring", CAPABILITY_CONFIDENCE_SCORE),
    ),
)
```
All eight stages registered, in `KNOWLEDGE_VALIDATION_SPEC.md` §0's fixed order, each bound to the matching `ValidatorModule`-provided capability. `PipelineEngine.run("knowledge.validation", initial_input=<one ContentArtifact>)` executes them sequentially; per Sprint 1's own `PipelineEngine._execute_stage`, each stage's output becomes the next stage's input, and every gate above is written to accept and return exactly that same artifact type (or an updated copy of it) — so the whole run threads one artifact through all eight gates. Every `StageDefinition` uses the default `max_attempts=1` — no gate is retried (none of them are transient/network operations at this Sprint's fixture scale).

### `knowledge.graph_build`
```python
PipelineDefinition(
    name="knowledge.graph_build",
    stages=(
        StageDefinition("extraction", CAPABILITY_EXTRACT),
        StageDefinition("pattern_extraction", CAPABILITY_EXTRACT_PATTERNS),
        StageDefinition("conflict_resolution", CAPABILITY_RESOLVE_CONFLICTS_BATCH),
    ),
)
```
Three of the four stages `docs/runtime/PIPELINE_ENGINE.md` §4's table specifies for `knowledge.graph_build` (Extraction, Pattern Extraction, Conflict Resolution, **Graph Node/Edge Materialization**). The fourth is deferred — see §14. `PipelineEngine.run("knowledge.graph_build", initial_input=<one KnowledgeDocument>)`:
1. `extraction` — `KnowledgeDocument` in, `list[ContentArtifact]` out.
2. `pattern_extraction` — `list[ContentArtifact]` in, `list[ContentArtifact]` out (input list plus any newly-promoted patterns).
3. `conflict_resolution` — `list[ContentArtifact | KnowledgeConflict]` in (in practice, always `list[ContentArtifact]` this Sprint — see §14), `list[ContentArtifact | KnowledgeConflict]` out.

The two pipelines are meant to be **chained by the caller**, not automatically: `knowledge.graph_build`'s output (a list) is not itself valid input to `knowledge.validation` (which expects one artifact) — a caller iterates the list and calls `engine.run("knowledge.validation", initial_input=artifact)` once per produced artifact. This is exactly what `tests/knowledge/test_pipeline_integration.py` does.

**`register_knowledge_pipelines`** simply calls `engine.register()` twice — `PipelineEngine.register()` already raises `PipelineDefinitionError` on a duplicate name, so no additional idempotency handling was added.

---

## 10. Event Model

Every event below is confirmed, in `tests/knowledge/test_event_publication.py`, to actually reach a real `runtime.events.bus.EventBus` during an end-to-end run — not merely asserted to be "published" in isolation.

| Event | Published by (file:function) | When | Payload |
|---|---|---|---|
| `ArtifactCreated` | `extraction/stage.py::extract` | Once per artifact Extraction produces | `{"artifact_id", "artifact_type"}` |
| `ArtifactCreated` | `extraction/pattern_extraction.py::extract_patterns` | Once per newly-promoted Pattern/AntiPattern | `{"artifact_id", "artifact_type"}` |
| `ConflictDetected` | `validation/gates.py::version_conflict_detection` | Whenever a genuine same-subject, same-version disagreement is found (regardless of resolution outcome) | `{"artifact_id", "conflicting_with", "outcome"}` |
| `HumanApprovalRequested` | `validation/gates.py::human_approval_gate` | Whenever an artifact is actually routed into the pending queue | `{"artifact_id"}` |
| `HumanApprovalResolved` | `validation/approval.py::PendingApprovalStore._publish_resolved` (called from `resolve()`) | Every time `resolve()` is called, approved or rejected | `{"artifact_id", "decision"}` |
| `ValidationCompleted` | `validation/gates.py::confidence_scoring` | Once an artifact reaches `VALIDATED` (i.e. survives all 8 gates without being rejected/superseded/pending) | `{"artifact_id", "confidence"}` |
| `PipelineRunStateChanged` | Sprint 1's `runtime/pipeline/engine.py::PipelineEngine._emit_run_state_changed` (unmodified) | `running` then `completed`/`failed`, for every `engine.run()` call on either Sprint 2 pipeline | `{"pipeline_name", "state"}` |

All five Sprint-2-specific events match `docs/studio/STUDIO_EVENT_MODEL.md` §2's "Knowledge Factory Status" table exactly — no new event name was invented beyond what that table already specifies. `PipelineRunStateChanged` is Sprint 1's own generic event, inherited for free since `PipelineEngine` was constructed with an `EventBus` in the integration tests.

**Not implemented this Sprint** (named in the Studio catalog but with no producing code yet): `GraphNodeCreated`/`GraphEdgeCreated`/`GraphSnapshot` (Knowledge Graph module, deferred), `RuleCandidateCreated`/`RuleEvaluated` (no rule-candidate type modeled), `RetrievalQueryExecuted`/`EmbeddingGenerated` (out of scope), `DocumentDiscovered`/`DocumentDownloaded`/`DocumentParsed`/`MetadataExtracted`/`ConnectorStatusSnapshot` (Crawler, not built by any Sprint).

**Event delivery mechanism:** every publisher takes an optional `event_bus: EventBus | None = None` parameter, threaded through `functools.partial` closures built in each module's `init()`. If no `EventBus` capability (`"runtime.event_bus"`) is registered in the `Container`, `event_bus` resolves to `None` and every publish call is a silent no-op — a Validator/Extractor used standalone (e.g. a unit test calling a gate function directly) needs no Event Bus.

---

## 11. Capability Map

```
Capability                              Provider Module      Pipeline Stage (in which PipelineDefinition)
─────────────────────────────────────── ───────────────────  ─────────────────────────────────────────────
knowledge.extract                       ExtractorModule   →  "extraction"            (knowledge.graph_build)
knowledge.extract_patterns              ExtractorModule   →  "pattern_extraction"     (knowledge.graph_build)
knowledge.resolve_conflicts_batch       ExtractorModule   →  "conflict_resolution"    (knowledge.graph_build)

knowledge.validate.schema               ValidatorModule   →  "schema_validation"          (knowledge.validation)
knowledge.validate.duplicate            ValidatorModule   →  "duplicate_detection"        (knowledge.validation)
knowledge.validate.version_conflict     ValidatorModule   →  "version_conflict_detection" (knowledge.validation)
knowledge.validate.source_verify        ValidatorModule   →  "source_verification"        (knowledge.validation)
knowledge.validate.trust_verify         ValidatorModule   →  "trust_verification"         (knowledge.validation)
knowledge.validate.engineering_review   ValidatorModule   →  "engineering_review"         (knowledge.validation)
knowledge.validate.human_approval       ValidatorModule   →  "human_approval_gate"        (knowledge.validation)
knowledge.validate.confidence_score     ValidatorModule   →  "confidence_scoring"         (knowledge.validation)
```

**Capabilities that exist but are *not* pipeline stages** (resolved directly out of the `Container`, never bound to a `StageDefinition`):

```
Capability                                Provider Module    Consumed by
────────────────────────────────────────  ─────────────────  ──────────────────────────────────────────
knowledge.providers.source_verifier       (external, seam)   ValidatorModule.init() → source_verification
knowledge.providers.trust_score           (external, seam)   ValidatorModule.init() → trust_verification,
                                                               confidence_scoring, human_approval_gate
knowledge.providers.precedence            (external, seam)   ValidatorModule.init() → version_conflict_detection;
                                                               ExtractorModule.init() → conflict_resolution
runtime.event_bus                         (external, optional) Both modules' init(), for event publication
```

The three `knowledge.providers.*` capabilities have **no provider module** — they are the `SourceVerifier`/`TrustScoreProvider`/`PrecedenceProvider` seams (§14) that a caller must register before either module's `init()` runs. They are deliberately **not** declared in either `module.yaml`'s `capabilities_required`, so `PluginRegistry.validate_dependencies()` does not (and structurally cannot) catch a missing one — `Container.resolve()` raises `CapabilityResolutionError` directly instead, which is the failure mode demonstrated live via `architect doctor --plugin-path plugins` (fails with a clear message; see §14).

---

## 12. Public APIs

Every symbol a caller outside `knowledge/` is expected to import, by package:

**`knowledge.artifacts`** — `ArtifactType`, `ArtifactStatus`, `ARTIFACT_ID_PREFIXES`, `ArtifactMetadata`, `ArtifactVersionInfo`, `ProvenanceLink`, `SourceReference`, `RelationshipType`, `RelationshipEdge`, `DependencyEdge`, `ArtifactEnvelope`, `KnowledgeDocument`/`KnowledgeDocumentContent`, `KnowledgeAPI`/`KnowledgeAPIContent`, `Pattern`/`AntiPattern`/`PatternContent`, `BestPractice`/`BestPracticeContent`, `Example`/`ExampleContent`, `Workflow`/`WorkflowContent`/`WorkflowStep`, `KnowledgeConflict`/`KnowledgeConflictContent`/`KnowledgeConflictStatus`, `ContentArtifact` (union type alias). All pydantic models, all frozen. This is the vocabulary every other package and every future Sprint building on the Knowledge Factory imports.

**`knowledge.conflict`** — `PrecedenceTier`, `ConflictClaim`, `ConflictCase`, `ConflictOutcomeKind`, `ConflictResolution`, `resolve_conflict(case) -> ConflictResolution` (the pure algorithm, callable with no pipeline/module machinery at all — e.g. for a future Studio tool that wants to preview a resolution), `resolve_conflict_stage`/`resolve_conflicts_in_batch` (pipeline adapters), `PrecedenceProvider` (Protocol to implement), `to_conflict_claim` (artifact→claim helper), `TAG_STAFF_AUTHORED`/`TAG_AFTER_DOCS_UPDATE`/`TAG_CONTRADICTS_STABLE_RULE` (the tag strings a caller must set to trigger the corresponding scenario).

**`knowledge.validation`** — `ValidatorModule` (the `Module` to register with a `PluginRegistry`, or instantiate/`init()` directly in a test), `PendingApprovalStore`, `ApprovalDecision`, `KnowledgeStore`, `SourceVerifier`/`TrustScoreProvider`/`PrecedenceProvider` (the three Protocols a real deployment must implement). `knowledge.validation.gates` (not re-exported from `__init__.py`, imported directly as `from knowledge.validation import gates`) exposes all eight gate functions individually plus `TRUST_THRESHOLDS`/`KNOWN_ARTIFACT_SCHEMA_VERSIONS` for anything that wants to call a single gate in isolation (as every test in `test_validation_gates.py` does).

**`knowledge.extraction`** — `ExtractorModule`, `IdAllocator`, `extract`, `extract_patterns`, `PATTERN_CANDIDATE_TAG_PREFIX`/`ANTI_PATTERN_CANDIDATE_TAG_PREFIX` (the tag prefixes a future extraction rule must use to make a candidate eligible for promotion).

**`knowledge.pipelines`** — `KNOWLEDGE_VALIDATION_PIPELINE`, `KNOWLEDGE_GRAPH_BUILD_PIPELINE` (the two `PipelineDefinition` constants, importable for inspection without registering them), `register_knowledge_pipelines(engine)`.

**Not exported anywhere** (internal, prefixed `_`): `gates._reject`/`_claim_identity`/`_claim_body`/`_trust_threshold_for`/`_PASSES_THROUGH`; `resolution._rule_contradiction`/`_version_scoped_pair`/`_docs_vs_staff_forum`/`_version_is_newer`/`_leading_number`; `rules._source_reference_for`/`_provenance_for`/`_metadata_for`/`_build_*`; `pattern_extraction._promote_recurring_shapes`/`_shape_key`/`_build_pattern`; `state.content_hash` (module-level, not underscore-prefixed, but only ever called internally by `KnowledgeStore`).

---

## 13. Tests

73 tests across 9 files, all under `tests/knowledge/`. `conftest.py` (not itself a test file) supplies every shared fixture.

### `conftest.py`
Not a test file — shared infrastructure. Provides: `make_metadata`/`make_source_ref`/`make_knowledge_document`/`make_knowledge_api`/`make_pattern`/`make_best_practice` (factory fixtures returning fully-formed, overridable artifacts); `StaticSourceVerifier`/`StaticTrustScoreProvider`/`StaticPrecedenceProvider` (configurable test doubles for the three provider Protocols) plus `source_verifier`/`trust_score_provider`/`precedence_provider` fixtures wrapping them; `pipeline_context` (a ready-to-use `PipelineContext`); `fixture_document()` (a plain function, not a fixture — a `KnowledgeDocument` shaped for `official_documentation` extraction, reused by name across test files); `wired_engine` (the one fixture that does real work: discovers the actual `plugins/` directory via `PluginRegistry`, instantiates/`init()`s/`start()`s both real modules against a real `Container` with the three provider capabilities and an `EventBus` registered, builds a real `PipelineEngine`, registers both Sprint 2 `PipelineDefinition`s, and returns it).

### `test_artifacts.py` — 10 tests
Validates the artifact schema layer in isolation: `KnowledgeDocument` constructs with empty `source_references` (proving schema-level permissiveness); `type` is fixed per subclass; `id`-prefix mismatch raises `ValidationError`; out-of-range `confidence` raises; the envelope is frozen (assigning `.status` raises); `model_copy(update=...)` produces a new, independent instance; `Pattern`/`AntiPattern` share `PatternContent` but differ in `.type`; `BestPractice`/`Example`/`Workflow` all construct correctly; `KnowledgeConflict` links two claim IDs and defaults to `open`; `RelationshipEdge`/`DependencyEdge` round-trip through construction.

### `test_conflict_resolution.py` — 15 tests
Validates `resolve_conflict`, `resolve_conflict_stage`, and `resolve_conflicts_in_batch` in isolation from any pipeline/module machinery: precedence ordering (and that it's symmetric regardless of argument position); scenario 2 (differing-version is not a conflict, and that an `inferred`-confidence version does *not* skip the check); scenario 3 (code beats docs); scenario 4 (staff-forum-postdating-docs is flagged not resolved, and that the exception does *not* apply when the forum reply predates the docs); scenario 5 (marketplace never outranks the framework); scenario 6 (a version-transition is not a conflict, and rule-contradiction escalates regardless of tier); same-tier-no-version-difference is `UNDECIDED` with the exact required reason substring; `resolve_conflict_stage` matches the `(input, context) -> (output, outcome)` contract; three `resolve_conflicts_in_batch` tests (deterministic supersession, an unresolvable conflict left in the batch, a conflict whose referenced claims aren't present in the batch passed through untouched).

### `test_validation_gates.py` — 20 tests
Calls each of the 8 gate functions directly (not through a `PipelineEngine`), covering: gate 1 rejects on empty `source_references` and on unknown schema version, passes a well-formed artifact, and passes an already-`REJECTED` artifact through *unchanged* (same object identity, `result is rejected`); gate 2 remembers a first-seen artifact and merges an exact duplicate's `source_references` into the existing one; gate 3 supersedes the lower-precedence claim, lets the higher-precedence claim continue, holds a same-tier conflict at `PENDING_CONFLICT_RESOLUTION`, and ignores claims about a different subject entirely; gate 4 rejects/passes based on `SourceVerifier` result; gate 5 tags `low-confidence` below threshold, does not tag at/above, and uses the lower third-party threshold for a `third_party_observed` Pattern; gate 6 escalates a tagged artifact and passes an untagged one; gate 8 promotes a surviving artifact to `VALIDATED` with `0 < confidence <= 1`, and leaves both a `REJECTED` and a `PENDING_HUMAN_APPROVAL` artifact untouched (proving gate 8 never finalizes a still-pending artifact).

### `test_approval_gate.py` — 9 tests
Focuses on gate 7 and `PendingApprovalStore`: an ordinary artifact takes the automated path (never enters the queue); a Best Practice with trust=60 (deliberately chosen so `0.6 × 0.75 = 0.45` lands in the ambiguous band) is routed to the queue; an artifact already `PENDING_CONFLICT_RESOLUTION` is also routed (proving gate 7 acts on, not merely passes through, that status); `REJECTED`/`SUPERSEDED` pass through untouched; `HumanApprovalRequested` reaches a real `EventBus`; `resolve(APPROVED)` finalizes to `VALIDATED` with `confidence > 0` and drains the queue; `resolve(REJECTED)` finalizes to `REJECTED`; resolving an unknown `artifact_id` raises `KeyError`; `resolve()` publishes `HumanApprovalResolved` with the correct payload.

### `test_extraction.py` — 6 tests
`extract_from_official_documentation` produces a correct `KnowledgeAPI` (name/signature/span/provenance all checked); the same rule produces both a `Workflow` (2 ordered steps, `invokes` preserved) and an `Example` from one document; `extract_from_official_source_code` produces two `KnowledgeAPI`s (one from `doctype_schemas`, one from `whitelisted_methods`); an out-of-scope `extraction_method` (e.g. `video_transcript`) produces `[]` with `StageOutcome.SUCCESS` (not a failure); `ArtifactCreated` is published once per produced artifact; `IdAllocator` issues correctly-prefixed, per-type-sequential IDs.

### `test_pattern_extraction.py` — 6 tests
A shape observed once is never promoted (list unchanged, same objects); a shape from two artifacts with *different* `provenance[0].id` is promoted to a `Pattern` referencing both via `REFERENCES` edges; a shape repeated *within the same source document* (same `provenance[0].id` on both) is **not** promoted, proving the independence check actually checks provenance, not just count; `anti-pattern-candidate:` promotes to `AntiPattern` via its own prefix; untagged artifacts pass through unaffected; a promoted Pattern's `confidence` is exactly `0.0` (never hand-set).

### `test_pipeline_integration.py` — 4 tests
Uses `wired_engine` (real `PluginRegistry` discovery of the actual `plugins/` directory, real `init()`/`start()`, real `PipelineEngine`): `knowledge.graph_build` run against `fixture_document()` produces exactly one `KnowledgeAPI`; that artifact, run through `knowledge.validation`, ends `VALIDATED` with `0 < confidence <= 1`, and the recorded `stage_records` name all eight gates in the exact fixed order; an artifact with `source_references` stripped to `()` and re-run through `knowledge.validation` ends `REJECTED` while the *pipeline run itself* still reports `succeeded` (proving the "never `StageOutcome.FAILURE`" design holds end-to-end, not just at the unit level); `wired_engine.registered_pipelines()` returns exactly `{"knowledge.validation", "knowledge.graph_build"}`.

### `test_event_publication.py` — 3 tests
Also via `wired_engine`: `ArtifactCreated` reaches a real `EventBus` during a `knowledge.graph_build` run, with the correct `artifact_type`; `ValidationCompleted` reaches the bus during a `knowledge.validation` run, with the correct `artifact_id`; `PipelineRunStateChanged` fires 4 times total (running+completed × 2 pipeline runs) and includes both `"knowledge.graph_build:completed"` and `"knowledge.validation:completed"`.

---

## 14. Known Limitations

Every deferral below is a stated, deliberate Sprint 2 scope boundary — not an oversight discovered after the fact.

1. **No `StageOutcome.FAILURE` anywhere in the 8 gates.** *Why deferred:* `PipelineEngine.run()` sets `output=None` on the `PipelineRunResult` the moment any stage returns `FAILURE` (see `runtime/pipeline/engine.py`'s `run()` method) — there is no mechanism in Sprint 1's Engine to fail a stage *and* retain its output. Since retaining a rejected artifact is a non-negotiable requirement of `KNOWLEDGE_VALIDATION_SPEC.md`, and modifying `PipelineEngine` was explicitly out of scope ("Do not modify Runtime"), every gate encodes outcome in `artifact.status` instead. This is the single largest structural decision in Sprint 2 and is flagged again in §16.

2. **Trust Verification's demotion is tag-only, not type-changing.** `KNOWLEDGE_VALIDATION_SPEC.md` §5's literal example ("a Best Practice candidate from a Trust-30 source is retained as a tagged low-confidence Example instead") describes retyping the artifact to a different, lower-bar `ContentArtifact` subclass. Sprint 2 only adds a `low-confidence` tag; the artifact's Python type/`ArtifactType` is unchanged. *Why deferred:* full retyping requires a defined demotion-target mapping per type and a way to reconstruct a differently-shaped `content` payload from the original — a real feature, not a one-line fix, and not requested as explicitly in-scope by the plan.

3. **Extraction implements 2 of 10 `KNOWLEDGE_EXTRACTION_SPEC.md` source types** (Official Documentation, Official Source Code). *Why deferred:* `SPRINT2_IMPLEMENTATION_PLAN.md` §4 explicitly scoped this to "a first, deliberately small subset"; the other 8 (GitHub Issues, Merged PRs, Release Notes, Forum Discussions, Marketplace Apps, Tutorials/Videos, plus two more) each have materially different extraction rules and no Crawler yet supplies real input for any of them.

4. **Pattern Extraction uses an explicit tag signal, not semantic similarity.** *Why deferred:* genuine similarity detection needs Embedding, out of scope this Sprint per the plan. A fabricated text-similarity heuristic was considered and rejected as worse than the honest tag-based mechanism, because it would misrepresent the code's actual sophistication to a future reader.

5. **`resolve_conflicts_in_batch` has no live producer.** No implemented extraction rule emits a raw `KnowledgeConflict` (that would come from, e.g., `KNOWLEDGE_EXTRACTION_SPEC.md` §6's "contradicting forum answers" rule — not implemented, see limitation 3). *Why deferred:* the same "2 of 10 source types" scoping. The batch resolver itself is real and tested via directly-constructed fixtures (`test_conflict_resolution.py`'s three `resolve_conflicts_in_batch` tests); only its upstream feed is missing.

6. **Graph Node/Edge Materialization (the 4th `knowledge.graph_build` stage) is not registered.** *Why deferred:* `SPRINT2_IMPLEMENTATION_PLAN.md` §2's explicit scope decision — this stage belongs to a Knowledge Graph module no Sprint has built, and building graph storage/traversal was never in Sprint 2's brief.

7. **`SourceVerifier`/`TrustScoreProvider`/`PrecedenceProvider` have no default implementation, and booting a real Runtime against `plugins/` fails without them.** Confirmed live: `architect doctor --plugin-path plugins` raises `CapabilityResolutionError: no provider registered for capability 'knowledge.providers.precedence'`. *Why deferred, and why this is by design, not a bug:* a default "always succeeds" implementation would be functionally indistinguishable from a disguised stub silently letting every artifact through — the opposite of `KNOWLEDGE_VALIDATION_SPEC.md`'s anti-hallucination intent. The real implementations depend on a live Crawler and Knowledge Source Catalog integration, neither built yet.

8. **`ArtifactStatus` is a Sprint-2-assembled state machine, not previously frozen anywhere as one.** The individual status values are named piecemeal across `KNOWLEDGE_VALIDATION_SPEC.md`, `KNOWLEDGE_ARTIFACTS.md` §2.7, and `KNOWLEDGE_CONFLICT_RESOLUTION.md`; Sprint 2 assembled them into one enum because the gates needed a concrete type. *Why not escalated as an architecture question this Sprint:* narrow enough (6 values, all individually spec-named) that assembling it was a reasonable implementation step, but it has not been through architecture review as a unified state machine.

9. **No persistence layer anywhere.** `KnowledgeStore` (duplicate/version indices), `IdAllocator` (ID issuance), and `PendingApprovalStore` (the approval queue) are all process-local, in-memory, and lost on process exit. *Why deferred:* no Sprint has built a storage layer; `SPRINT2_IMPLEMENTATION_PLAN.md` §3 named this explicitly out of scope.

10. **`PendingApprovalStore.resolve()` finalizes directly rather than restarting a pipeline run.** The original plan sketch (`SPRINT2_IMPLEMENTATION_PLAN.md` §6) described resolution as "starting a new pipeline run continuing from Confidence Scoring." The actual implementation has `resolve()` compute confidence and set the terminal status itself, without re-entering `knowledge.validation`. *Why changed during implementation:* re-running the full 8-gate sequence on a just-approved artifact risked gate 7 re-evaluating its own ambiguous-confidence check and re-queuing the artifact it was just asked to release — a real infinite-loop/re-entry risk, not a hypothetical one. Flagged explicitly for review in §16, since it is a deviation from the written plan.

11. **`recency_factor` is hardcoded to `1.0`.** *Why deferred:* the confidence formula's version-recency factor needs a live "current framework version" registry to compare `version.applies_to` against; no such registry exists this Sprint.

12. **Duplicate Detection is exact-match only** (content-hash equality), not near-duplicate/semantic. *Why deferred:* near-duplicate detection is explicitly assigned to Embedding in `KNOWLEDGE_PIPELINE.md` §5, out of scope.

13. **Running `mypy` across the whole `tests/` directory (not just `tests/knowledge/`) surfaces 15 pre-existing errors** in Sprint 1's `test_pipeline_engine.py`/`test_event_bus.py`, never previously checked under strict mode (Sprint 1's own mypy invocation was scoped to `runtime/` only). *Why not fixed:* these files were not touched by Sprint 2 and fixing them would be unrelated-scope work; disclosed rather than silently left for a future discoverer. `knowledge/`, `plugins/`, and `tests/knowledge/` are independently 100% mypy-clean.

---

## 15. Design Decisions

1. **Never `StageOutcome.FAILURE` in any Validation gate; encode outcome in `artifact.status` instead.** See Limitation 1. Alternative considered and rejected: modifying `PipelineEngine` to preserve output on failure — rejected because it would violate "Do not modify Runtime."

2. **"Stopping" a halted artifact is implemented as idempotent pass-through, not Engine-level abort.** Every gate begins with `if artifact.status in _PASSES_THROUGH: return artifact, StageOutcome.SUCCESS`. This makes every gate independently composable and testable (a test can feed an already-`REJECTED` artifact directly to any gate and assert it comes back byte-identical) without needing the Engine to know anything about "halted" artifacts.

3. **Tag-facet convention for per-claim facts the frozen envelope has no field for.** `TAG_STAFF_AUTHORED`, `TAG_AFTER_DOCS_UPDATE`, `TAG_CONTRADICTS_STABLE_RULE`, `TAG_LOW_CONFIDENCE`, `pattern-candidate:<key>`, `anti-pattern-candidate:<key>` — all live in `artifact.tags` rather than as new envelope fields. Justification: `KNOWLEDGE_ARTIFACTS.md` §1 already defines `tags` as "kebab-case facets... for index grouping," and `KNOWLEDGE_EXTRACTION_SPEC.md` itself already uses the identical convention for `verified-fixed`/`interim-workaround`/`third-party-observed`. Alternative considered: extending `ArtifactEnvelope` with new typed fields — rejected as premature schema expansion for facts that may not generalize beyond this Sprint's specific gates.

4. **`PrecedenceProvider` and the conflict-relevant tags moved into `knowledge/conflict/` (not `knowledge/validation/`).** Both `knowledge/validation/gates.py` (Version Conflict Detection) and `knowledge/conflict/stage.py` (batch resolution) need the identical provider and tag constants. Placing them in `knowledge/validation/` would make `knowledge/conflict/` depend on `knowledge/validation/`, which already depends on `knowledge/conflict/` for `resolve_conflict` itself — a circular import. This was discovered mid-Sprint and fixed in commit `e387dc1` (a dedicated refactor commit, not folded silently into a feature commit).

5. **`ExtractorModule` owns the batch Conflict Resolution capability, not a dedicated "Conflict Resolution" module.** `docs/runtime/MODULE_SYSTEM.md` §5's domain-module table names no such module, and Extraction/Pattern Extraction already own the other two in-scope `knowledge.graph_build` stages. Alternative considered: a third, single-stage module — rejected as disproportionate (one capability, no independent state) and explicitly disclosed as a Sprint 2 judgment call in `extraction/module.py`'s docstring, not asserted as architecturally settled.

6. **Confidence formula split into a shared, pure function (`confidence.py`), called from both gate 7 (preview) and gate 8 (final).** `KNOWLEDGE_VALIDATION_SPEC.md` §7's condition 4 needs the §8 confidence score before §8 has run (gates execute in fixed 1→8 order). Rather than let gate 7 duplicate the formula (risking drift) or reordering gates (contradicting the fixed-order requirement), both gates call the identical `compute_confidence_for_artifact`.

7. **Frozen (immutable) artifact envelope; every transition via `model_copy(update=...)`.** Chosen to match `KNOWLEDGE_GRAPH_SPEC.md` §4's "append, never overwrite" discipline and Sprint 1's own precedent (`ModuleManifest`, `StageDefinition`, `PipelineContext` are all frozen dataclasses/models). Alternative (mutable envelope) was not seriously considered given this precedent.

8. **`IdAllocator` is per-process, per-instance state, not a global counter.** Each `ExtractorModule.init()` call constructs its own `IdAllocator`; nothing is shared across module instances or processes. Consistent with "no persistence layer this Sprint" — a real ID authority is future work, not simulated here.

9. **Schema construction is permissive; business rules live only in the gates.** `ArtifactEnvelope` enforces structural constraints (types, `confidence` range, `id`-prefix match) but not business rules like "must have ≥1 source reference." This directly follows from `KNOWLEDGE_VALIDATION_SPEC.md`'s "retained, not un-constructible" failure mode — an artifact that fails Schema Validation must still exist as a Python object afterward.

10. **Small, cohesive commits during active development**, superseding the earlier "exactly one commit per Sprint" standing rule for this specific execution round, per this round's explicit "Small cohesive commits" instruction. Six commits, each independently green (tests/mypy/ruff) before the next began.

---

## 16. Reviewer Focus

In priority order:

1. **The "never `StageOutcome.FAILURE`" decision (`knowledge/validation/gates.py`'s module docstring and every gate).** This is the single biggest structural choice in Sprint 2, made unilaterally against the Pipeline Engine's existing failure semantics. Confirm the reasoning (PipelineEngine drops `output` on `FAILURE`, contradicting "never deleted, always retained") is sound, and that no gate accidentally relies on Engine-level rollback/retry behavior it no longer gets by construction (e.g., `StageDefinition.rollback_capability` is never populated by either Sprint 2 `PipelineDefinition` — rollback is structurally unreachable for these two pipelines today).

2. **`PendingApprovalStore.resolve()` finalizing directly, instead of the plan's original "restart from Confidence Scoring."** A mid-implementation deviation from the written plan (Limitation 10). Confirm this is the right tradeoff versus building an actual resume-in-place mechanism.

3. **`ExtractorModule` owning `knowledge.resolve_conflicts_batch`.** A one-module-does-three-stages decision with no frozen-architecture backing either way (Design Decision 5). Decide now whether this is acceptable permanently or should be revisited when a real Knowledge Graph module is built (at which point a natural 4-stage "Knowledge Graph module" boundary might make more sense than the current 3+1 split).

4. **The tag-facet convention's growing surface area.** Six distinct tag meanings now live in `artifact.tags` (`low-confidence`, `staff-authored`, `authored-after-docs-update`, `contradicts-stable-rule`, `pattern-candidate:*`, `anti-pattern-candidate:*`). Still within the spec's own precedent, but worth a explicit decision on whether any of these should graduate to real envelope fields before Sprint 3 adds more.

5. **Trust Verification's narrowed demotion behavior (Limitation 2).** Confirm tag-only demotion is an acceptable interim reading of `KNOWLEDGE_VALIDATION_SPEC.md` §5, not a silent under-implementation that changes retrieval-time behavior in a way the spec didn't intend.

6. **The `_claim_identity`/`_claim_body` heuristic in Version Conflict Detection (`gates.py`).** Determining "same subject, different claim" via `content.name`/`content.title` plus a type-specific substantive-field tuple is a Sprint 2 invention with no direct spec citation for *how* to detect a claim collision (the spec says conflicts must be detected, not how identity/equality is computed). Worth checking against realistic extracted data shapes before this becomes load-bearing.

7. **`architect doctor --plugin-path plugins` failing without registered providers (Limitation 7).** Confirm this "fail loudly, no default" UX is the desired behavior going forward, versus wanting a documented way to supply fixture/demo providers via CLI or config for manual smoke-testing without writing a test.

8. **Whether `ArtifactStatus` (Design Decision assembling 6 values into one enum) needs a real architecture-review pass**, per the risk already flagged in `SPRINT2_IMPLEMENTATION_PLAN.md` §8 and repeated in this package's Limitation 8 — this package does not resolve that question, only re-surfaces it now that real code depends on the enum's exact shape.

9. **Test coverage gap:** no test exercises `knowledge.graph_build`'s `conflict_resolution` stage wired *through* `wired_engine`'s real `PluginRegistry` path end-to-end with a genuine `KnowledgeConflict` in the batch — `resolve_conflicts_in_batch` is only tested directly (`test_conflict_resolution.py`) or with an empty/conflict-free batch (`test_pipeline_integration.py`). This is a direct consequence of Limitation 5 (no producer yet) but is worth naming explicitly as a coverage gap, not just a feature gap.

---

**End of review package.** No implementation was modified while producing this document. No commit was made. Awaiting review.
