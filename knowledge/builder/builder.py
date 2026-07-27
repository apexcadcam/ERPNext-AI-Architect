"""The deterministic Knowledge Builder — Sprint 10, Phase 2.

Implements ADR-001's "Knowledge consumes Analysis" mandate as pure,
deterministic functions: `analysis.contract.AnalysisResult` in,
`knowledge.domain` contracts out. No persistence, no indexing, no
querying, no graph implementation, no AI, no heuristics, no similarity
logic — every function here is a total, side-effect-free mapping that
never asserts a fact `AnalysisResult` did not already state.

**The one real design finding this phase surfaced, disclosed rather than
smoothed over:** Phase 1 reused `knowledge.artifacts.ContentArtifact`
(`KnowledgeAPI | Pattern | AntiPattern | BestPractice | Example |
Workflow`) for `KnowledgeCollection.artifacts`, on the reasoning that
Knowledge should not invent a parallel artifact model. Building this
Builder required checking that reuse against every one of the five
`analysis.contract` fact kinds individually, not assuming it would work
uniformly:

- **`BusinessProcess` → `Workflow`** — a genuine, honest fit. `Workflow`'s
  own content payload (`title`, ordered `WorkflowStep`s) is structurally
  identical to `BusinessProcess.name`/`.steps`. This is the only fact kind
  this Builder converts into a `ContentArtifact`.
- **`BusinessEntity`, `BusinessRule`, `BusinessConstraint`, `Actor` → no
  `ContentArtifact`.** Checked individually, not assumed: `Pattern`/
  `AntiPattern` require evidence "observed successfully across ≥2
  independent artifacts, never manufactured from a single anecdote"
  (`knowledge/artifacts/pattern.py`) — a single deterministically-extracted
  fact cannot honestly satisfy that bar. `BestPractice` is "a recommended,
  non-mandatory approach" — prescriptive advice, a different epistemic
  category from a `BusinessRule`, which is a descriptive fact about what a
  requirement or ERPNext instance already states. `Example` is explicitly
  "non-authoritative... of a Pattern/Knowledge API" — about another
  artifact, not a standalone fact. `KnowledgeDocument` is "closer to raw
  material than a claim," the *pre*-extraction staging unit — the reverse
  of what an already-structured Analysis fact is. Forcing any of these
  four fact kinds into one of these types would misrepresent it under an
  evidence bar or epistemic category that does not apply — worse than not
  representing it as a `ContentArtifact` at all. These four kinds are
  represented only via `KnowledgeReference` (Phase 1), which was built
  for exactly this — a pointer to an Analysis fact, not a claim about it.

**`.nodes`/`.edges` are always empty.** Beyond graph materialization
being explicitly out of this phase's scope, `GraphNode.wraps_type:
ArtifactType` has the identical enum-fit problem `ContentArtifact` does —
`ArtifactType` has no value for `business_entity`/`business_rule`/
`business_constraint`/`actor` either. A future, separately-scoped phase
that actually builds the graph is where that question is resolved, not
here.

**`created_at` is a required, caller-supplied parameter, never read from
a clock internally.** This is what makes "the same `AnalysisResult`
always produces byte-for-byte equivalent output" true by construction,
not by convention — the alternative already established in this project,
`planning.strategy.RuleBasedPlannerStrategy`'s own fixed
`_CREATED_AT_PLACEHOLDER` constant, was available and rejected here
specifically because that Sprint's function signature was already fixed
and approved with no room for an extra parameter; this Builder's
signature is being designed fresh, so requiring the real value from the
caller — never fabricating one — was the more honest option available.

**`source_references`, `provenance`, `dependencies`, and `relationships`
on the built `Workflow` are always empty.** `SourceReference` is shaped
for externally crawled content (`url`/`content_hash`/`span`) Analysis
facts never carry; fabricating one would violate "never infer information
that does not exist in `AnalysisResult`." Provenance back to Analysis is
carried entirely by `KnowledgeReference.analysis_id`, not by these
Sprint-2-shaped fields. `confidence` and `status` are left at their
documented defaults (`0.0`, `DRAFT`) for the same reason
`KNOWLEDGE_VALIDATION_SPEC.md §8` already states: confidence is the
Validator's output, never hand-set by extraction — and this Builder does
not run Validation.

**No deduplication.** Two `BusinessEntity` mentions sharing the same
`entity_id` (a legitimate, already-disclosed possibility per Sprint 9's
own requirement analyzer) produce two separate `KnowledgeReference`
objects here, unmerged. Deciding two facts denote "the same" thing is a
judgment call — inference — this Builder is not permitted to make.

Imports only `analysis.contract` and `knowledge.artifacts`/`knowledge.
domain` (this project's own, frozen packages). No `intelligence`,
`planning`, `execution`, `runtime`, `orchestration`, or `integration`. No
graph library, no database SDK, no provider SDK, no networking.
"""

