"""Tests for `aggregation.module` (Pattern Aggregation Engine Architecture
Specification v1.0 §12).
"""

from __future__ import annotations

from datetime import UTC, datetime

from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, StageOutcome

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


def _context() -> PipelineContext:
    return PipelineContext(
        pipeline_run_id="run-1",
        correlation_id="corr-1",
        pipeline_name="aggregation.patterns",
        started_at=datetime.now(UTC),
    )


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


# -- Module lifecycle --------------------------------------------------------------------------------


def test_aggregation_module_is_a_module() -> None:
    assert isinstance(AggregationModule(_manifest()), Module)


def test_health_check_is_healthy_before_init() -> None:
    assert AggregationModule(_manifest()).health_check().healthy is True


def test_health_check_is_healthy_after_init() -> None:
    module = AggregationModule(_manifest())
    module.init(Container())
    assert module.health_check().healthy is True


def test_manifest_requires_no_capabilities() -> None:
    assert _manifest().capabilities_required == ()


def test_init_calls_no_container_resolve() -> None:
    # Aggregation is a pure function of the request it is handed, which
    # already carries the persisted EvidenceSet -- nothing to resolve.
    module = AggregationModule(_manifest())

    module.init(Container())


# -- Exactly one capability --------------------------------------------------------------------------


def test_init_registers_the_aggregate_patterns_capability() -> None:
    module = AggregationModule(_manifest())
    container = Container()

    module.init(container)

    assert container.is_registered(CAPABILITY_AGGREGATE_PATTERNS)


def test_exactly_one_capability_is_declared() -> None:
    assert len(_ALL_CAPABILITIES) == 1


def test_the_module_defines_exactly_one_capability_constant() -> None:
    # Structural guard: a second capability constant appearing here would
    # be a scope change, not an implementation detail.
    import aggregation.module as module_under_test

    capability_constants = [name for name in dir(module_under_test) if name.startswith("CAPABILITY_")]
    assert capability_constants == ["CAPABILITY_AGGREGATE_PATTERNS"]


def test_the_capability_name_is_namespaced_to_this_package() -> None:
    assert CAPABILITY_AGGREGATE_PATTERNS == "aggregation.aggregate_patterns"


# -- The wrapper adds nothing -------------------------------------------------------------------------


def test_the_registered_stage_produces_a_pattern_set() -> None:
    module = AggregationModule(_manifest())
    container = Container()
    module.init(container)

    pattern_set, outcome = container.resolve(CAPABILITY_AGGREGATE_PATTERNS)(_request(), _context())

    assert outcome is StageOutcome.SUCCESS
    assert isinstance(pattern_set, PatternSet)
    assert pattern_set.correlation_id == "corr-1"
    assert pattern_set.patterns


def test_the_registered_stage_matches_the_plain_function_exactly() -> None:
    # SS12: the wrapper delegates to aggregate_patterns as-is. Same input,
    # same output -- differing only in the per-run id and timestamp.
    request = _request()
    module = AggregationModule(_manifest())
    container = Container()
    module.init(container)

    via_stage, _ = container.resolve(CAPABILITY_AGGREGATE_PATTERNS)(request, _context())
    via_plain_function = aggregate_patterns(request)

    strip = {"pattern_set_id": "x", "aggregated_at": "x"}
    assert via_stage.model_copy(update=strip) == via_plain_function.model_copy(update=strip)


def test_the_stage_preserves_pattern_ids_exactly() -> None:
    # Content-addressed ids must survive the wrapper untouched.
    request = _request()
    module = AggregationModule(_manifest())
    container = Container()
    module.init(container)

    via_stage, _ = container.resolve(CAPABILITY_AGGREGATE_PATTERNS)(request, _context())
    via_plain_function = aggregate_patterns(request)

    assert [p.pattern_id for p in via_stage.patterns] == [p.pattern_id for p in via_plain_function.patterns]


def test_the_stage_preserves_skipped_aggregations() -> None:
    # SS9's first-class result must pass through the runtime boundary
    # intact, not be flattened into a log line.
    request = _request()
    module = AggregationModule(_manifest())
    container = Container()
    module.init(container)

    via_stage, _ = container.resolve(CAPABILITY_AGGREGATE_PATTERNS)(request, _context())
    via_plain_function = aggregate_patterns(request)

    assert via_stage.skipped_aggregations == via_plain_function.skipped_aggregations


def test_the_stage_always_reports_success_for_ordinary_data() -> None:
    # SS10: no ordinary-data path raises or fails. A category that cannot
    # be aggregated is a recorded result inside a SUCCESS outcome.
    module = AggregationModule(_manifest())
    container = Container()
    module.init(container)

    _, outcome = container.resolve(CAPABILITY_AGGREGATE_PATTERNS)(_request(), _context())

    assert outcome is StageOutcome.SUCCESS
