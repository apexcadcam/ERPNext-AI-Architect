"""Tests for `evidence.pipeline` (Evidence Extraction Engine Architecture Specification v1.1 §11)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from runtime.container.di import Container
from runtime.errors import PipelineDefinitionError
from runtime.lifecycle import PipelineRunState
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, PipelineEngine, StageOutcome

from evidence.contract import CanonicalRepository, EvidenceExtractionRequest, EvidenceSet
from evidence.engine import extract_evidence
from evidence.module import CAPABILITY_EXTRACT_EVIDENCE, EvidenceModule
from evidence.pipeline import EVIDENCE_EXTRACTION_PIPELINE, register_evidence_pipeline

_ALL_CAPABILITIES = (CAPABILITY_EXTRACT_EVIDENCE,)

_CUSTOMER_PY = """
class Customer:
    def validate(self):
        pass
"""

_API_PY = """
import frappe


@frappe.whitelist()
def get_data():
    return {}
"""


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="evidence",
        display_name="Evidence Extraction",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=_ALL_CAPABILITIES,
        entry_point="module:create",
    )


def _booted_engine() -> PipelineEngine:
    container = Container()
    module = EvidenceModule(_manifest())
    module.init(container)
    engine = PipelineEngine(container)
    register_evidence_pipeline(engine)
    return engine


def _build_tree(root: Path) -> None:
    (root / "erpnext").mkdir()
    (root / "erpnext" / "customer.py").write_text(_CUSTOMER_PY)
    (root / "erpnext" / "api.py").write_text(_API_PY)


def _request(root: Path) -> EvidenceExtractionRequest:
    return EvidenceExtractionRequest(
        repository=CanonicalRepository.FRAPPE,
        source_root=str(root),
        version="v15.103.1",
        commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        correlation_id="corr-1",
        requested_by="test-suite",
        max_files=1_000,
        timeout_seconds=30.0,
    )


# -- Definition shape -------------------------------------------------------------------------------


def test_evidence_extraction_pipeline_has_the_one_specified_stage() -> None:
    assert [stage.name for stage in EVIDENCE_EXTRACTION_PIPELINE.stages] == ["extract_evidence"]


def test_the_stage_is_bound_to_the_modules_own_registered_capability() -> None:
    assert EVIDENCE_EXTRACTION_PIPELINE.stages[0].capability == CAPABILITY_EXTRACT_EVIDENCE


def test_no_stage_declares_a_rollback_capability() -> None:
    assert all(stage.rollback_capability is None for stage in EVIDENCE_EXTRACTION_PIPELINE.stages)


# -- Registration -----------------------------------------------------------------------------------


def test_register_evidence_pipeline_registers_it_by_name() -> None:
    engine = _booted_engine()
    assert "evidence.extraction" in engine.registered_pipelines()


def test_registering_twice_raises() -> None:
    engine = _booted_engine()
    with pytest.raises(PipelineDefinitionError):
        register_evidence_pipeline(engine)


# -- Execution ---------------------------------------------------------------------------------------


def test_running_the_pipeline_produces_an_evidence_set(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    engine = _booted_engine()

    result = engine.run("evidence.extraction", initial_input=_request(tmp_path), correlation_id="corr-1")

    assert result.state is PipelineRunState.COMPLETED
    assert result.succeeded
    assert isinstance(result.output, EvidenceSet)
    assert [record.stage_name for record in result.stage_records] == ["extract_evidence"]


def test_pipeline_output_matches_the_plain_function_interface(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    request = _request(tmp_path)

    via_pipeline = (
        _booted_engine().run("evidence.extraction", initial_input=request, correlation_id="corr-1").output
    )
    via_plain_function = extract_evidence(request)

    strip = {"evidence_set_id": "x", "extracted_at": "x"}
    pipeline_normalized = via_pipeline.model_copy(
        update={
            **strip,
            "evidence": tuple(e.model_copy(update={"collected_at": "x"}) for e in via_pipeline.evidence),
        }
    )
    plain_normalized = via_plain_function.model_copy(
        update={
            **strip,
            "evidence": tuple(
                e.model_copy(update={"collected_at": "x"}) for e in via_plain_function.evidence
            ),
        }
    )
    assert pipeline_normalized == plain_normalized


def test_the_pipeline_invokes_the_container_registered_capability_not_the_engine_directly(
    tmp_path: Path,
) -> None:
    # Proves the pipeline resolves the capability through the Container
    # rather than bypassing it: a Container whose registered stage is
    # replaced entirely must change what the pipeline run returns.
    _build_tree(tmp_path)
    sentinel = object()
    calls: list[str] = []

    def _sentinel_stage(data: Any, _context: PipelineContext) -> tuple[Any, StageOutcome]:
        calls.append("resolved-through-container")
        return sentinel, StageOutcome.SUCCESS

    container = Container()
    container.register(CAPABILITY_EXTRACT_EVIDENCE, lambda: _sentinel_stage)
    engine = PipelineEngine(container)
    register_evidence_pipeline(engine)

    result = engine.run("evidence.extraction", initial_input=_request(tmp_path), correlation_id="corr-1")

    assert calls == ["resolved-through-container"]
    assert result.output is sentinel
