"""The Evaluation module — Runtime-facing host for Architecture
Evaluation's three pipeline stages.

Implements Architecture Evaluation Engine Specification v1.0 §2's Module
lifecycle. Like `DiscoveryModule`/`SynthesisModule`, `init()` calls zero
`container.resolve(...)`: every stage function is pure and self-contained
(`evaluation.engine`), operating only on the `RepositoryFacts` already
present in its own input — `capabilities_required` is empty.

Each stage wrapper below delegates to the exact same package-internal
functions `evaluation.engine.evaluate_architecture()` itself composes —
no duplicated stage logic between the plain-function interface and the
Pipeline-Engine-driven one.
"""

from __future__ import annotations

import time
from typing import Any

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.pipeline.engine import PipelineContext, StageOutcome

from evaluation.contract import EvaluationRequest
from evaluation.engine import Budget, assemble_evaluation, execute_rules
from evaluation.rules import build_fact_index

#: The three Container capabilities this module provides — one per
#: Architecture Evaluation stage (§4), matching `evaluation.pipeline`'s
#: own `StageDefinition.capability` bindings exactly.
CAPABILITY_INDEX_FACTS = "evaluation.index_facts"
CAPABILITY_EXECUTE_RULES = "evaluation.execute_rules"
CAPABILITY_ASSEMBLE_EVALUATION = "evaluation.assemble_evaluation"


def _index_facts_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request: EvaluationRequest = data
    index = build_fact_index(request.repository_facts)
    budget = Budget(remaining_rules=request.max_findings, deadline=time.monotonic() + request.timeout_seconds)
    return (request, index, budget), StageOutcome.SUCCESS


def _execute_rules_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, index, budget = data
    findings, skipped_rules = execute_rules(request.repository_facts, index, budget)
    return (request, findings, skipped_rules, budget), StageOutcome.SUCCESS


def _assemble_evaluation_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request, findings, skipped_rules, budget = data
    evaluation = assemble_evaluation(request, findings, skipped_rules, budget)
    return evaluation, StageOutcome.SUCCESS


class EvaluationModule(Module):
    """Provides the three Architecture Evaluation stage capabilities.
    Requires nothing — see this module's own docstring.
    """

    def init(self, container: Container) -> None:
        container.register(CAPABILITY_INDEX_FACTS, lambda: _index_facts_stage)
        container.register(CAPABILITY_EXECUTE_RULES, lambda: _execute_rules_stage)
        container.register(CAPABILITY_ASSEMBLE_EVALUATION, lambda: _assemble_evaluation_stage)

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="Evaluation stages ready")
