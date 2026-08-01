# INHERITANCE RESOLUTION — ARCHITECTURE SPECIFICATION

**Sprint:** 22
**Version:** 1.0
**Status:** Implemented, including the Commit 7 correction in §4.4. Sections marked *(final)* record decisions settled during implementation.
**Decides:** how the `controller_lifecycle_hook` population becomes derivable
**Governed by:** [ADR-0015](../../adr/ADR-0015-cross-repository-inheritance-resolution.md) · **Evidence from:** [RQ-0002](../../research/RQ-0002-controller-lifecycle-hook-population.md)

---

## 0. What this Sprint is

The platform has carried one declared, unmeasurable category since `v1.2.0`. 713 Evidence records — 237 in `frappe`, 476 in `erpnext` — are collected and cannot be turned into a measurement, because the collector emits a record only where a hook is *found*, so classes without hooks leave no trace. The numerator exists; the denominator does not.

This Sprint supplies the denominator. It adds Evidence describing class definitions and their declared bases, a component that resolves descent from those raw facts, and the two contract changes that let a population be resolved using more corpora than the one being measured.

**It is an addition, not a modification.** §8 makes that testable rather than aspirational.

## 1. Sequence

```
  ┌─────────────────────────────────────────────────────────────┐
  │ EXTRACTION — one repository, no knowledge of any other       │
  └─────────────────────────────────────────────────────────────┘

        class_definition_collector       (new, §2 §3)
                    │
                    │  raw facts only: "this class exists",
                    │  "this class declares this base name"
                    ▼
              EvidenceSet(erpnext)          EvidenceSet(frappe)
                    │                              │
                    └──────────────┬───────────────┘
                                   │
  ┌────────────────────────────────┼────────────────────────────┐
  │ AGGREGATION                    │                            │
  └────────────────────────────────┼────────────────────────────┘
                                   ▼
                          AggregationRequest             (§5)
                            evidence_set          = erpnext   ← the subject
                            supporting_evidence_sets = (frappe,) ← context only
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ INHERITANCE RESOLVER  │           (§4)
                       │ nodes + edges → graph │   an independent component:
                       │ descent, transitively │   knows classes, not Patterns
                       └───────────────────────┘
                                   │
                     ClassDescentResult ─────────────┐
                       resolved / unresolved         │
                                   │                 │
                                   ▼                 │
                          population resolver        │  (existing dispatch, §4.3)
                                   │                 │
                                   ▼                 ▼
                              Population      resolution provenance
                                   │                 │
                                   └────────┬────────┘
                                            ▼
                                        PatternSet                 (§6)
                                  patterns + provenance of
                                  how the denominator was reached
```

Read the diagram for one thing above all: **the arrow into the Resolver carries facts, and the arrow out carries an inference.** That boundary is the Sprint.

## 2. Evidence Contract

### 2.1 Two categories, where the brief said one

**A deviation, stated before anything else, because the rest of the design rests on it.**

The approved scope says "the new Evidence category", singular. This specification proposes **two**, and the reason is the bug being fixed.

A single category recording "class X declares base B" emits nothing for a class that declares no base. Classes with no bases would leave no trace — which is *precisely* the failure that made the lifecycle-hook population underivable in the first place. Reproducing it one level up, inside the fix for it, would be a poor trade for a smaller enum.

So the node set and the edge set are recorded separately:

| Category | One record means | Emitted for |
|---|---|---|
| `class_definition` | "a class by this name is defined here" | **Every** class, without exception, including classes with no bases |
| `class_base_declaration` | "that class declares this name among its bases" | Each base, one record per base |

`class Customer(Document, NestedSet)` therefore produces **three** records: one definition, two base declarations. `class Foo:` produces exactly one. The invariant that matters — *every class produces at least one record* — is structural rather than remembered.

### 2.2 Field mapping

Both categories reuse the existing `Evidence` shape unchanged. No field is added to `Evidence` (§7).

