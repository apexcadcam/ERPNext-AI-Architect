"""Deterministic Similarity Analysis — Sprint 9, Phase 4.

Implements the approved Sprint 9 brief's Phase 4 objective: compare
`RequirementAnalysis` (Phase 3) against ERPNext-derived Analysis
artifacts (Phase 2) — or, more precisely, compare any two same-typed
tuples of `analysis.contract` objects, since both phases already produce
the identical canonical shapes. No inference, no semantic AI, no
embeddings, no vector search, no LLM.

**The algorithm, disclosed in full:** every comparison is a Jaccard
similarity over lowercase, alphanumeric-tokenized text — `name` for
`BusinessEntity`/`BusinessProcess`/`Actor`, `statement` for `BusinessRule`/
`BusinessConstraint`. `similarity_score = |tokens_a ∩ tokens_b| /
|tokens_a ∪ tokens_b|`, `0.0` when both token sets are empty (undefined
overlap, never treated as a match). This is deliberately shallow and
lexical, not semantic — "Patient" and "Customer" share no tokens and will
always score `0.0` here, even though a human (or this project's own
`intelligence/`) might reasonably judge them related. That is not a defect
in this module; it is the precise boundary this Sprint draws between
Analysis (deterministic fact comparison) and Intelligence (judgment) —
recognizing that kind of relationship is exactly the reasoning task
`intelligence.contract.IntelligenceEngine` exists for, and this module
must not attempt it.

**Gap detection threshold, disclosed and justified:** a subject is a gap
when the *maximum* similarity score across every candidate it was
compared against is exactly `0.0` — including the case of zero candidates
supplied at all. No other threshold is used, because any nonzero cutoff
(e.g. "below 0.3 counts as a gap") would itself be a judgment call this
deterministic phase is not authorized to make; "shares literally no term
with anything" is the one gap rule with no arbitrary constant in it.

**`GapAnalysis.supporting_evidence` is never fabricated** — it is always
the subject's own already-real `supporting_evidence`, produced by
whichever earlier phase (2 or 3) extracted that subject in the first
place. This module adds no new evidence of its own; it only observes an
absence.

**Disclosed content gap, not a design gap:** `analysis.erpnext.extractor`
(Phase 2) produces no `Actor` or `BusinessConstraint` instances — a gap
already disclosed there. `compare_actors`/`compare_business_constraints`
and their gap-detection counterparts are nonetheless fully implemented and
tested here, using directly-constructed fixture instances standing in for
the ERPNext side, so the comparison capability is complete for all five
supported kinds regardless of how far Phase 2's own extraction breadth has
grown.

Imports nothing beyond `analysis.contract` (a sibling package) and the
standard library: no `intelligence`, `planning`, `execution`, `runtime`,
`knowledge`, `orchestration`, or `integration`. No network, no provider
SDK.
"""

from __future__ import annotations

import re

from analysis.contract import (
    Actor,
    AnalysisResult,
    BusinessConstraint,
    BusinessEntity,
    BusinessProcess,
    BusinessRule,
    GapAnalysis,
    SimilarityResult,
    SupportingEvidence,
)

_TOKEN_PATTERN = re.compile(r"[^a-z0-9]+")


def _tokens(text: str) -> frozenset[str]:
    return frozenset(token for token in _TOKEN_PATTERN.split(text.lower()) if token)


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    tokens_a = _tokens(text_a)
    tokens_b = _tokens(text_b)
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)


def _rationale(text_a: str, text_b: str, score: float) -> str:
    shared = sorted(_tokens(text_a) & _tokens(text_b))
    if shared:
        return f"shared terms: {', '.join(shared)} (Jaccard similarity {score:.4f})"
    return f"no shared terms between '{text_a}' and '{text_b}' (Jaccard similarity {score:.4f})"


def _compare_pairs(
    subject_ids: tuple[str, ...],
    subject_texts: tuple[str, ...],
    candidate_ids: tuple[str, ...],
    candidate_texts: tuple[str, ...],
) -> tuple[SimilarityResult, ...]:
    results: list[SimilarityResult] = []
    for subject_id, subject_text in zip(subject_ids, subject_texts, strict=True):
        for candidate_id, candidate_text in zip(candidate_ids, candidate_texts, strict=True):
            score = _jaccard_similarity(subject_text, candidate_text)
            results.append(
                SimilarityResult(
                    subject_id=subject_id,
                    candidate_reference=candidate_id,
                    similarity_score=score,
                    rationale=_rationale(subject_text, candidate_text, score),
                )
            )
    return tuple(results)


def _gaps_for(
    subject_ids_with_evidence: tuple[tuple[str, tuple[SupportingEvidence, ...]], ...],
    similarity_results: tuple[SimilarityResult, ...],
) -> tuple[GapAnalysis, ...]:
    best_score: dict[str, float] = {}
    for result in similarity_results:
        if result.similarity_score > best_score.get(result.subject_id, 0.0):
            best_score[result.subject_id] = result.similarity_score

    gaps: list[GapAnalysis] = []
    for subject_id, evidence in subject_ids_with_evidence:
        if best_score.get(subject_id, 0.0) == 0.0:
            gaps.append(
                GapAnalysis(
                    subject_id=subject_id,
                    description=f"no candidate shares any term with subject '{subject_id}'",
                    supporting_evidence=evidence,
                )
            )
    return tuple(gaps)


# -- Business Entities ------------------------------------------------------------------------------


