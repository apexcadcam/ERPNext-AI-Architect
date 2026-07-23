"""Tests for conflict resolution (KNOWLEDGE_CONFLICT_RESOLUTION.md)."""

from __future__ import annotations

from datetime import UTC, datetime

from knowledge.conflict import (
    ConflictCase,
    ConflictClaim,
    ConflictOutcomeKind,
    PrecedenceTier,
    resolve_conflict,
    resolve_conflict_stage,
)
from runtime.pipeline.engine import PipelineContext, StageOutcome


def test_precedence_hierarchy_orders_by_tier_not_confidence() -> None:
    # §1: code (tier 1) always outranks documentation (tier 3), regardless
    # of any confidence score — confidence is not part of this function's
    # input at all, precisely because it must never be conflated with
    # source authority.
    code_claim = ConflictClaim(artifact_id="KA-0001", precedence_tier=PrecedenceTier.OFFICIAL_SOURCE_CODE)
    docs_claim = ConflictClaim(artifact_id="KA-0002", precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)

    resolution = resolve_conflict(ConflictCase(claim_a=docs_claim, claim_b=code_claim))

    assert resolution.outcome is ConflictOutcomeKind.WINNER_BY_PRECEDENCE
    assert resolution.winning_claim_id == "KA-0001"
    assert resolution.losing_claim_id == "KA-0002"
    assert not resolution.requires_human_review


def test_precedence_order_is_symmetric_regardless_of_argument_position() -> None:
    code_claim = ConflictClaim(artifact_id="KA-0001", precedence_tier=PrecedenceTier.OFFICIAL_SOURCE_CODE)
    docs_claim = ConflictClaim(artifact_id="KA-0002", precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)

    resolution = resolve_conflict(ConflictCase(claim_a=code_claim, claim_b=docs_claim))

    assert resolution.winning_claim_id == "KA-0001"


def test_scenario_2_two_documentation_versions_disagree_is_not_a_real_conflict() -> None:
    v14_claim = ConflictClaim(
        artifact_id="KA-0001",
        precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION,
        version_applies_to="v14",
    )
    v15_claim = ConflictClaim(
        artifact_id="KA-0002",
        precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION,
        version_applies_to="v15",
    )

    resolution = resolve_conflict(ConflictCase(claim_a=v14_claim, claim_b=v15_claim))

    assert resolution.outcome is ConflictOutcomeKind.BOTH_VALID_VERSION_SCOPED
    assert resolution.winning_claim_id == "KA-0002"  # v15 supersedes v14
    assert resolution.losing_claim_id == "KA-0001"
    assert not resolution.requires_human_review


def test_scenario_2_ambiguous_version_scoping_enters_the_full_conflict_process() -> None:
    # An inferred-confidence version tag is treated as same-version-until-
    # proven-otherwise, per §2 — it must not silently skip conflict handling.
    explicit_claim = ConflictClaim(
        artifact_id="KA-0001",
        precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION,
        version_applies_to="v14",
        version_confidence="explicit",
    )
    inferred_claim = ConflictClaim(
        artifact_id="KA-0002",
        precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION,
        version_applies_to="v15",
        version_confidence="inferred",
    )

    resolution = resolve_conflict(ConflictCase(claim_a=explicit_claim, claim_b=inferred_claim))

    assert resolution.outcome is ConflictOutcomeKind.UNDECIDED


def test_scenario_3_documentation_disagrees_with_code_code_always_wins() -> None:
    code_claim = ConflictClaim(artifact_id="KA-0001", precedence_tier=PrecedenceTier.OFFICIAL_SOURCE_CODE)
    docs_claim = ConflictClaim(artifact_id="KA-0002", precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)

    resolution = resolve_conflict(ConflictCase(claim_a=docs_claim, claim_b=code_claim))

    assert resolution.outcome is ConflictOutcomeKind.WINNER_BY_PRECEDENCE
    assert resolution.winning_claim_id == "KA-0001"


def test_scenario_4_staff_forum_reply_postdating_docs_is_flagged_not_resolved() -> None:
    docs_claim = ConflictClaim(artifact_id="KA-0001", precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)
    staff_forum_claim = ConflictClaim(
        artifact_id="BP-0001",
        precedence_tier=PrecedenceTier.STAFF_FORUM_REPLY,
        staff_authored=True,
        authored_after_docs_last_update=True,
    )

    resolution = resolve_conflict(ConflictCase(claim_a=docs_claim, claim_b=staff_forum_claim))

    assert resolution.outcome is ConflictOutcomeKind.FLAGGED_DOCS_MAY_BE_STALE
    assert resolution.winning_claim_id is None  # neither claim is picked
    assert resolution.requires_human_review