from __future__ import annotations

from analysis.contract import AnalysisResult
from knowledge.artifacts import ArtifactMetadata, ArtifactVersionInfo, Workflow, WorkflowContent, WorkflowStep
from knowledge.domain import KnowledgeCollection, KnowledgeReference, KnowledgeSnapshot

#: Disclosed, fixed constants describing this Builder's own identity as an
#: extraction method — never a claim about *when* it ran (see `created_at`).
_EXTRACTION_METHOD = "knowledge.builder:analysis_result"
_EXTRACTOR_VERSION = "0.1.0"


def _reference(analysis_result: AnalysisResult, subject_id: str, subject_kind: str) -> KnowledgeReference:
    return KnowledgeReference(
        analysis_id=analysis_result.analysis_id,
        subject_id=subject_id,
        subject_kind=subject_kind,  # type: ignore[arg-type]
    )


def build_entity_references(analysis_result: AnalysisResult) -> tuple[KnowledgeReference, ...]:
    return tuple(
        _reference(analysis_result, entity.entity_id, "business_entity")
        for entity in analysis_result.requirement_analysis.entities
    )


def build_process_references(analysis_result: AnalysisResult) -> tuple[KnowledgeReference, ...]:
    return tuple(
        _reference(analysis_result, process.process_id, "business_process")
        for process in analysis_result.requirement_analysis.processes
    )


def build_rule_references(analysis_result: AnalysisResult) -> tuple[KnowledgeReference, ...]:
    return tuple(
        _reference(analysis_result, rule.rule_id, "business_rule")
        for rule in analysis_result.requirement_analysis.rules
    )


def build_constraint_references(analysis_result: AnalysisResult) -> tuple[KnowledgeReference, ...]:
    return tuple(
        _reference(analysis_result, constraint.constraint_id, "business_constraint")
        for constraint in analysis_result.requirement_analysis.constraints
    )


def build_actor_references(analysis_result: AnalysisResult) -> tuple[KnowledgeReference, ...]:
    return tuple(
        _reference(analysis_result, actor.actor_id, "actor")
        for actor in analysis_result.requirement_analysis.actors
    )


def build_workflow_artifacts(analysis_result: AnalysisResult, *, created_at: str) -> tuple[Workflow, ...]:
    """The one Analysis fact kind with a genuine `ContentArtifact` fit —
    see this module's own docstring for why the other four do not.
    """

    workflows = []
    for process in analysis_result.requirement_analysis.processes:
        steps = tuple(
            WorkflowStep(order=index, description=description)
            for index, description in enumerate(process.steps)
        )
        workflows.append(
            Workflow(
                id=f"WF-{process.process_id}",
                metadata=ArtifactMetadata(
                    extracted_at=created_at,
                    extraction_method=_EXTRACTION_METHOD,
                    extractor_version=_EXTRACTOR_VERSION,
                ),
                version=ArtifactVersionInfo(),
                content=WorkflowContent(title=process.name, steps=steps),
            )
        )
    return tuple(workflows)


def build_knowledge_collection(analysis_result: AnalysisResult, *, created_at: str) -> KnowledgeCollection:
    references = (
        build_entity_references(analysis_result)
        + build_process_references(analysis_result)
        + build_rule_references(analysis_result)
        + build_constraint_references(analysis_result)
        + build_actor_references(analysis_result)
    )
    return KnowledgeCollection(
        collection_id=f"collection:{analysis_result.analysis_id}",
        name=analysis_result.requirement_id,
        artifacts=build_workflow_artifacts(analysis_result, created_at=created_at),
        references=references,
    )


def build_knowledge_snapshot(analysis_result: AnalysisResult, *, created_at: str) -> KnowledgeSnapshot:
    """Consumes one `AnalysisResult`, produces one `KnowledgeSnapshot` —
    this Builder's sole top-level entry point.
    """

    return KnowledgeSnapshot(
        snapshot_id=f"snapshot:{analysis_result.analysis_id}",
        created_at=created_at,
        source=analysis_result,
        collections=(build_knowledge_collection(analysis_result, created_at=created_at),),
    )