| Field | `class_definition` | `class_base_declaration` |
|---|---|---|
| `kind` | `implementation` | `implementation` |
| `category` | `class_definition` | `class_base_declaration` |
| `symbol` | `<module>.<ClassName>` | `<module>.<ClassName>` — the class doing the declaring |
| `subject` | `<ClassName>` | the base **exactly as written in the source** |
| `source` | repository, version, commit, path, line of the `class` statement | same |
| `collector` | `class_definition_collector` | `class_definition_collector` |

**`subject` on a base declaration is the source text, not a resolved reference.** `class X(Document)` records `Document`; `class X(frappe.model.document.Document)` records `frappe.model.document.Document`. Both forms occur in the real trees. Normalising them is an inference and belongs to §4.

### 2.3 The symbol format is a join key, not a display string

The lifecycle-hook collector already emits `symbol` as `<module>.<Class>.<hook>` — verified against the committed corpus:

```json
{"category": "controller_lifecycle_hook",
 "symbol": "erpnext.accounts.custom.address.ERPNextAddress.validate",
 "subject": "validate"}
```

The class identity inside a hook record is that symbol with its final segment removed. **The new collector must produce byte-identical class symbols**, using the same `_module_dotted_name` helper, or the numerator and denominator will fail to join — and they will fail *silently*, as a population that looks plausible and is wrong.

This is the single most likely way to get a wrong number out of this Sprint, so §8 requires a test that asserts the two collectors agree, rather than trusting that they will.

### 2.4 Two new `CollectorName` values? No — one

`CollectorName` gains exactly one member, `class_definition_collector`, emitting both categories. One pass over the AST produces both a definition record and its base records; splitting that into two collectors would walk the same tree twice to produce facts that are only meaningful together.

### 2.5 Rationale

Recorded here because [R009](../../rules/R009-yagni-no-speculative-infrastructure.md) forbids speculative structure, and every field above has a named consumer in §4:

- `class_definition` records are the resolver's **nodes** — the set the population is drawn from.
- `class_base_declaration` records are its **edges**.
- `subject` as written is what lets the resolver's matching rule change later without re-extracting a corpus.

Nothing is recorded that §4 does not consume. There is no `is_document_subclass`, no `resolved_base`, no `depth`, no `is_abstract`, and no `doctype` field — every one of those is an inference, and ADR-0015 places inferences downstream.

## 3. Collector Design

### 3.1 Entry point

```python
def collect_class_definition_evidence(context: _FileContext, tree: ast.Module) -> list[Evidence]
```

Identical in shape to the two existing collectors, registered the same way, called from the same `_collect_from_file` loop. It receives one parsed module and returns records in source order.

### 3.2 What it collects

Every `ast.ClassDef` the hook collector could also attribute a method to, and:

- one `class_definition` record per class;
- one `class_base_declaration` record per entry in `ClassDef.bases`, in written order;
- the base name reduced to source text: `Name → id`, `Attribute → full dotted text as written`.

**Nesting reach matches the hook collector exactly.** `_class_membership` attributes methods one level deep and deliberately not inside doubly-nested classes. If the definition collector reached deeper, the denominator would contain classes the numerator can never mention — a silent deflation of support. §8 requires the two reaches to be asserted equal.

### 3.3 What it refuses to collect

- **Base expressions that are not a name or a dotted name** — a subscript, a call, a comprehension. RQ-0002 measured zero of these across 1,938 class definitions in both repositories, so this is a guard rather than a live case. It is refused rather than approximated: recording `<dynamic>` would put a token into the corpus that looks like a base name and is not one. Refusal must be **visible**, via the existing `EvidenceExtractionError` channel, never a silent skip.
- **Anything outside the repository under extraction.** The collector reads one file at a time and has no cross-file, let alone cross-repository, view.

### 3.4 Non-goals