def compare_business_entities(
    subjects: tuple[BusinessEntity, ...], candidates: tuple[BusinessEntity, ...]
) -> tuple[SimilarityResult, ...]:
    return _compare_pairs(
        tuple(subject.entity_id for subject in subjects),
        tuple(subject.name for subject in subjects),
        tuple(candidate.entity_id for candidate in candidates),
        tuple(candidate.name for candidate in candidates),
    )


def detect_business_entity_gaps(
    subjects: tuple[BusinessEntity, ...], similarity_results: tuple[SimilarityResult, ...]
) -> tuple[GapAnalysis, ...]:
    return _gaps_for(
        tuple((subject.entity_id, subject.supporting_evidence) for subject in subjects), similarity_results
    )


# -- Business Processes -----------------------------------------------------------------------------


def compare_business_processes(
    subjects: tuple[BusinessProcess, ...], candidates: tuple[BusinessProcess, ...]
) -> tuple[SimilarityResult, ...]:
    return _compare_pairs(
        tuple(subject.process_id for subject in subjects),
        tuple(subject.name for subject in subjects),
        tuple(candidate.process_id for candidate in candidates),
        tuple(candidate.name for candidate in candidates),
    )


def detect_business_process_gaps(
    subjects: tuple[BusinessProcess, ...], similarity_results: tuple[SimilarityResult, ...]
) -> tuple[GapAnalysis, ...]:
    return _gaps_for(
        tuple((subject.process_id, subject.supporting_evidence) for subject in subjects), similarity_results
    )


# -- Actors -------------------------------------------------------------------------------------------


def compare_actors(
    subjects: tuple[Actor, ...], candidates: tuple[Actor, ...]
) -> tuple[SimilarityResult, ...]:
    return _compare_pairs(
        tuple(subject.actor_id for subject in subjects),
        tuple(subject.name for subject in subjects),
        tuple(candidate.actor_id for candidate in candidates),
        tuple(candidate.name for candidate in candidates),
    )


def detect_actor_gaps(
    subjects: tuple[Actor, ...], similarity_results: tuple[SimilarityResult, ...]
) -> tuple[GapAnalysis, ...]:
    return _gaps_for(
        tuple((subject.actor_id, subject.supporting_evidence) for subject in subjects), similarity_results
    )


# -- Business Rules -----------------------------------------------------------------------------------


def compare_business_rules(
    subjects: tuple[BusinessRule, ...], candidates: tuple[BusinessRule, ...]
) -> tuple[SimilarityResult, ...]:
    return _compare_pairs(
        tuple(subject.rule_id for subject in subjects),
        tuple(subject.statement for subject in subjects),
        tuple(candidate.rule_id for candidate in candidates),
        tuple(candidate.statement for candidate in candidates),
    )


def detect_business_rule_gaps(
    subjects: tuple[BusinessRule, ...], similarity_results: tuple[SimilarityResult, ...]
) -> tuple[GapAnalysis, ...]:
    return _gaps_for(
        tuple((subject.rule_id, subject.supporting_evidence) for subject in subjects), similarity_results
    )


# -- Business Constraints ------------------------------------------------------------------------------


def compare_business_constraints(
    subjects: tuple[BusinessConstraint, ...], candidates: tuple[BusinessConstraint, ...]
) -> tuple[SimilarityResult, ...]:
    return _compare_pairs(
        tuple(subject.constraint_id for subject in subjects),
        tuple(subject.statement for subject in subjects),
        tuple(candidate.constraint_id for candidate in candidates),
        tuple(candidate.statement for candidate in candidates),
    )


def detect_business_constraint_gaps(
    subjects: tuple[BusinessConstraint, ...], similarity_results: tuple[SimilarityResult, ...]
) -> tuple[GapAnalysis, ...]:
    return _gaps_for(
        tuple((subject.constraint_id, subject.supporting_evidence) for subject in subjects),
        similarity_results,
    )


# -- Top-level: populate an AnalysisResult's own similarity_results/gaps fields ------------------------


def compare_analysis_result(
    analysis_result: AnalysisResult,
    *,
    erpnext_entities: tuple[BusinessEntity, ...] = (),
    erpnext_processes: tuple[BusinessProcess, ...] = (),
    erpnext_actors: tuple[Actor, ...] = (),
    erpnext_rules: tuple[BusinessRule, ...] = (),
    erpnext_constraints: tuple[BusinessConstraint, ...] = (),
) -> AnalysisResult:
    """Compares every category in `analysis_result.requirement_analysis`
    against the supplied ERPNext-side candidates, and returns a *new*
    `AnalysisResult` (frozen models are never mutated in place) with
    `similarity_results`/`gaps` populated — the two fields Sprint 9 Phase 3
    always left empty, explicitly deferring them to this phase.
    """

    requirement_analysis = analysis_result.requirement_analysis

    entity_results = compare_business_entities(requirement_analysis.entities, erpnext_entities)
    process_results = compare_business_processes(requirement_analysis.processes, erpnext_processes)
    actor_results = compare_actors(requirement_analysis.actors, erpnext_actors)
    rule_results = compare_business_rules(requirement_analysis.rules, erpnext_rules)
    constraint_results = compare_business_constraints(requirement_analysis.constraints, erpnext_constraints)

    similarity_results = entity_results + process_results + actor_results + rule_results + constraint_results

    gaps = (
        detect_business_entity_gaps(requirement_analysis.entities, entity_results)
        + detect_business_process_gaps(requirement_analysis.processes, process_results)
        + detect_actor_gaps(requirement_analysis.actors, actor_results)
        + detect_business_rule_gaps(requirement_analysis.rules, rule_results)
        + detect_business_constraint_gaps(requirement_analysis.constraints, constraint_results)
    )

    return analysis_result.model_copy(update={"similarity_results": similarity_results, "gaps": gaps})
