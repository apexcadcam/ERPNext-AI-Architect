"""The Validator: KNOWLEDGE_VALIDATION_SPEC.md's eight fixed-order gates."""

from __future__ import annotations

from knowledge.conflict.providers import PrecedenceProvider
from knowledge.validation.approval import ApprovalDecision, PendingApprovalStore
from knowledge.validation.module import ValidatorModule
from knowledge.validation.providers import SourceVerifier, TrustScoreProvider
from knowledge.validation.state import KnowledgeStore

__all__ = [
    "ApprovalDecision",
    "KnowledgeStore",
    "PendingApprovalStore",
    "PrecedenceProvider",
    "SourceVerifier",
    "TrustScoreProvider",
    "ValidatorModule",
]