**Binding, and the reason this section exists: everything below is something an implementer will be tempted to add because it seems helpful, and each would move an inference upstream of the evidence it is supposed to be inferred from.**

The collector:

1. **Does not resolve inheritance.** It never determines whether a class descends from `Document`. Reading `class SalesInvoice(SellingController)`, it genuinely does not know — and a collector that guesses is one that can be wrong in a way nothing downstream can detect.
2. **Does not look outside its own repository**, or outside the file in front of it.
3. **Does not compute or contribute to any population.** It emits facts; §4.3 counts.
4. **Does not distinguish a controller from any other class.** `ValidationError` subclasses, mixins, test helpers, and DocType controllers are recorded identically. RQ-0002 found 85 `ValidationError` subclasses inside ERPNext's DocType controller files — filtering by file location or by name would have admitted every one of them. **Filtering is the resolver's job, using resolved descent, not the collector's, using a heuristic.**
5. **Does not import or execute anything.** Static parse only, as with every existing collector.
6. **Does not normalise base names.** `Document` and `frappe.model.document.Document` are recorded as written and reconciled in §4.2.

## 4. Resolver Design

Per the approved scope, the resolver is specified as an **independent component with its own boundary**, not as a step inside aggregation — because it is an independent responsibility. It answers one question about a class graph and knows nothing about Patterns, support, thresholds, or repositories-as-subjects.

**Proposed location:** `aggregation/inheritance.py` — a sibling of `population.py` and `resolvers.py`, not a section inside `engine.py`.

```
aggregation/inheritance.py   ← this component: classes and descent
aggregation/resolvers.py     ← existing: population per category, now a consumer of the above
aggregation/engine.py        ← existing: patterns, thresholds, skips
```

### 4.1 Interface

```python
def resolve_descent(
    definitions: tuple[Evidence, ...],   # class_definition records, all corpora
    declarations: tuple[Evidence, ...],  # class_base_declaration records, all corpora
    *,
    root: str,                           # e.g. "Document"
) -> ClassDescentResult
```

Pure, deterministic, no I/O, no filesystem, no clock. Given the same records it returns the same result, which makes it testable in isolation from any repository.

```python
class ClassDescentResult(BaseModel):     # frozen, extra="forbid"
    descendants: tuple[str, ...]         # qualified symbols that descend from `root`
    unresolved_bases: tuple[str, ...]    # base names matching no known definition
    max_depth: int
```

### 4.2 Rules

1. **Matching is by final dotted segment.** `Document`, `frappe.model.document.Document`, and `document.Document` all match a definition whose class name is `Document`. This is the one normalising inference in the design, and it lives here rather than in the collector precisely so it can be changed without re-extracting a corpus.
2. **Descent is transitive, to full depth.** RQ-0002 measured chains reaching depth 6 in ERPNext; a single-level check would miss 37 of its 62 transitive controllers.
3. **Cycles terminate.** A visited-set guard is mandatory. RQ-0002 observed no cycles in either repository, but the resolver consumes persisted records that a future corpus or a hand-edited artifact could make cyclic, and unbounded recursion is not an acceptable response to bad input.
4. **Ambiguity resolves to descent.** If two definitions share a final segment and either descends from the root, the referring class is treated as descending. Stated so the behaviour is chosen rather than emergent; the alternative — refusing ambiguous names — would discard real controllers to avoid a rare false positive.
5. **`unresolved_bases` is reported, never swallowed.** A base naming nothing in any supplied corpus (`object`, `Exception`, a third-party class) is normal and expected. It is returned so a caller can see the residue, in the same spirit as `SkippedAggregation`.

### 4.3 How the population resolver consumes it

`POPULATION_RESOLVERS` gains an entry for `CONTROLLER_LIFECYCLE_HOOK` whose population is `len(result.descendants)` for `root="Document"`, **counting only descendants whose symbol belongs to the measured corpus** — supporting corpora resolve descent, they never join the population (§5.2).

