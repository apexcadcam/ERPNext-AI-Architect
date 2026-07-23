"""The Human Approval Gate's pending queue and resolution entrypoint.

Implements KNOWLEDGE_VALIDATION_SPEC.md §7 as a pipeline *pause*, not a
blocking call: the gate halts a run at `pending-human-approval` (see
gates.py's `human_approval_gate`); `PendingApprovalStore.resolve()` is the
separate, explicit re-entry point a caller uses once a decision is made.

Per SPRINT2_IMPLEMENTATION_PLAN.md §6/§8: PIPELINE_ENGINE.md defines no
resume-in-place primitive, so `resolve()` finalizes the artifact directly
(computing confidence and setting its terminal status) rather than
re-entering the eight-gate sequence — this is a deliberate implementation
choice within the frozen stage contract, flagged for review rather than
presented as an obvious resume mechanism.
"""

from __future__ import annotations

import enum

from knowledge.artifacts import ArtifactStatus, ContentArtifact
from knowledge.validation.confidence import compute_confidence_for_artifact
from knowledge.validation.providers import TrustScoreProvider
from runtime.events.bus import Event, EventBus


class ApprovalDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class PendingApprovalStore:
    """The queue `human_approval_gate` writes to and `resolve()` drains."""

    def __init__(self, trust_score_provider: TrustScoreProvider, event_bus: EventBus | None = None) -> None:
        self._trust_score_provider = trust_score_provider
        self._event_bus = event_bus
        self._pending: dict[str, ContentArtifact] = {}

    def record(self, artifact: ContentArtifact) -> None:
        self._pending[artifact.id] = artifact

    def get(self, artifact_id: str) -> ContentArtifact | None:
        return self._pending.get(artifact_id)

    def pending_ids(self) -> tuple[str, ...]:
        return tuple(self._pending)

    def resolve(self, artifact_id: str, decision: ApprovalDecision) -> ContentArtifact:
        """Resolve a pending artifact. Raises `KeyError` if `artifact_id`
        has no pending approval — resolving something that was never asked
        for is a caller defect, not a condition to swallow. Publishes
        `HumanApprovalResolved` (STUDIO_EVENT_MODEL.md §2) either way.
        """

        artifact = self._pending.pop(artifact_id, None)
        if artifact is None:
            raise KeyError(f"no pending approval for artifact '{artifact_id}'")

        if decision is ApprovalDecision.REJECTED:
            resolved = artifact.model_copy(update={"status": ArtifactStatus.REJECTED})
            self._publish_resolved(artifact_id, decision)
            return resolved

        confidence = compute_confidence_for_artifact(artifact, self._trust_score_provider)
        resolved = artifact.model_copy(update={"status": ArtifactStatus.VALIDATED, "confidence": confidence})
        self._publish_resolved(artifact_id, decision)
        return resolved

    def _publish_resolved(self, artifact_id: str, decision: ApprovalDecision) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            Event(
                event_type="HumanApprovalResolved",
                payload={"artifact_id": artifact_id, "decision": decision.value},
                emitted_by="validator",
            )
        )
