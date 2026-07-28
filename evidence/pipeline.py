"""Evidence Extraction's own Pipeline Definition.

Registers Evidence Extraction against the existing, real, unmodified
`runtime.pipeline.engine.PipelineEngine`, mirroring
`discovery.pipeline.register_discovery_pipeline`'s own registration shape
field for field (Evidence Extraction Engine Architecture Specification
v1.1 §11).

One stage, bound to `evidence.module`'s one registered capability — the
Pipeline Engine resolves that capability through the Container rather
than calling `evidence.engine.extract_evidence` directly, so the
Container-registered stage is genuinely the thing that runs (see
`tests/evidence/test_pipeline.py`'s own monkeypatched proof of exactly
this).

No `rollback_capability` is set — extraction is read-only (it never
writes to the canonical reference source trees, §5), so there is nothing
to compensate. A deliberate omission, matching every sibling engine's own
identical decision.
"""

from __future__ import annotations

from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition

from evidence.module import CAPABILITY_EXTRACT_EVIDENCE

EVIDENCE_EXTRACTION_PIPELINE = PipelineDefinition(
    name="evidence.extraction",
    stages=(StageDefinition(name="extract_evidence", capability=CAPABILITY_EXTRACT_EVIDENCE),),
)


def register_evidence_pipeline(engine: PipelineEngine) -> None:
    """Registers Evidence Extraction's Pipeline Definition against
    `engine`. Must be called only after an `EvidenceModule` has already
    run `init()` against the same engine's own `Container`, mirroring
    `register_discovery_pipeline`'s identical precondition.
    """

    engine.register(EVIDENCE_EXTRACTION_PIPELINE)