def test_scenario_4_does_not_apply_when_forum_reply_predates_the_docs() -> None:
    # Without the "dated after the documentation's last update" condition,
    # this is not the §4 exception — plain precedence applies and docs win.
    docs_claim = ConflictClaim(artifact_id="KA-0001", precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)
    stale_staff_forum_claim = ConflictClaim(
        artifact_id="BP-0001",
        precedence_tier=PrecedenceTier.STAFF_FORUM_REPLY,
        staff_authored=True,
        authored_after_docs_last_update=False,
    )

    resolution = resolve_conflict(ConflictCase(claim_a=docs_claim, claim_b=stale_staff_forum_claim))

    assert resolution.outcome is ConflictOutcomeKind.WINNER_BY_PRECEDENCE
    assert resolution.winning_claim_id == "KA-0001"


def test_scenario_5_marketplace_never_outranks_the_framework_recommendation() -> None:
    framework_pattern = ConflictClaim(
        artifact_id="PAT-0001", precedence_tier=PrecedenceTier.OFFICIAL_SOURCE_CODE
    )
    marketplace_pattern = ConflictClaim(
        artifact_id="PAT-0002", precedence_tier=PrecedenceTier.VETTED_MARKETPLACE
    )

    resolution = resolve_conflict(ConflictCase(claim_a=marketplace_pattern, claim_b=framework_pattern))

    assert resolution.outcome is ConflictOutcomeKind.WINNER_BY_PRECEDENCE
    assert resolution.winning_claim_id == "PAT-0001"


def test_scenario_6_a_merged_pr_changing_behavior_is_a_version_transition() -> None:
    old_behavior = ConflictClaim(
        artifact_id="KA-0001",
        precedence_tier=PrecedenceTier.MERGED_PULL_REQUEST,
        version_applies_to="v14",
    )
    new_behavior = ConflictClaim(
        artifact_id="KA-0002",
        precedence_tier=PrecedenceTier.MERGED_PULL_REQUEST,
        version_applies_to="v15",
    )

    resolution = resolve_conflict(ConflictCase(claim_a=old_behavior, claim_b=new_behavior))

    assert resolution.outcome is ConflictOutcomeKind.BOTH_VALID_VERSION_SCOPED
    assert resolution.winning_claim_id == "KA-0002"


def test_scenario_6_rationale_contradicting_a_stable_rule_is_escalated_regardless_of_tier() -> None:
    # Even though this claim's tier (MERGED_PULL_REQUEST) would ordinarily
    # outrank the other side outright, rule-contradiction bypasses precedence
    # entirely and is never resolved automatically.
    pr_claim = ConflictClaim(
        artifact_id="KA-0001",
        precedence_tier=PrecedenceTier.MERGED_PULL_REQUEST,
        contradicts_stable_rule=True,
    )
    docs_claim = ConflictClaim(artifact_id="KA-0002", precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)

    resolution = resolve_conflict(ConflictCase(claim_a=pr_claim, claim_b=docs_claim))

    assert resolution.outcome is ConflictOutcomeKind.ESCALATED_RULE_CONTRADICTION
    assert resolution.winning_claim_id is None
    assert resolution.requires_human_review


def test_same_tier_genuine_disagreement_with_no_version_difference_is_undecided() -> None:
    forum_claim_a = ConflictClaim(
        artifact_id="BP-0001", precedence_tier=PrecedenceTier.COMMUNITY_FORUM_CONSENSUS
    )
    forum_claim_b = ConflictClaim(
        artifact_id="BP-0002", precedence_tier=PrecedenceTier.COMMUNITY_FORUM_CONSENSUS
    )

    resolution = resolve_conflict(ConflictCase(claim_a=forum_claim_a, claim_b=forum_claim_b))

    assert resolution.outcome is ConflictOutcomeKind.UNDECIDED
    assert resolution.winning_claim_id is None
    assert resolution.losing_claim_id is None
    assert resolution.requires_human_review
    assert "do not resolve silently" in resolution.reason


def test_resolve_conflict_stage_matches_the_pipeline_stage_contract() -> None:
    code_claim = ConflictClaim(artifact_id="KA-0001", precedence_tier=PrecedenceTier.OFFICIAL_SOURCE_CODE)
    docs_claim = ConflictClaim(artifact_id="KA-0002", precedence_tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)
    case = ConflictCase(claim_a=code_claim, claim_b=docs_claim)
    context = PipelineContext(
        pipeline_run_id="run-1", correlation_id="run-1", pipeline_name="test", started_at=datetime.now(UTC)
    )

    resolution, outcome = resolve_conflict_stage(case, context)

    assert outcome is StageOutcome.SUCCESS
    assert resolution.winning_claim_id == "KA-0001"
