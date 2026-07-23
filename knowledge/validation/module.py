"""The Validator module — the eight Validation gates as a Runtime Module.

Implements docs/runtime/MODULE_SYSTEM.md's contract for the domain module
docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md specifies. Every gate
is registered into the Container as its own capability, matching
PIPELINE_ENGINE.md §2's stage-execution contract exactly — the
`knowledge.validation` PipelineDefinition (knowledge/pipelines/definitions.py)
binds its eight StageDefinitions to these capability names.

This module's three external-data seams (SourceVerifier, TrustScoreProvider,
PrecedenceProvider) are resolved from the Container under the
`*_CAPABILITY` names below, but are deliberately **not** declared in
`capabilities_required` — per SPRINT2_IMPLEMENTATION_PLAN.md §5, no
capability in this Sprint requires anything from another *module*, and no
Sprint 2 module provides these (they are fixture-backed in this Sprint's own
tests, standing in for a future Crawler/Catalog integration). A caller
assembling a real Runtime must register all three before this module's
`init()` runs; `Container.resolve()` already raises a clear
`CapabilityResolutionError` if one is missing — no extra handling is added
here to paper over that.
"""

from __future__ import annotations

from functools import partial

from knowledge.conflict.providers import PRECEDENCE_PROVIDER_CAPABILITY as _PRECEDENCE_PROVIDER_CAPABILITY
from knowledge.conflict.providers import PrecedenceProvider
from knowledge.validation import gates
from knowledge.validation.approval import PendingApprovalStore
from knowledge.validation.providers import SourceVerifier, TrustScoreProvider
from knowledge.validation.state import KnowledgeStore
from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.modules.manifest import ModuleManifest

#: Registered by whatever assembles the Runtime, not by this module —
#: optional, since a Validator used standalone (e.g. in a unit test) has no
#: Event Bus to notify.
EVENT_BUS_CAPABILITY = "runtime.event_bus"

CAPABILITY_SCHEMA = "knowledge.validate.schema"
CAPABILITY_DUPLICATE = "knowledge.validate.duplicate"
CAPABILITY_VERSION_CONFLICT = "knowledge.validate.version_conflict"
CAPABILITY_SOURCE_VERIFY = "knowledge.validate.source_verify"
CAPABILITY_TRUST_VERIFY = "knowledge.validate.trust_verify"
CAPABILITY_ENGINEERING_REVIEW = "knowledge.validate.engineering_review"
CAPABILITY_HUMAN_APPROVAL = "knowledge.validate.human_approval"
CAPABILITY_CONFIDENCE_SCORE = "knowledge.validate.confidence_score"


class ValidatorModule(Module):
    """Provides the eight `knowledge.validate.*` stage capabilities plus
    the `pending_approvals` queue `knowledge.approval.resolve` (module.py's
    callers, and this Sprint's own tests) drain via
    `PendingApprovalStore.resolve()`.
    """

    SOURCE_VERIFIER_CAPABILITY = "knowledge.providers.source_verifier"
    TRUST_SCORE_PROVIDER_CAPABILITY = "knowledge.providers.trust_score"
    #: Shared with ExtractorModule — see knowledge/conflict/providers.py.
    PRECEDENCE_PROVIDER_CAPABILITY = _PRECEDENCE_PROVIDER_CAPABILITY

    def __init__(self, manifest: ModuleManifest) -> None:
        super().__init__(manifest)
        self.store = KnowledgeStore()
        self.pending_approvals: PendingApprovalStore | None = None

    def init(self, container: Container) -> None:
        source_verifier: SourceVerifier = container.resolve(self.SOURCE_VERIFIER_CAPABILITY)
        trust_score_provider: TrustScoreProvider = container.resolve(self.TRUST_SCORE_PROVIDER_CAPABILITY)
        precedence_provider: PrecedenceProvider = container.resolve(self.PRECEDENCE_PROVIDER_CAPABILITY)
        event_bus = (
            container.resolve(EVENT_BUS_CAPABILITY) if container.is_registered(EVENT_BUS_CAPABILITY) else None
        )
        pending_approvals = PendingApprovalStore(trust_score_provider, event_bus=event_bus)
        self.pending_approvals = pending_approvals

        container.register(CAPABILITY_SCHEMA, lambda: gates.schema_validation, override=True)
        container.register(
            CAPABILITY_DUPLICATE, lambda: partial(gates.duplicate_detection, store=self.store), override=True
        )
        container.register(
            CAPABILITY_VERSION_CONFLICT,
            lambda: partial(
                gates.version_conflict_detection,
                store=self.store,
                precedence_provider=precedence_provider,
                event_bus=event_bus,
            ),
            override=True,
        )
        container.register(
            CAPABILITY_SOURCE_VERIFY,
            lambda: partial(gates.source_verification, source_verifier=source_verifier),
            override=True,
        )
        container.register(
            CAPABILITY_TRUST_VERIFY,
            lambda: partial(gates.trust_verification, trust_score_provider=trust_score_provider),
            override=True,
        )
        container.register(CAPABILITY_ENGINEERING_REVIEW, lambda: gates.engineering_review, override=True)
        container.register(
            CAPABILITY_HUMAN_APPROVAL,
            lambda: partial(
                gates.human_approval_gate,
                trust_score_provider=trust_score_provider,
                pending_store=pending_approvals,
                event_bus=event_bus,
            ),
            override=True,
        )
        container.register(
            CAPABILITY_CONFIDENCE_SCORE,
            lambda: partial(
                gates.confidence_scoring, trust_score_provider=trust_score_provider, event_bus=event_bus
            ),
            override=True,
        )

    def health_check(self) -> HealthCheckResult:
        ready = self.pending_approvals is not None
        return HealthCheckResult(healthy=ready, detail="validator ready" if ready else "not initialized")
