"""The Aggregation module — Runtime-facing host for Pattern Aggregation.

Implements Pattern Aggregation Engine Architecture Specification v1.0
§12's Module shape. Like every sibling engine's module, `init()` calls
zero `container.resolve(...)`: aggregation is a pure function of the
`AggregationRequest` it is given, which already carries the persisted
`EvidenceSet` — `capabilities_required` is empty.

**One capability, not one per step.** Discovery, Evaluation, and
Recommendation each register one capability per pipeline stage because
each of those engines has genuinely separable stages with meaningful
intermediate artifacts. §10's six steps here share a single in-flight
accumulation (the partitioned records, the resolved population, the
subject groups), so splitting them would mean inventing intermediate
types that exist only to be passed between Container capabilities —
orchestration this module is explicitly not responsible for. The stage
wrapper below therefore delegates to `aggregate_patterns` exactly as-is,
adding nothing. `EvidenceModule` made the same call for the same reason.
"""

from __future__ import annotations

from typing import Any

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.pipeline.engine import PipelineContext, StageOutcome

from aggregation.contract import AggregationRequest
from aggregation.engine import aggregate_patterns

#: The one Container capability this module provides, matching
#: `aggregation.pipeline`'s own `StageDefinition.capability` binding
#: exactly.
CAPABILITY_AGGREGATE_PATTERNS = "aggregation.aggregate_patterns"


def _aggregate_patterns_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request: AggregationRequest = data
    pattern_set = aggregate_patterns(request)
    return pattern_set, StageOutcome.SUCCESS


class AggregationModule(Module):
    """Provides the one Pattern Aggregation capability. Requires nothing —
    see this module's own docstring.
    """

    def init(self, container: Container) -> None:
        container.register(CAPABILITY_AGGREGATE_PATTERNS, lambda: _aggregate_patterns_stage)

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="Pattern aggregation ready")
