# ADR-001: Analysis → Knowledge → Intelligence Dependency Direction

**Date:** 2026-07-25
**Status:** Accepted

---

## 1. Context

### Original Strategic Realignment dependency

The Strategic Realignment (v1 §2, carried forward unchanged through v2–v4) specified `analysis/` as a *consumer* of Knowledge: the ERP Analyzer would query the ERP Knowledge Engine (`knowledge/erpnext/`'s `does_erpnext_provide()`, `find_extension_points()`, `is_protected()`) against an already-populated Knowledge Graph, and `analysis/`'s own `Recommendation.evidence` (v2 §7.1) was specified to carry a `knowledge_layer: KnowledgeLayer` field, tying every piece of evidence directly back to the Layered Knowledge Architecture (v2 §3). The documented dependency arrow was **Analysis → Knowledge**. v4's own roadmap (§15) sequenced this literally: Sprints 9–11 were to build Knowledge (ERP Core ingestion, the Knowledge Engine, Decision Rules integration) *before* Sprint 12's Analyzer, precisely so the Analyzer would have a real corpus to query from day one.

### Implemented Sprint 9 architecture

Sprint 9 built `analysis/` first, and built it fully self-contained: its own `SupportingEvidence` type (deliberately independent of, and simpler than, the `knowledge_layer`-bearing type v2 specified), its own deterministic ERPNext metadata extractor (`analysis/erpnext/`, structurally unrelated to Sprint 2's `knowledge/extraction` pipeline), and its own lexical similarity comparator (`analysis/similarity/`) comparing two locally-supplied fact sets with no reference to any graph. Every phase's own architecture-boundary tests confirm, executably, that `analysis/` imports nothing from `knowledge/` at all.

### Architecture Reconciliation findings

The [Architecture Reconciliation Report](ARCHITECTURE_RECONCILIATION_REPORT.md — prepared as a review artifact, not committed to this repository) identified this as the one architectural divergence, among thirteen found, that constitutes a genuine, unresolved fork rather than a safe-to-fold-in refinement: Sprint 9's independence from Knowledge is not a bug, but it does directly contradict the documented Analysis → Knowledge arrow, and the documents never anticipated or resolved which direction should now hold going forward. Two options were presented: adopt the implemented direction as the new design (Option A), or treat Sprint 9's independence as a temporary simplification to be retrofitted later toward the original direction (Option B). This ADR records the decision between them.

---

## 2. Decision

The project officially adopts the following dependency direction as authoritative, superseding the direction described in Strategic Realignment v1/v2:

```
Requirements
      ↓
  Analysis
      ↓
  Knowledge
      ↓
Intelligence
      ↓
  Planning
      ↓
 Execution
```

**Analysis** produces deterministic facts (`BusinessEntity`, `BusinessProcess`, `BusinessRule`, `BusinessConstraint`, `Actor`, `SimilarityResult`, `GapAnalysis` — Sprint 9, unchanged). **Knowledge** organizes those facts into reusable, accumulating knowledge — it is downstream of Analysis, not upstream of it. **Intelligence** reasons over what Knowledge organizes (Sprint 8, unchanged in its own contract — see Consequences for the one implication this has for `EvidenceItem`). Planning and Execution remain exactly as built in Sprints 4–7, unaffected by this decision.

---

## 3. Rationale

- **Deterministic Analysis.** Analysis's entire value, as built, rests on being provably deterministic and side-effect-free — 100% branch coverage, no hidden state, every fact traceable to a supplied excerpt. A component that queries a live, evolving Knowledge Graph mid-computation is harder to hold to that same standard than one that only ever transforms the inputs it was directly handed. Keeping Analysis upstream and knowledge-independent preserves the property that was actually delivered and tested through Sprint 9, rather than asking it to be rebuilt against a dependency it was never designed around.
- **Provider independence.** Neither Analysis nor Knowledge, in this ordering, needs to know anything about which `IntelligenceEngine` implementation exists downstream. Reversing the arrow (Knowledge feeding Analysis) would have made Analysis's own determinism conditional on whatever Knowledge happened to contain at query time — a form of hidden coupling this project has structurally avoided everywhere else (the same reasoning `intelligence/`'s own vendor-adapter isolation already rests on).
- **Reproducibility.** Analysis → Knowledge → Intelligence means a given Analysis run's output is reproducible independent of Knowledge's own state at any later time. Under the original direction, the same Analysis call could legitimately return different results as the Knowledge Graph grew — correct for a system that wants "smarter over time," but incompatible with the "identical input produces identical output" guarantee Sprint 9's own test suite was built to prove and enforce.
- **Separation of responsibilities.** This ordering gives each layer exactly one job with no overlap: Analysis extracts, Knowledge organizes/accumulates, Intelligence reasons. The original direction asked Analysis to do two things — extract facts *and* decide which existing knowledge they relate to — collapsing extraction and organization into one step.
- **Reusable Knowledge.** Because Knowledge now sits downstream of every Analysis run rather than upstream of one, every Analysis run becomes a potential *contributor* to Knowledge, not just a consumer of it — the natural shape for an accumulating asset that is meant to compound over time, consistent with "Knowledge is the Asset" (v3 §4).

---

## 4. Consequences

**Positive:**

- Sprint 9's `analysis/` package requires no rework. Its existing contracts, extractors, and comparator remain exactly as delivered — this decision ratifies what was already built rather than requiring a retrofit.
- Knowledge's own design (Sprint 10 onward) can be scoped cleanly as "given Analysis output, organize it" — a narrower, more concrete brief than "be a queryable oracle Analysis depends on before it can do anything."
- The dependency graph across the whole project remains a strict, acyclic chain — no layer needs to know about anything downstream of it, matching the "no domain imports another domain, except by name exception" discipline already enforced everywhere else (`orchestration/`, `analysis/`, `intelligence/`).

**Trade-offs:**

- Analysis's own comparisons (`analysis/similarity/`) do not benefit from Knowledge's accumulated, cross-layer corpus (Core/Ecosystem/Cross-Platform/Organization evidence, precedence-weighted) — each Analysis run only ever sees what is directly handed to it in that call. Any future desire for Analysis itself to reason over a broader corpus would require either a second, explicit query path back into Knowledge (a new, separate concern from this decision) or accepting that such reasoning belongs to Intelligence instead, not Analysis.
- `intelligence.contract.EvidenceItem` was already built generic, with no `knowledge_layer` field, because `intelligence/` predates this decision and was deliberately kept domain-agnostic. This decision does not change that — `EvidenceItem` remains the correct, generic shape Intelligence receives regardless of what Knowledge does; Knowledge's own richer internal representation is translated down to it at the boundary, the same pattern already established between `analysis.contract.SupportingEvidence` and `intelligence.contract.EvidenceItem`.

**Future implications:**

- Knowledge's own design must define, as its first real task, *how* it ingests `AnalysisResult`/`SimilarityResult`/`GapAnalysis` — this was not previously specified in any direction, since v1/v2 never described Knowledge consuming Analysis output at all.
- The Recommendation/`ReuseDecision` taxonomy (v2 §7.1, still unbuilt — see the Reconciliation Report) will need to be re-anchored: originally specified as consuming Analysis-plus-Knowledge-Graph evidence directly, it now more naturally sits downstream of Knowledge (or of Intelligence, once Intelligence reasons over what Knowledge organizes) rather than being built directly on top of Analysis's own output.
- Layer 5 (Decision Rules — the Rule Retrieval Index wrapper originally specified as `analysis/rules.py` in v2 §9) is re-scoped by this decision to belong to Knowledge, not Analysis — rules are exactly the kind of reusable, organized knowledge this layer now owns, not a fact Analysis itself extracts.

---

## 5. Rejected Alternative

**Option B — retain the original direction; treat Sprint 9's independence as a temporary simplification.**

Under this alternative, Sprint 9's `analysis/similarity/` would eventually be retrofitted to consult a populated Knowledge Graph instead of (or alongside) its current locally-supplied comparison, restoring the original Analysis → Knowledge arrow, with Sprint 9's comparator surviving only as a "no Knowledge available" fallback path.

**Why it was not adopted:**

- It would require reopening and modifying a fully-shipped, 100%-covered, already-frozen Sprint (Sprint 9) — direct tension with this project's own "prior sprints are frozen unless a genuine defect is found" discipline. Nothing about Sprint 9's own behavior is a defect; retrofitting it under Option B would be a redesign of working code to match a direction that was never actually implemented, not a bug fix.
- It reintroduces the exact dependency this decision's Rationale (§3) identifies as a real cost: Analysis's determinism becoming conditional on Knowledge's state at query time.
- It presupposes Knowledge will be populated with a real, queryable corpus before Analysis needs one — the same assumption v4's original roadmap made (Knowledge first, Sprints 9–11) that this project's own actual execution order already overtook. Adopting Option B now would mean sequencing Sprint 10 around restoring an ordering the project has already moved past, rather than building forward from where Sprint 9 actually left things.

---

## 6. Status

**Accepted.**
