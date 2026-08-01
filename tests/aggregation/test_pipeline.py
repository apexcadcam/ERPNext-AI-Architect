"""Tests for `aggregation.pipeline` (Pattern Aggregation Engine Architecture
Specification v1.0 §12).
"""

from __future__ import annotations

from typing import Any

import pytest

from runtime.container.di import Container
from runtime.errors import PipelineDefinitionError
from runtime.lifecycle import PipelineRunState
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, PipelineEngine, StageOutcome

from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceKind,
    EvidenceSet,
    EvidenceStatistics,
    Source,
)

from aggregation.contract import AggregationRequest, PatternSet
from aggregation.engine import aggregate_patterns
from aggregation.module import CAPABILITY_AGGREGATE_PATTERNS, AggregationModule
from aggregation.pipeline import AGGREGATION_PATTERN_PIPELINE, register_aggregation_pipeline

_ALL_CAPABILITIES = (CAPABILITY_AGGREGATE_PATTERNS,)
_COMMIT = "1d14ba16398db3a220873509565c60f2932bed81"


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="aggregation",
        display_name="Pattern Aggregation",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=_ALL_CAPABILITIES,
        entry_point="module:create",
    )


def _booted_engine() -> PipelineEngine:
    container = Container()
    module = AggregationModule(_manifest())
    module.init(container)
    engine = PipelineEngine(container)
    register_aggregation_pipeline(engine)
    return engine


def _evidence(*, symbol: str, subject: str) -> Evidence:
    return Evidence(
        evidence_id=f"{symbol}|{subject}".ljust(64, "0")[:64],
        kind=EvidenceKind.IMPLEMENTATION,
        category=EvidenceCategory.WHITELISTED_API_DECORATION,
        symbol=symbol,
        subject=subject,
        source=Source(
            repository=CanonicalRepository.FRAPPE,
            version="v15.102.0",
            commit=_COMMIT,
            relative_path="erpnext/api.py",
            line=1,
        ),
        collector=CollectorName.WHITELISTED_API_DECORATION_COLLECTOR,
        collected_at="2026-07-27T12:00:00+00:00",
    )


def _request() -> AggregationRequest:
    records = (
        _evidence(symbol="erpnext.api.a", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.api.a", subject="frappe.read_only"),
        _evidence(symbol="erpnext.api.b", subject="frappe.whitelist"),
        _evidence(symbol="erpnext.api.b", subject="frappe.read_only"),
    )
    evidence_set = EvidenceSet(
        evidence_set_id="evset-1",
        schema_version="1.0",
        repository=CanonicalRepository.FRAPPE,
        version="v15.102.0",
        commit=_COMMIT,
        extracted_at="2026-07-27T12:00:00+00:00",
        correlation_id="corr-1",
        evidence=records,
        errors=(),
        truncated=False,
        statistics=EvidenceStatistics(
            files_examined=1, files_skipped=0, files_failed=0, evidence_extracted=len(records)
        ),
    )
    return AggregationRequest(evidence_set=evidence_set, correlation_id="corr-1", requested_by="test-suite")


# -- Definition shape -------------------------------------------------------------------------------


def test_the_pipeline_has_the_one_specified_stage() -> None:
    assert [stage.name for stage in AGGREGATION_PATTERN_PIPELINE.stages] == ["aggregate_patterns"]


def test_the_stage_is_bound_to_the_modules_own_registered_capability() -> None:
    assert AGGREGATION_PATTERN_PIPELINE.stages[0].capability == CAPABILITY_AGGREGATE_PATTERNS


def test_the_pipeline_is_named_for_this_package() -> None:
    assert AGGREGATION_PATTERN_PIPELINE.name == "aggregation.patterns"


def test_no_stage_declares_a_rollback_capability() -> None:
    # Aggregation is read-only: it consumes an in-memory EvidenceSet,
    # writes nothing, mutates nothing -- so there is no side effect to
    # compensate. A deliberate omission, not an oversight.
    assert all(stage.rollback_capability is None for stage in AGGREGATION_PATTERN_PIPELINE.stages)


# -- Registration -----------------------------------------------------------------------------------


def test_register_aggregation_pipeline_registers_it_by_name() -> None:
    engine = _booted_engine()
    assert "aggregation.patterns" in engine.registered_pipelines()


def test_registering_twice_raises() -> None:
    engine = _booted_engine()
    with pytest.raises(PipelineDefinitionError):
        register_aggregation_pipeline(engine)


def test_registering_does_not_disturb_other_pipelines() -> None:
    # Backward compatibility: registering this pipeline must not remove or
    # shadow any pipeline already present on the same engine.
    from evidence.module import CAPABILITY_EXTRACT_EVIDENCE, EvidenceModule
    from evidence.pipeline import register_evidence_pipeline

    container = Container()
    AggregationModule(_manifest()).init(container)
    EvidenceModule(
        ModuleManifest(
            module_id="evidence",
            display_name="Evidence Extraction",
            maintained_by="test-suite",
            version="0.1.0",
            capabilities_provided=(CAPABILITY_EXTRACT_EVIDENCE,),
            entry_point="module:create",
        )
    ).init(container)

    engine = PipelineEngine(container)
    register_evidence_pipeline(engine)
    register_aggregation_pipeline(engine)

    registered = engine.registered_pipelines()
    assert "evidence.extraction" in registered
    assert "aggregation.patterns" in registered


# -- Execution ---------------------------------------------------------------------------------------


def test_running_the_pipeline_produces_a_pattern_set() -> None:
    engine = _booted_engine()

    result = engine.run("aggregation.patterns", initial_input=_request(), correlation_id="corr-1")

    assert result.state is PipelineRunState.COMPLETED
    assert result.succeeded
    assert isinstance(result.output, PatternSet)
    assert [record.stage_name for record in result.stage_records] == ["aggregate_patterns"]


def test_pipeline_output_matches_the_plain_function_interface() -> None:
    request = _request()

    via_pipeline = (
        _booted_engine().run("aggregation.patterns", initial_input=request, correlation_id="corr-1").output
    )
    via_plain_function = aggregate_patterns(request)

    strip = {"pattern_set_id": "x", "aggregated_at": "x"}
    assert via_pipeline.model_copy(update=strip) == via_plain_function.model_copy(update=strip)


def test_pipeline_output_preserves_pattern_ids_and_skips() -> None:
    request = _request()

    via_pipeline = (
        _booted_engine().run("aggregation.patterns", initial_input=request, correlation_id="corr-1").output
    )
    via_plain_function = aggregate_patterns(request)

    assert [p.pattern_id for p in via_pipeline.patterns] == [
        p.pattern_id for p in via_plain_function.patterns
    ]
    assert via_pipeline.skipped_aggregations == via_plain_function.skipped_aggregations


def test_the_pipeline_resolves_the_stage_through_the_container() -> None:
    # Proves the pipeline goes through the Container rather than reaching
    # aggregate_patterns directly: a Container whose registered stage is
    # replaced entirely must change what the run returns.
    sentinel = object()
    calls: list[str] = []

    def _sentinel_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
        calls.append("resolved-through-container")
        return sentinel, StageOutcome.SUCCESS

    container = Container()
    container.register(CAPABILITY_AGGREGATE_PATTERNS, lambda: _sentinel_stage)
    engine = PipelineEngine(container)
    register_aggregation_pipeline(engine)

    result = engine.run("aggregation.patterns", initial_input=_request(), correlation_id="corr-1")

    assert calls == ["resolved-through-container"]
    assert result.output is sentinel
