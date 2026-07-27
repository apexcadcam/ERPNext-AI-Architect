"""Architecture Evaluation — Sprint 18.

Implements the Architecture Evaluation Engine Specification v1.0 (and its
Threshold Documentation & Rule Metadata Addendum) in full: given an
already-produced `synthesis.contract.RepositoryFacts`, evaluates
modularity, separation of concerns, dependency structure, extension
mechanisms, coupling, cohesion, framework usage, configuration quality,
API exposure, service organization, and maintainability indicators,
producing one self-contained `ArchitectureEvaluation` artifact. Zero
Reasoning Engine calls anywhere in this package (see `evaluation.rules`'
own module docstring for why none are needed).

This package touches no filesystem and imports no connector -- every rule
operates on `RepositoryFacts` already in memory. Depends only on
`synthesis.contract` (for `RepositoryFacts` and its fact types) and
`runtime.pipeline.engine`/`runtime.modules.base`/`runtime.modules.manifest`/
`runtime.container.di`. Nothing in this package imports `discovery/`,
`analysis/`, `knowledge/`, `intelligence/`, `planning/`, `execution/`,
`orchestration/`, or `composition_root/`.
"""

from __future__ import annotations

from evaluation.contract import (
    ArchitectureEvaluation,
    Confidence,
    EvaluationRequest,
    EvaluationStatistics,
    Evidence,
    Finding,
    RuleThresholdSpec,
    Severity,
    SkippedRule,
)
from evaluation.engine import evaluate_architecture
from evaluation.errors import EvaluationError_

__all__ = [
    "ArchitectureEvaluation",
    "Confidence",
    "EvaluationError_",
    "EvaluationRequest",
    "EvaluationStatistics",
    "Evidence",
    "Finding",
    "RuleThresholdSpec",
    "Severity",
    "SkippedRule",
    "evaluate_architecture",
]