`POPULATION_BASES` moves that category from `skipped_no_population` to `aggregated`, and its `blocker` text is removed rather than edited.

### 4.4 The membership invariant *(final — Commit 7)*

**Supplying the denominator is only half of a valid measurement. The numerator must be drawn from that same denominator.**

```
occurrence_symbols ⊆ population_symbols
    ⇒  0 ≤ occurrences ≤ population
    ⇒  0 ≤ support ≤ 1
```

For `CONTROLLER_LIFECYCLE_HOOK`, a lifecycle record contributes to the numerator **only when its owning class is a member of the resolved `Document`-descendant population**.

**Why this is not automatic.** A hook record states that a class defines a method whose *name* is a lifecycle hook name. That is not proof the class is a Frappe controller — any class may define a method called `validate` or `on_update`, and many do for entirely unrelated reasons. The collector cannot tell the difference, and §3.4 says it must not try: `class_definition` records exist precisely so the distinction is drawn later, from the resolved graph.

**Why it matters.** Without the restriction, `occurrences` counted distinct symbols across *every* lifecycle record while `population` counted resolved descendants — two different sets. A ratio between different populations is not a share of anything: silently inflated where the numerator is small relative to the denominator, and **invalid outright** where it is not. Both were observed: `frappe`'s `validate` read `87/275` against an aligned figure of `84/275`, and a corpus small enough produced `occurrences > population`, failing `Pattern.support`'s own `le=1.0` constraint.

**Clamping is forbidden.** Capping a support above `1.0` back to `1.0` would satisfy the constraint while leaving the measurement wrong, and would convert a loud failure into a quiet one. Membership is corrected instead — the numerator is narrowed, never the result.

Enforced by construction before any grouping happens, through a registry parallel to the population dispatch. Full statement of the rule and its scope: **[Aggregation §5.1](PATTERN_AGGREGATION_SPECIFICATION.md)**; the decision and how it was found: **[D18](../DECISION_LOG.md)**.

## 5. Aggregation Contract Changes

### 5.1 `AggregationRequest`

```python
evidence_set: EvidenceSet                                # unchanged — the subject
supporting_evidence_sets: tuple[EvidenceSet, ...] = ()   # new — resolution context only
```

### 5.2 The line this specification is built around

> **A supporting corpus contributes class definitions used to resolve inheritance, and nothing else.**

It never contributes:

- an **occurrence** — no `Pattern.occurrences` counts a symbol from a supporting corpus;
- **population membership** — `frappe`'s 275 controllers are not part of ERPNext's 510;
- **Pattern ownership** — no `Pattern` is produced for a supporting corpus, and `PatternSet.repository` remains the subject's.

`frappe`'s `NestedSet` explains *why* an ERPNext class is a controller. It does not thereby become one of ERPNext's. Merging the two corpora would produce cross-repository Patterns, which [Aggregation §4](PATTERN_AGGREGATION_SPECIFICATION.md) forbids because the populations are differently constituted.

§8 makes this a test, not a promise.

### 5.3 Category accounting *(final)*

Settled in Commit 5, and now enforced by a validator on
`AggregationStatistics` rather than left to be noticed:

| Statistic | Counts |
|---|---|
| `categories_present` | Evidence categories treated as candidates for measurement — every category in the `EvidenceSet` **except the structural ones** |
| `categories_aggregated` | Of those, the ones that produced a measurement |
| `categories_skipped` | Of those, the ones that could not |
| `evidence_records_consumed` | **Every** record read, structural included |

`aggregated + skipped == present` always holds. Structural categories sit
outside the accounting entirely — neither present, nor aggregated, nor
skipped. Counting them as present while excluding them from the other two
would break the invariant; counting them as skipped would assert "we
could not measure this" when nobody tried, because there is nothing there
to measure. **A declared gap that is not a gap devalues the ones that
are.**

`evidence_records_consumed` is deliberately not narrowed the same way:
those records were read, and the populations depend on them.

