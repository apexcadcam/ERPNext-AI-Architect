"""The Evidence module — Runtime-facing host for Evidence Extraction.

Implements Evidence Extraction Engine Architecture Specification v1.1
§11's Module shape. Like `DiscoveryModule`/`SynthesisModule`/
`EvaluationModule`/`RecommendationModule`, `init()` calls zero
`container.resolve(...)`: extraction is a pure function of its own
`EvidenceExtractionRequest`, constructing its own `FilesystemConnector`
from that request — `capabilities_required` is empty.

**One capability, not several.** Discovery, Evaluation, and
Recommendation each register one capability per pipeline stage because
each of those engines has genuinely separable stages with meaningful
intermediate artifacts. Evidence Extraction does not: §8's five steps
share a single connector and a single in-flight accumulation, and
splitting them would mean inventing intermediate types that exist only to
be passed between Container capabilities — orchestration logic this
module is explicitly not responsible for. The stage wrapper below
therefore delegates to `extract_evidence` exactly as-is, adding nothing.
"""

from __future__ import annotations

from typing import Any

from runtime.container.di import Container
from runtime.modules.base import HealthCheckResult, Module
from runtime.pipeline.engine import PipelineContext, StageOutcome

from evidence.contract import EvidenceExtractionRequest
from evidence.engine import extract_evidence

#: The one Container capability this module provides, matching
#: `evidence.pipeline`'s own `StageDefinition.capability` binding exactly.
CAPABILITY_EXTRACT_EVIDENCE = "evidence.extract_evidence"


def _extract_evidence_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
    request: EvidenceExtractionRequest = data
    evidence_set = extract_evidence(request)
    return evidence_set, StageOutcome.SUCCESS


class EvidenceModule(Module):
    """Provides the one Evidence Extraction capability. Requires nothing —
    see this module's own docstring.
    """

    def init(self, container: Container) -> None:
        container.register(CAPABILITY_EXTRACT_EVIDENCE, lambda: _extract_evidence_stage)

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, detail="Evidence extraction ready")
