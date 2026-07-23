"""The eight Validation gates, in their fixed order.

Implements docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md §§1-8. Per
§0, later stages assume earlier ones already passed and an artifact that
fails any stage does not proceed to the next one. Because
`runtime.pipeline.engine.PipelineEngine` discards a run's output entirely
on `StageOutcome.FAILURE` (it cannot, by construction, retain a rejected
artifact for inspection afterward — the opposite of this specification's
"never deleted, only rejected/superseded/pending, always retained"
requirement), every gate below always returns `StageOutcome.SUCCESS` and
encodes the real business outcome in the artifact's own `status` field.
"Stopping" a halted artifact from further gate checks is implemented as
each subsequent gate passing it through unchanged once its status is no
longer `draft` — see `_PASSES_THROUGH` — rather than as an Engine-level abort.

Every gate is a pure function of `(artifact, PipelineContext)`, matching
`runtime.pipeline.engine.StageCallable` exactly. Gates needing state
(duplicate/version indices, injected providers, the approval queue) receive
it via `functools.partial` closures built by `ValidatorModule.init()`
(module.py) — the gate functions themselves hold no state of their own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.artifacts import (
    AntiPattern,
    ArtifactStatus,
    ArtifactType,
    BestPractice,
    ContentArtifact,
    Example,
    KnowledgeAPI,
    Pattern,
    Workflow,
)
from knowledge.conflict import ConflictCase, ConflictClaim, resolve_conflict
from knowledge.validation.approval import PendingApprovalStore
from knowledge.validation.confidence import compute_confidence_for_artifact
from knowledge.validation.providers import PrecedenceProvider, SourceVerifier, TrustScoreProvider
from knowledge.validation.state import KnowledgeStore
from runtime.events.bus import Event, EventBus
from runtime.pipeline.engine import StageOutcome

if TYPE_CHECKING:
    from runtime.pipeline.engine import PipelineContext

#: A status a gate has already moved an artifact into that means "leave it
#: alone" for every gate from this point forward. `draft` is the only status
#: gates 1-6 actively act on; `pending-human-approval` is additionally acted
#: on (once) by gate 7 itself, not by gates 1-6/8.
_PASSES_THROUGH = frozenset(
    {
        ArtifactStatus.REJECTED,
        ArtifactStatus.SUPERSEDED,
        ArtifactStatus.PENDING_CONFLICT_RESOLUTION,
        ArtifactStatus.PENDING_HUMAN_APPROVAL,
    }
)

#: Tag facets Sprint 2 uses as the seam for per-claim facts the artifact
#: envelope has no dedicated field for (KNOWLEDGE_ARTIFACTS.md §1's `tags`
#: are "kebab-case facets... for index grouping" — the same convention
#: KNOWLEDGE_EXTRACTION_SPEC.md already uses for `verified-fixed`,
#: `interim-workaround`, `third-party-observed`, etc.).
TAG_STAFF_AUTHORED = "staff-authored"
TAG_AFTER_DOCS_UPDATE = "authored-after-docs-update"
TAG_CONTRADICTS_STABLE_RULE = "contradicts-stable-rule"
TAG_LOW_CONFIDENCE = "low-confidence"

#: KNOWLEDGE_VALIDATION_SPEC.md §1's supported schema versions.
KNOWN_ARTIFACT_SCHEMA_VERSIONS = frozenset({"1.0.0"})

#: KNOWLEDGE_VALIDATION_SPEC.md §5's per-type Trust Score threshold table.
TRUST_THRESHOLDS: dict[ArtifactType, int] = {
    ArtifactType.KNOWLEDGE_API: 80,
    ArtifactType.PATTERN: 70,
    ArtifactType.ANTI_PATTERN: 70,
    ArtifactType.BEST_PRACTICE: 50,
    ArtifactType.EXAMPLE: 40,
    ArtifactType.WORKFLOW: 60,
}
THIRD_PARTY_PATTERN_TRUST_THRESHOLD = 50

#: The ambiguous confidence band that triggers Human Approval condition 4.
_AMBIGUOUS_CONFIDENCE_LOW = 0.4
_AMBIGUOUS_CONFIDENCE_HIGH = 0.6


def _reject(artifact: ContentArtifact) -> ContentArtifact:
    return artifact.model_copy(update={"status": ArtifactStatus.REJECTED})


def _claim_identity(artifact: ContentArtifact) -> str:
    """The name/title a claim is 'about', used to find a competing claim on
    the same subject. Not itself part of the frozen envelope — derived from
    whichever content field plays that role for each type.
    """

    content = artifact.content
    name = getattr(content, "name", None)
    if isinstance(name, str) and name:
        return name
    title = getattr(content, "title", "")
    return title if isinstance(title, str) else ""


def _claim_body(artifact: ContentArtifact) -> tuple[object, ...]:
    """The substance of a claim, compared to decide whether two artifacts
    with the same identity genuinely disagree.
    """

    if isinstance(artifact, KnowledgeAPI):
        return (artifact.content.signature, artifact.content.return_shape)
    if isinstance(artifact, Pattern | AntiPattern):
        return (artifact.content.solution_shape,)
    if isinstance(artifact, BestPractice):
        return (artifact.content.recommendation,)
    if isinstance(artifact, Example):
        return (artifact.content.code_or_steps,)
    if isinstance(artifact, Workflow):
        return (tuple((step.order, step.description) for step in artifact.content.steps),)
    return ()


def _to_conflict_claim(artifact: ContentArtifact, precedence_provider: PrecedenceProvider) -> ConflictClaim:
    return ConflictClaim(
        artifact_id=artifact.id,
        precedence_tier=precedence_provider.precedence_tier(artifact),
        version_applies_to=artifact.version.applies_to,
        version_confidence=artifact.version.version_confidence,
        staff_authored=TAG_STAFF_AUTHORED in artifact.tags,
        authored_after_docs_last_update=TAG_AFTER_DOCS_UPDATE in artifact.tags,
        contradicts_stable_rule=TAG_CONTRADICTS_STABLE_RULE in artifact.tags,
    )


def _trust_threshold_for(artifact: ContentArtifact) -> int:
    if isinstance(artifact, Pattern) and artifact.content.third_party_observed:
        return THIRD_PARTY_PATTERN_TRUST_THRESHOLD
    return TRUST_THRESHOLDS.get(artifact.type, 0)


# -- §1 Schema Validation ----------------------------------------------------


def schema_validation(
    artifact: ContentArtifact, context: PipelineContext
) -> tuple[ContentArtifact, StageOutcome]:
    """§1: an artifact with no source reference, or an unrecognized schema
    version, is rejected outright — a defect for engineering triage, never
    routed to §7's human queue.
    """

    del context
    if artifact.status in _PASSES_THROUGH:
        return artifact, StageOutcome.SUCCESS
    if not artifact.source_references:
        return _reject(artifact), StageOutcome.SUCCESS
    if artifact.metadata.artifact_schema_version not in KNOWN_ARTIFACT_SCHEMA_VERSIONS:
        return _reject(artifact), StageOutcome.SUCCESS
    return artifact, StageOutcome.SUCCESS


# -- §2 Duplicate Detection ---------------------------------------------------


def duplicate_detection(
    artifact: ContentArtifact, context: PipelineContext, *, store: KnowledgeStore
) -> tuple[ContentArtifact, StageOutcome]:
    """§2: an exact-match duplicate is merged into the existing artifact
    (its source_references appended) rather than rejected or duplicated.
    Near-duplicate/semantic detection needs Embedding — out of Sprint 2's
    scope, per SPRINT2_IMPLEMENTATION_PLAN.md §3.
    """

    del context
    if artifact.status in _PASSES_THROUGH:
        return artifact, StageOutcome.SUCCESS

    existing = store.find_exact_duplicate(artifact)
    if existing is None:
        store.remember(artifact)
        return artifact, StageOutcome.SUCCESS

    merged = existing.model_copy(
        update={"source_references": existing.source_references + artifact.source_references}
    )
    store.remember(merged)
    return merged, StageOutcome.SUCCESS


# -- §3 Version Conflict Detection --------------------------------------------


def version_conflict_detection(
    artifact: ContentArtifact,
    context: PipelineContext,
    *,
    store: KnowledgeStore,
    precedence_provider: PrecedenceProvider,
    event_bus: EventBus | None = None,
) -> tuple[ContentArtifact, StageOutcome]:
    """§3: a same-version, same-subject artifact whose claim genuinely
    disagrees is resolved via `resolve_conflict()`. A deterministic loser is
    marked `superseded`; a deterministic winner continues; anything
    unresolvable is held at `pending-conflict-resolution` until it reaches
    the Human Approval Gate. Publishes `ConflictDetected`
    (STUDIO_EVENT_MODEL.md §2) whenever a genuine disagreement is found.
    """

    del context
    if artifact.status in _PASSES_THROUGH:
        return artifact, StageOutcome.SUCCESS
    if artifact.version.applies_to is None:
        return artifact, StageOutcome.SUCCESS

    candidates = store.same_type_same_version(artifact.type, artifact.version.applies_to)
    for existing in candidates:
        if existing.id == artifact.id:
            continue
        if _claim_identity(existing) != _claim_identity(artifact):
            continue
        if _claim_body(existing) == _claim_body(artifact):
            continue  # same claim, not a disagreement

        case = ConflictCase(
            claim_a=_to_conflict_claim(artifact, precedence_provider),
            claim_b=_to_conflict_claim(existing, precedence_provider),
        )
        resolution = resolve_conflict(case)
        if event_bus is not None:
            event_bus.publish(
                Event(
                    event_type="ConflictDetected",
                    payload={
                        "artifact_id": artifact.id,
                        "conflicting_with": existing.id,
                        "outcome": resolution.outcome.value,
                    },
                    emitted_by="validator",
                )
            )

        if resolution.requires_human_review:
            return artifact.model_copy(update={"status": ArtifactStatus.PENDING_CONFLICT_RESOLUTION}), (
                StageOutcome.SUCCESS
            )
        if resolution.winning_claim_id == existing.id:
            return artifact.model_copy(update={"status": ArtifactStatus.SUPERSEDED}), StageOutcome.SUCCESS
        # this artifact wins deterministically — keep validating it.

    return artifact, StageOutcome.SUCCESS


# -- §4 Source Verification ---------------------------------------------------


def source_verification(
    artifact: ContentArtifact, context: PipelineContext, *, source_verifier: SourceVerifier
) -> tuple[ContentArtifact, StageOutcome]:
    """§4: a source that no longer checks out is rejected — the second,
    most direct anti-hallucination check.
    """

    del context
    if artifact.status in _PASSES_THROUGH:
        return artifact, StageOutcome.SUCCESS
    if not source_verifier.verify(artifact):
        return _reject(artifact), StageOutcome.SUCCESS
    return artifact, StageOutcome.SUCCESS


# -- §5 Trust Verification -----------------------------------------------------


def trust_verification(
    artifact: ContentArtifact, context: PipelineContext, *, trust_score_provider: TrustScoreProvider
) -> tuple[ContentArtifact, StageOutcome]:
    """§5: below-threshold is a demotion, never a rejection — tagged
    `low-confidence` rather than retyped to a lower-bar artifact type
    (full type-changing demotion, e.g. Best Practice → Example, is a known
    Sprint 2 limitation — see SPRINT2_IMPLEMENTATION_PLAN.md-era Known
    Limitations in the Sprint report).
    """

    del context
    if artifact.status in _PASSES_THROUGH:
        return artifact, StageOutcome.SUCCESS

    score = trust_score_provider.trust_score(artifact)
    if score < _trust_threshold_for(artifact) and TAG_LOW_CONFIDENCE not in artifact.tags:
        return artifact.model_copy(
            update={"tags": artifact.tags + (TAG_LOW_CONFIDENCE,)}
        ), StageOutcome.SUCCESS
    return artifact, StageOutcome.SUCCESS


# -- §6 Engineering Review -----------------------------------------------------


def engineering_review(
    artifact: ContentArtifact, context: PipelineContext
) -> tuple[ContentArtifact, StageOutcome]:
    """§6: a candidate contradicting a `Stable` Engineering Rule's Good/Bad
    Pattern is escalated straight to §7, bypassing normal risk-tiered
    routing — never resolved automatically, per PROJECT_CHARTER.md's AI
    First Principles.
    """

    del context
    if artifact.status in _PASSES_THROUGH:
        return artifact, StageOutcome.SUCCESS
    if TAG_CONTRADICTS_STABLE_RULE in artifact.tags:
        return artifact.model_copy(
            update={"status": ArtifactStatus.PENDING_HUMAN_APPROVAL}
        ), StageOutcome.SUCCESS
    return artifact, StageOutcome.SUCCESS


# -- §7 Human Approval Gate ----------------------------------------------------


def human_approval_gate(
    artifact: ContentArtifact,
    context: PipelineContext,
    *,
    trust_score_provider: TrustScoreProvider,
    pending_store: PendingApprovalStore,
    event_bus: EventBus | None = None,
) -> tuple[ContentArtifact, StageOutcome]:
    """§7: mandatory only for an artifact already routed here by §3/§6, or
    whose §8 confidence score (previewed here — see confidence.py's module
    docstring for why) falls in the ambiguous 0.4-0.6 band. Condition 1
    (Engineering Rule candidate drafts) never applies to Sprint 2's modeled
    artifact types — a rule candidate is drafted as a `rules/*.md`-shaped
    document, not one of `ContentArtifact`'s pipeline-native types, per
    KNOWLEDGE_ARTIFACTS.md §2.9.

    Everything else proceeds through the automated approval path untouched.
    Publishes `HumanApprovalRequested` (STUDIO_EVENT_MODEL.md §2) whenever an
    artifact is actually routed into the pending queue.
    """

    del context
    if artifact.status in (ArtifactStatus.REJECTED, ArtifactStatus.SUPERSEDED):
        return artifact, StageOutcome.SUCCESS

    already_routed = artifact.status in (
        ArtifactStatus.PENDING_CONFLICT_RESOLUTION,
        ArtifactStatus.PENDING_HUMAN_APPROVAL,
    )
    ambiguous_confidence = (
        _AMBIGUOUS_CONFIDENCE_LOW
        <= compute_confidence_for_artifact(artifact, trust_score_provider)
        <= _AMBIGUOUS_CONFIDENCE_HIGH
    )

    if not already_routed and not ambiguous_confidence:
        return artifact, StageOutcome.SUCCESS  # automated approval path

    pending = artifact.model_copy(update={"status": ArtifactStatus.PENDING_HUMAN_APPROVAL})
    pending_store.record(pending)
    if event_bus is not None:
        event_bus.publish(
            Event(
                event_type="HumanApprovalRequested",
                payload={"artifact_id": pending.id},
                emitted_by="validator",
            )
        )
    return pending, StageOutcome.SUCCESS


# -- §8 Confidence Scoring -----------------------------------------------------


def confidence_scoring(
    artifact: ContentArtifact,
    context: PipelineContext,
    *,
    trust_score_provider: TrustScoreProvider,
    event_bus: EventBus | None = None,
) -> tuple[ContentArtifact, StageOutcome]:
    """§8: the final gate. An artifact that reached here without being
    rejected, superseded, or routed to a human is promoted to `validated`
    with its computed confidence — this is what "passed validation" means.
    An artifact still awaiting conflict resolution or human approval is left
    untouched; it is finalized later via `PendingApprovalStore.resolve()`.
    Publishes `ValidationCompleted` (STUDIO_EVENT_MODEL.md §2) once the full
    eight-gate sequence finishes for an artifact that reaches `validated`.
    """

    del context
    if artifact.status in _PASSES_THROUGH:
        return artifact, StageOutcome.SUCCESS

    confidence = compute_confidence_for_artifact(artifact, trust_score_provider)
    validated = artifact.model_copy(update={"confidence": confidence, "status": ArtifactStatus.VALIDATED})
    if event_bus is not None:
        event_bus.publish(
            Event(
                event_type="ValidationCompleted",
                payload={"artifact_id": validated.id, "confidence": confidence},
                emitted_by="validator",
            )
        )
    return validated, StageOutcome.SUCCESS
