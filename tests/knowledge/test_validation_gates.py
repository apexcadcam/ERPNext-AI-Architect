"""Tests for the eight Validation gates (KNOWLEDGE_VALIDATION_SPEC.md)."""

from __future__ import annotations

from collections.abc import Callable

from knowledge.artifacts import ArtifactStatus, BestPractice, KnowledgeAPI, Pattern
from knowledge.conflict import PrecedenceTier
from knowledge.validation import gates
from knowledge.validation.state import KnowledgeStore
from runtime.pipeline.engine import PipelineContext, StageOutcome

from tests.knowledge.conftest import StaticPrecedenceProvider, StaticSourceVerifier, StaticTrustScoreProvider


# -- §1 Schema Validation ------------------------------------------------------


def test_schema_validation_rejects_an_artifact_with_no_source_references(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api(source_references=())
    result, outcome = gates.schema_validation(api, pipeline_context)

    assert outcome is StageOutcome.SUCCESS  # never FAILURE — see gates.py module docstring
    assert result.status is ArtifactStatus.REJECTED


def test_schema_validation_rejects_unknown_schema_version(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api(
        metadata=make_knowledge_api().metadata.model_copy(update={"artifact_schema_version": "9.9.9"})
    )
    result, outcome = gates.schema_validation(api, pipeline_context)

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.REJECTED


def test_schema_validation_passes_a_well_formed_artifact(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api()
    result, outcome = gates.schema_validation(api, pipeline_context)

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.DRAFT


def test_schema_validation_passes_through_an_already_rejected_artifact_unchanged(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    rejected = make_knowledge_api(status=ArtifactStatus.REJECTED, source_references=())
    result, outcome = gates.schema_validation(rejected, pipeline_context)

    assert result is rejected  # untouched, not re-evaluated
    assert outcome is StageOutcome.SUCCESS


# -- §2 Duplicate Detection -----------------------------------------------------


def test_duplicate_detection_remembers_the_first_artifact_of_its_kind(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    store = KnowledgeStore()
    api = make_knowledge_api()

    result, outcome = gates.duplicate_detection(api, pipeline_context, store=store)

    assert outcome is StageOutcome.SUCCESS
    assert result is api
    assert store.find_exact_duplicate(api) is not None


def test_duplicate_detection_merges_an_exact_duplicate_into_the_existing_artifact(
    make_knowledge_api: Callable[..., KnowledgeAPI],
    make_source_ref: Callable[..., object],
    pipeline_context: PipelineContext,
) -> None:
    store = KnowledgeStore()
    first = make_knowledge_api(api_id="KA-0001")
    gates.duplicate_detection(first, pipeline_context, store=store)

    duplicate = make_knowledge_api(
        api_id="KA-0002", source_references=(make_source_ref(url="https://second.invalid"),)
    )
    result, outcome = gates.duplicate_detection(duplicate, pipeline_context, store=store)

    assert outcome is StageOutcome.SUCCESS
    assert result.id == "KA-0001"  # the existing artifact, not a new one
    assert len(result.source_references) == 2  # corroborated, not replaced


# -- §3 Version Conflict Detection ----------------------------------------------


def test_version_conflict_detection_supersedes_the_lower_precedence_claim(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    store = KnowledgeStore()
    precedence = StaticPrecedenceProvider(
        overrides={
            "KA-0001": PrecedenceTier.OFFICIAL_SOURCE_CODE,
            "KA-0002": PrecedenceTier.OFFICIAL_DOCUMENTATION,
        }
    )
    existing = make_knowledge_api(
        api_id="KA-0001", content=make_knowledge_api().content.model_copy(update={"signature": "old(x)"})
    )
    store.remember(existing)

    new_claim = make_knowledge_api(
        api_id="KA-0002", content=make_knowledge_api().content.model_copy(update={"signature": "new(x, y)"})
    )
    result, outcome = gates.version_conflict_detection(
        new_claim, pipeline_context, store=store, precedence_provider=precedence
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.SUPERSEDED  # code (KA-0001) outranks docs (KA-0002)


def test_version_conflict_detection_lets_the_higher_precedence_claim_continue(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    store = KnowledgeStore()
    precedence = StaticPrecedenceProvider(
        overrides={
            "KA-0001": PrecedenceTier.OFFICIAL_DOCUMENTATION,
            "KA-0002": PrecedenceTier.OFFICIAL_SOURCE_CODE,
        }
    )
    existing = make_knowledge_api(
        api_id="KA-0001", content=make_knowledge_api().content.model_copy(update={"signature": "old(x)"})
    )
    store.remember(existing)

    new_claim = make_knowledge_api(
        api_id="KA-0002", content=make_knowledge_api().content.model_copy(update={"signature": "new(x, y)"})
    )
    result, outcome = gates.version_conflict_detection(
        new_claim, pipeline_context, store=store, precedence_provider=precedence
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.DRAFT  # KA-0002 (code) wins, keeps validating


def test_version_conflict_detection_holds_an_unresolvable_conflict_pending(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    store = KnowledgeStore()
    precedence = StaticPrecedenceProvider(
        tier=PrecedenceTier.COMMUNITY_FORUM_CONSENSUS
    )  # same tier both sides
    existing = make_knowledge_api(
        api_id="KA-0001", content=make_knowledge_api().content.model_copy(update={"signature": "old(x)"})
    )
    store.remember(existing)

    new_claim = make_knowledge_api(
        api_id="KA-0002", content=make_knowledge_api().content.model_copy(update={"signature": "new(x, y)"})
    )
    result, outcome = gates.version_conflict_detection(
        new_claim, pipeline_context, store=store, precedence_provider=precedence
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.PENDING_CONFLICT_RESOLUTION


def test_version_conflict_detection_ignores_claims_about_a_different_subject(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    store = KnowledgeStore()
    precedence = StaticPrecedenceProvider()
    other_subject = make_knowledge_api(
        api_id="KA-0001",
        content=make_knowledge_api().content.model_copy(update={"name": "frappe.other.method"}),
    )
    store.remember(other_subject)

    new_claim = make_knowledge_api(api_id="KA-0002")
    result, outcome = gates.version_conflict_detection(
        new_claim, pipeline_context, store=store, precedence_provider=precedence
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.DRAFT


# -- §4 Source Verification -----------------------------------------------------


def test_source_verification_rejects_when_the_source_no_longer_checks_out(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api()
    result, outcome = gates.source_verification(
        api, pipeline_context, source_verifier=StaticSourceVerifier(False)
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.REJECTED


def test_source_verification_passes_when_the_source_checks_out(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api()
    result, outcome = gates.source_verification(
        api, pipeline_context, source_verifier=StaticSourceVerifier(True)
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.DRAFT


# -- §5 Trust Verification -------------------------------------------------------


def test_trust_verification_tags_low_confidence_below_the_type_threshold(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api()  # Knowledge API threshold is 80
    result, outcome = gates.trust_verification(
        api, pipeline_context, trust_score_provider=StaticTrustScoreProvider(score=50)
    )

    assert outcome is StageOutcome.SUCCESS
    assert "low-confidence" in result.tags
    assert result.status is ArtifactStatus.DRAFT  # demoted, not rejected


def test_trust_verification_does_not_tag_at_or_above_threshold(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api()
    result, outcome = gates.trust_verification(
        api, pipeline_context, trust_score_provider=StaticTrustScoreProvider(score=80)
    )

    assert outcome is StageOutcome.SUCCESS
    assert "low-confidence" not in result.tags


def test_trust_verification_uses_the_lower_threshold_for_third_party_patterns(
    make_pattern: Callable[..., Pattern], pipeline_context: PipelineContext
) -> None:
    third_party_pattern = make_pattern(
        content=make_pattern().content.model_copy(update={"third_party_observed": True})
    )
    # 60 fails the official 70 bar but clears the third-party 50 bar.
    result, outcome = gates.trust_verification(
        third_party_pattern, pipeline_context, trust_score_provider=StaticTrustScoreProvider(score=60)
    )

    assert outcome is StageOutcome.SUCCESS
    assert "low-confidence" not in result.tags


# -- §6 Engineering Review -------------------------------------------------------


def test_engineering_review_escalates_a_claim_tagged_as_contradicting_a_stable_rule(
    make_pattern: Callable[..., Pattern], pipeline_context: PipelineContext
) -> None:
    pattern = make_pattern(tags=(gates.TAG_CONTRADICTS_STABLE_RULE,))
    result, outcome = gates.engineering_review(pattern, pipeline_context)

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.PENDING_HUMAN_APPROVAL


def test_engineering_review_passes_an_untagged_artifact(
    make_pattern: Callable[..., Pattern], pipeline_context: PipelineContext
) -> None:
    pattern = make_pattern()
    result, outcome = gates.engineering_review(pattern, pipeline_context)

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.DRAFT


# -- §8 Confidence Scoring --------------------------------------------------------


def test_confidence_scoring_promotes_a_surviving_artifact_to_validated(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api()
    result, outcome = gates.confidence_scoring(
        api, pipeline_context, trust_score_provider=StaticTrustScoreProvider(score=90)
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.VALIDATED
    assert 0.0 < result.confidence <= 1.0


def test_confidence_scoring_leaves_a_rejected_artifact_untouched(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    rejected = make_knowledge_api(status=ArtifactStatus.REJECTED)
    result, outcome = gates.confidence_scoring(
        rejected, pipeline_context, trust_score_provider=StaticTrustScoreProvider(score=90)
    )

    assert result is rejected
    assert outcome is StageOutcome.SUCCESS


def test_confidence_scoring_leaves_a_pending_human_approval_artifact_untouched(
    make_best_practice: Callable[..., BestPractice], pipeline_context: PipelineContext
) -> None:
    pending = make_best_practice(status=ArtifactStatus.PENDING_HUMAN_APPROVAL)
    result, outcome = gates.confidence_scoring(
        pending, pipeline_context, trust_score_provider=StaticTrustScoreProvider(score=90)
    )

    assert result is pending  # gate 8 must not finalize a still-pending artifact
    assert outcome is StageOutcome.SUCCESS