### 5.4 Validation

- A supporting corpus whose `repository` equals the subject's is rejected. Supplying `erpnext` as its own context is a caller error, not a no-op.
- Duplicate supporting corpora are rejected.
- An empty tuple is valid and is the default: single-corpus aggregation keeps working exactly as it does today.

## 6. `PatternSet` Changes — Provenance of Population Resolution

### 6.1 Why

**510 and 492 are both defensible ERPNext populations. They differ only by what was supplied.** A stored `PatternSet` that does not record which corpora contributed is one whose central figure cannot be reproduced or audited — and this platform's whole claim is that its figures can be.

### 6.2 Shape

```python
class ResolutionProvenance(BaseModel):       # frozen, extra="forbid"
    measured_corpus: CorpusRef               # repository, version, commit
    supporting_corpora: tuple[CorpusRef, ...]
    strategy: ResolutionStrategy             # closed enum
    unresolved_bases_count: int
```

`ResolutionStrategy` is closed, with exactly two members for now:

| Value | Meaning |
|---|---|
| `single_corpus` | Descent resolved from the measured corpus alone |
| `multi_corpus` | Descent resolved across the measured corpus plus supporting corpora |

Carried on `PatternSet` and persisted in the metadata sidecar. A reader can then tell a 492 from a 510 without re-running anything.

### 6.3 `unresolved_bases_count` is measured-repository scoped *(final)*

Settled in Commit 5. The residue counts base names **declared by the
measured corpus** that match no class definition in any supplied corpus.

Resolution still consults every corpus — a name counts as unresolved only
when nothing anywhere defines it — but **attribution is narrowed to the
measured repository**, for the same reason `descendants` is (§5.2).
`frappe`'s own external bases (`ABC`, `Enum`, `Criterion`) are not
ERPNext's residue.

Without this, the diagnostic grew as more context was supplied: ERPNext
reported 11 alone and 40 with `frappe`, of which 29 were frappe's. It now
reports 4 with `frappe` supplied — its own residue, after the supporting
corpus resolved names that were previously unmatched. **Supplying context
can only ever shrink the residue, never grow it**, which is the property a
reader would assume and is now asserted by test.

### 6.4 When provenance is absent *(final)*

`None` means "no population in this artifact was derived from the class
graph" — a statement, not a missing value. It is set only when a
descent-derived category was actually aggregated, so a whitelist-only
artifact carries no provenance because none was needed.

## 7. Schema Version

