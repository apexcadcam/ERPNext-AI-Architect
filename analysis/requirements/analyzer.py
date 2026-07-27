"""Deterministic Requirement Analysis — Sprint 9, Phase 3.

Implements the approved Sprint 9 brief's Phase 3 objective: "the analyzer
extracts facts, it never interprets intent beyond deterministic parsing
rules." Every function here is a pure, deterministic mapping from one
`analysis.requirements.raw.RawRequirement` (already-structured input — see
`raw.py`'s own module docstring) to `analysis.contract` shapes. No LLM, no
inference of anything not already present in the raw input, no ranking,
no recommendation.

**Identifier scheme, disclosed rather than left implicit:** every produced
id is `f"{requirement_id}:{kind}:{discriminator}"` — for entities/
processes/actors, `discriminator` is the mention's own `name`; for rules/
constraints (which carry no name, only a `statement`), `discriminator` is
the mention's own position in its declared tuple. Both are a pure,
deterministic function of the input alone: the same `RawRequirement`
always produces the same ids, and ids are scoped per-requirement so the
same entity name mentioned in two different requirements never collides.
Two mentions with the same name within one requirement legitimately
produce the same id — this module does not deduplicate or otherwise judge
whether they denote "the same" entity, which would be inference, not
extraction.

**`BusinessProcess.actor_ids`** are generated from each process mention's
own `actors` names using the identical formula `analyze_actors()` uses —
if a matching `RawActorMention` also exists, the ids line up naturally;
if not, the reference is still a valid string, simply unresolved (the
same "opaque reference, not resolved here" discipline `SimilarityResult.
candidate_reference` already established in Phase 1).

Imports nothing beyond `analysis.contract` and `analysis.requirements.raw`
(both siblings in this same package) and the standard library: no
`intelligence`, `planning`, `execution`, `runtime`, `knowledge`,
`orchestration`, or `integration`. No network, no provider SDK.
"""

from __future__ import annotations

from analysis.contract import (
    Actor,
    AnalysisResult,
    BusinessConstraint,
    BusinessEntity,
    BusinessProcess,
    BusinessRule,
    Requirement,
    RequirementAnalysis,
    SupportingEvidence,
)
from analysis.requirements.raw import RawRequirement


def _evidence(requirement_id: str, excerpt: str) -> SupportingEvidence:
    return SupportingEvidence(
        source_reference=requirement_id,
        excerpt=excerpt,
        rationale="identified as a structured mention in the requirement input",
    )


def analyze_requirement_statement(raw: RawRequirement) -> Requirement:
    """Target: Requirements."""

    return Requirement(requirement_id=raw.requirement_id, description=raw.description)


def analyze_business_entities(raw: RawRequirement) -> tuple[BusinessEntity, ...]:
    """Target: Business Entities."""

    return tuple(
        BusinessEntity(
            entity_id=f"{raw.requirement_id}:entity:{mention.name}",
            name=mention.name,
            attributes=mention.attributes,
            supporting_evidence=(_evidence(raw.requirement_id, mention.excerpt),),
        )
        for mention in raw.entities
    )


def analyze_actors(raw: RawRequirement) -> tuple[Actor, ...]:
    """Target: Actors."""

    return tuple(
        Actor(
            actor_id=f"{raw.requirement_id}:actor:{mention.name}",
            name=mention.name,
            supporting_evidence=(_evidence(raw.requirement_id, mention.excerpt),),
        )
        for mention in raw.actors
    )


def analyze_business_processes(raw: RawRequirement) -> tuple[BusinessProcess, ...]:
    """Target: Business Processes."""

    return tuple(
        BusinessProcess(
            process_id=f"{raw.requirement_id}:process:{mention.name}",
            name=mention.name,
            actor_ids=tuple(f"{raw.requirement_id}:actor:{actor_name}" for actor_name in mention.actors),
            steps=mention.steps,
            supporting_evidence=(_evidence(raw.requirement_id, mention.excerpt),),
        )
        for mention in raw.processes
    )


def analyze_business_rules(raw: RawRequirement) -> tuple[BusinessRule, ...]:
    """Target: Business Rules."""

    return tuple(
        BusinessRule(
            rule_id=f"{raw.requirement_id}:rule:{index}",
            statement=mention.statement,
            supporting_evidence=(_evidence(raw.requirement_id, mention.excerpt),),
        )
        for index, mention in enumerate(raw.rules)
    )


def analyze_business_constraints(raw: RawRequirement) -> tuple[BusinessConstraint, ...]:
    """Target: Business Constraints."""

    return tuple(
        BusinessConstraint(
            constraint_id=f"{raw.requirement_id}:constraint:{index}",
            statement=mention.statement,
            supporting_evidence=(_evidence(raw.requirement_id, mention.excerpt),),
        )
        for index, mention in enumerate(raw.constraints)
    )


def build_requirement_analysis(raw: RawRequirement) -> RequirementAnalysis:
    """Assembles all six extraction targets into one `RequirementAnalysis`."""

    return RequirementAnalysis(
        requirement_id=raw.requirement_id,
        entities=analyze_business_entities(raw),
        processes=analyze_business_processes(raw),
        rules=analyze_business_rules(raw),
        constraints=analyze_business_constraints(raw),
        actors=analyze_actors(raw),
    )


def build_analysis_result(raw: RawRequirement) -> AnalysisResult:
    """Populates `AnalysisResult` using only deterministic logic.
    `similarity_results`/`gaps` are always empty here — similarity
    analysis and ERP comparison are explicitly out of this phase's scope,
    left for a later phase to attach.
    """

    return AnalysisResult(
        analysis_id=f"analysis:{raw.requirement_id}",
        requirement_id=raw.requirement_id,
        requirement_analysis=build_requirement_analysis(raw),
        similarity_results=(),
        gaps=(),
    )
