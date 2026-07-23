"""Tests for the Human Approval Gate and its resolution entrypoint
(KNOWLEDGE_VALIDATION_SPEC.md §7, knowledge/validation/approval.py).
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from knowledge.artifacts import ArtifactStatus, BestPractice, KnowledgeAPI
from knowledge.validation import gates
from knowledge.validation.approval import ApprovalDecision, PendingApprovalStore
from runtime.events.bus import EventBus
from runtime.pipeline.engine import PipelineContext, StageOutcome

from tests.knowledge.conftest import StaticTrustScoreProvider


def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0, interval: float = 0.01) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("condition not met before timeout")


def test_an_ordinary_artifact_takes_the_automated_approval_path(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    api = make_knowledge_api()
    store = PendingApprovalStore(StaticTrustScoreProvider(score=90))

    result, outcome = gates.human_approval_gate(
        api, pipeline_context, trust_score_provider=StaticTrustScoreProvider(score=90), pending_store=store
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.DRAFT  # untouched — proceeds straight to §8
    assert store.pending_ids() == ()


def test_ambiguous_confidence_routes_to_the_pending_queue(
    make_best_practice: Callable[..., BestPractice], pipeline_context: PipelineContext
) -> None:
    bp = make_best_practice()
    # Best Practice threshold is 50; trust=60 with the default
    # extraction_confidence (0.75) and corroboration (1.0) yields
    # confidence 0.6 * 0.75 = 0.45, inside the [0.4, 0.6] ambiguous band.
    trust_score_provider = StaticTrustScoreProvider(score=60)
    store = PendingApprovalStore(trust_score_provider)

    result, outcome = gates.human_approval_gate(
        bp, pipeline_context, trust_score_provider=trust_score_provider, pending_store=store
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.PENDING_HUMAN_APPROVAL
    assert store.pending_ids() == (bp.id,)


def test_an_artifact_already_pending_conflict_resolution_is_routed_to_the_queue(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    pending_conflict = make_knowledge_api(status=ArtifactStatus.PENDING_CONFLICT_RESOLUTION)
    trust_score_provider = StaticTrustScoreProvider(score=90)
    store = PendingApprovalStore(trust_score_provider)

    result, outcome = gates.human_approval_gate(
        pending_conflict, pipeline_context, trust_score_provider=trust_score_provider, pending_store=store
    )

    assert outcome is StageOutcome.SUCCESS
    assert result.status is ArtifactStatus.PENDING_HUMAN_APPROVAL
    assert store.get(pending_conflict.id) is not None


def test_rejected_and_superseded_artifacts_pass_through_untouched(
    make_knowledge_api: Callable[..., KnowledgeAPI], pipeline_context: PipelineContext
) -> None:
    rejected = make_knowledge_api(status=ArtifactStatus.REJECTED)
    trust_score_provider = StaticTrustScoreProvider(score=90)
    store = PendingApprovalStore(trust_score_provider)

    result, outcome = gates.human_approval_gate(
        rejected, pipeline_context, trust_score_provider=trust_score_provider, pending_store=store
    )

    assert result is rejected
    assert outcome is StageOutcome.SUCCESS
    assert store.pending_ids() == ()


def test_human_approval_gate_publishes_human_approval_requested(
    make_best_practice: Callable[..., BestPractice], pipeline_context: PipelineContext
) -> None:
    bp = make_best_practice()
    trust_score_provider = StaticTrustScoreProvider(score=60)  # lands in the ambiguous band
    store = PendingApprovalStore(trust_score_provider)
    bus = EventBus()
    received: list[dict[str, object]] = []
    bus.subscribe("HumanApprovalRequested", lambda e: received.append(e.payload))

    gates.human_approval_gate(
        bp, pipeline_context, trust_score_provider=trust_score_provider, pending_store=store, event_bus=bus
    )

    _wait_until(lambda: received == [{"artifact_id": bp.id}])
    bus.shutdown()


def test_resolve_approved_finalizes_the_artifact_as_validated(
    make_best_practice: Callable[..., BestPractice],
) -> None:
    trust_score_provider = StaticTrustScoreProvider(score=90)
    store = PendingApprovalStore(trust_score_provider)
    store.record(make_best_practice(status=ArtifactStatus.PENDING_HUMAN_APPROVAL))

    resolved = store.resolve("BP-0001", ApprovalDecision.APPROVED)

    assert resolved.status is ArtifactStatus.VALIDATED
    assert resolved.confidence > 0.0
    assert store.get("BP-0001") is None  # drained from the queue


def test_resolve_rejected_finalizes_the_artifact_as_rejected(
    make_best_practice: Callable[..., BestPractice],
) -> None:
    trust_score_provider = StaticTrustScoreProvider(score=90)
    store = PendingApprovalStore(trust_score_provider)
    store.record(make_best_practice(status=ArtifactStatus.PENDING_HUMAN_APPROVAL))

    resolved = store.resolve("BP-0001", ApprovalDecision.REJECTED)

    assert resolved.status is ArtifactStatus.REJECTED
    assert store.get("BP-0001") is None


def test_resolving_an_artifact_with_no_pending_approval_raises() -> None:
    store = PendingApprovalStore(StaticTrustScoreProvider(score=90))
    with pytest.raises(KeyError):
        store.resolve("BP-9999", ApprovalDecision.APPROVED)


def test_resolve_publishes_human_approval_resolved(make_best_practice: Callable[..., BestPractice]) -> None:
    trust_score_provider = StaticTrustScoreProvider(score=90)
    bus = EventBus()
    store = PendingApprovalStore(trust_score_provider, event_bus=bus)
    store.record(make_best_practice(status=ArtifactStatus.PENDING_HUMAN_APPROVAL))
    received: list[dict[str, object]] = []
    bus.subscribe("HumanApprovalResolved", lambda e: received.append(e.payload))

    store.resolve("BP-0001", ApprovalDecision.APPROVED)

    _wait_until(lambda: received == [{"artifact_id": "BP-0001", "decision": "approved"}])
    bus.shutdown()