**Both schema versions move to `2.0`.** Written out rather than left implicit, since the approved scope asks for exactly this. *(Sprint 22's move. Both have since moved to `3.0` in Sprint 24, on the same rule: `CanonicalRepository` gained `hrms`.)*

### 7.1 Why it increases

- **Evidence:** `EvidenceCategory` and `CollectorName` gain members, so a `2.0` file can contain `category` values a `1.0` reader has never seen.
- **Pattern:** `PatternSet` gains a `ResolutionProvenance` field, so the metadata sidecar gains a key.

### 7.2 Is it backward compatible?

**Two directions, two different answers, and only one of them is safe.**

| Direction | Result |
|---|---|
| **New reader, old (`1.0`) artifact** | ✅ Works. Every new field is optional or defaulted; a `1.0` Evidence file contains only categories the new reader still knows. |
| **Old reader, new (`2.0`) artifact** | ❌ **Rejects, loudly.** `Evidence` is `extra="forbid"` and `EvidenceCategory` is a closed enum, so a `class_definition` record fails validation and `read_evidence_set` raises `EvidenceError_`. A `PatternSet` sidecar with an unknown key fails the same way. |

Loud rejection is the correct outcome and is already the behaviour — no work is required to obtain it. An old reader silently ignoring the new categories would compute a population from a partial corpus and report it as if complete.

### 7.3 Does it need a migration?

**No migration in the sense of transforming stored files.** The committed corpus is regenerated by re-running extraction, which is cheap (46,296 files in well under a minute) and reproducible. Both `evidence-data/` and `pattern-data/` are re-extracted, re-aggregated and re-committed together, in one commit, so no intermediate state exists in which a `1.0` Evidence file sits beside a `2.0` Pattern file.

### 7.4 A finding that belongs in this section

**`schema_version` is currently written but never checked.** Both engines stamp it and both persistence layers store it; no reader compares it to anything. Grepped across the repository: the only equality checks live in four tests.

So today a version bump is a **label, not a gate** — an old reader rejects a `2.0` artifact because of `extra="forbid"` and the closed enum, which is the right outcome reached for an incidental reason rather than because the version said so.

This specification does **not** add version enforcement — that is out of the approved scope, and a reader that rejects for the right reason is not more correct today than one that rejects for the wrong reason. It is recorded so the gap is a known one rather than an assumed guarantee, and it is proposed as a backlog item rather than smuggled in here.

## 8. Regression Specification

Split as the approved scope requires. **These two sections together are what proves Sprint 22 is an addition and not a modification.**

### 8.1 Regression — nothing that exists today may move

Asserted against the committed `v1.3.0` corpus:

| Invariant | Expected |
|---|---|
| `frappe` — `frappe.whitelist` | **518 / 520** |
| `frappe` — `frappe.validate_and_sanitize_search_inputs` | **15 / 520** |
| `erpnext` — `frappe.whitelist` | **705 / 705** |
| `erpnext` — `frappe.validate_and_sanitize_search_inputs` | **59 / 705** |
| Every existing `pattern_id` | unchanged — the hash covers repository, version, commit, category, subject, none of which change |
| Every existing `evidence_id` | unchanged — new records are added; none of the old ones move |
| Pattern ordering within `whitelisted_api_decoration` | unchanged |
| `observed_below_threshold` for that category | unchanged |
| Single-corpus aggregation, no supporting sets | behaves exactly as `v1.3.0` |

**Any drift here is a defect in the new work, not a discovery about the corpus.**

### 8.2 Expansion — only the new category may add

| Quantity | Before | After |
|---|---|---|
| Measured lifecycle-hook Patterns | 0 | 7 (frappe), 11 (erpnext) |
| `categories_present` | 2 | **2** |
| `categories_aggregated` | 1 | **2** |
| `categories_skipped` | 1 | **0** |
| `SkippedAggregation` entries | 1 | **0** |
| `erpnext` lifecycle-hook population | — | **510**, with `frappe` supplied |
| `erpnext` lifecycle-hook population | — | 492, without |
| `frappe` lifecycle-hook population | — | **275**, unaffected by supporting corpora |

Both ERPNext rows are listed deliberately: the difference between them **is** the feature, and a test that only ever supplies both corpora would not detect a resolver that silently ignores supporting sets.

### 8.3 Integration invariants

Beyond before/after numbers, three properties that would otherwise fail silently:

1. **Symbol join.** Every `controller_lifecycle_hook` symbol, with its final segment removed, matches a `class_definition` symbol in the same corpus. A single mismatch means the numerator and denominator describe different things.

   **The join alone is not sufficient** (§4.4). Matching a class *definition* only proves the class exists; it does not prove the class is in the *population*. Both are required, and Commit 7 added the second.
2. **Collector reach parity.** The set of classes the definition collector emits equals the set the hook collector can attribute a method to.
3. **Supporting-corpus containment.** No `Pattern` in a `PatternSet` has a `supporting_evidence_id` originating in a supporting corpus, and no population count includes a symbol from one.

### 8.4 The SKIPPED entry disappears because it was earned

When `categories_skipped` reaches 0, `architect patterns aggregate` will print `SKIPPED (none)`. That must happen because the denominator now exists — never because the entry was removed from `POPULATION_BASES` ahead of the resolver that justifies it. §8.2's population rows are what distinguish the two.

## 9. Rejected Alternatives

Recorded so the reasoning survives the decision, per the approved scope.

### 9.1 Option 1 — resolve ancestry at extraction time

Each class-definition record would carry a resolved `is_document_subclass` verdict computed while the extractor still held the tree.

**Rejected.** It puts an inference inside a record whose entire contract is to state a fact, and the inference is then frozen into the artifact — recomputing it later, under a better matching rule, would require re-extracting the corpus rather than re-running a resolver. Worse, it would make extracting `erpnext` depend on `frappe` being present and checked out, so the same repository at the same commit could yield different Evidence on two machines. That is the opposite of reproducible, and reproducibility is the property this platform is built to defend.

### 9.2 Option 3 — resolve per repository and declare the residue

Aggregate the 492 that resolve in isolation and emit a `SkippedAggregation`-style disclosure for the 18 that do not.

**Not adopted**, though it is the closest to how the platform already behaves — and that closeness is exactly what makes it tempting.

The difference is what is known. Declaring "we cannot measure this" was honest in `v1.2.0` because it was true; the denominator genuinely was not derivable. It is derivable now, and RQ-0002 measured the exact size of what would be discarded: 3.5%. **Disclosing an unknown and disclosing a known undercount are not the same act.** A platform that ships the second while capable of the first has redefined disclosure as an excuse.

### 9.3 Merge corpora into one `EvidenceSet`

The obvious reading of "aggregate over a set of `EvidenceSet`s": take a collection, concatenate, aggregate.

**Rejected.** It produces Patterns spanning two repositories, which Aggregation §4 forbids because the populations are differently constituted — and it would silently redefine `PatternSet.repository`. §5.2's subject/context split exists to make this un-representable rather than merely discouraged.

### 9.4 One Evidence category instead of two

Covered in §2.1. Rejected because a class with no declared bases would emit no record, reproducing inside the fix the exact blind spot being fixed.

### 9.5 Use DocType JSON definitions as the population

Superficially attractive: DocTypes are what a Frappe developer thinks in.

**Rejected on measurement.** RQ-0002 found the sets differ in both directions — `frappe` has 275 controllers against 266 DocType definitions, `erpnext` 510 against 501 — because abstract intermediates like `AccountsController` are `Document` subclasses with no DocType, and because the two are simply different things. A lifecycle hook lives on a class. Counting DocTypes would be a different quantity wearing the population's name, which is the specific error §5 of the Aggregation specification exists to prevent.

## 10. Out of Scope

- **Extending `CanonicalRepository`** ([W3](BACKLOG.md#w3--hrms-support)). This Sprint builds the mechanism `hrms` will need; it does not add `hrms`, and it does not settle framework-versus-consumer.
  > **Closed in Sprint 24.** The mechanism this Sprint built turned out to be exactly what `hrms` needed, and nothing more was required of the resolver: it was measured running unmodified across three corpora. Framework-versus-consumer was never settled — [ADR-0016](../../adr/ADR-0016-no-automated-candidate-formation.md) removed it as a producer question, and [ADR-0017](../../adr/ADR-0017-canonical-repository-admission.md) replaced it with a measured supporting-corpus closure. See [W3](BACKLOG.md#w3--hrms-support).
- **Cross-repository comparison.** Still undefined, still no command surface.
- **`schema_version` enforcement** (§7.4) — recorded as a finding, proposed for the backlog.
- **Any second root beyond `Document`.** `resolve_descent` takes `root` as a parameter because the resolver has no reason to hardcode one, not because a second root is planned.
- **Any Rule.** A Rule about controller inheritance may become possible once hook-implementation rates can be measured — which is what this Sprint enables, not what it delivers.

## 11. Deliverable

```
architect patterns aggregate erpnext --version v15.102.0 --supporting frappe:v15.103.1
architect patterns report erpnext --version v15.102.0
```

…and the `SKIPPED` section is empty, because the platform can now measure what it has been declaring it could not.
