"""Tests for `evidence.module` (Evidence Extraction Engine Architecture Specification v1.1 §11)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from runtime.container.di import Container
from runtime.modules.base import Module
from runtime.modules.manifest import ModuleManifest
from runtime.pipeline.engine import PipelineContext, StageOutcome

from evidence.contract import CanonicalRepository, EvidenceExtractionRequest, EvidenceSet
from evidence.engine import extract_evidence
from evidence.module import CAPABILITY_EXTRACT_EVIDENCE, EvidenceModule

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


def _context() -> PipelineContext:
    return PipelineContext(
        pipeline_run_id="run-1",
        correlation_id="corr-1",
        pipeline_name="evidence.extraction",
        started_at=datetime.now(UTC),
    )


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


def test_evidence_module_is_a_module() -> None:
    assert isinstance(EvidenceModule(_manifest()), Module)


def test_health_check_is_healthy_before_init() -> None:
    assert EvidenceModule(_manifest()).health_check().healthy is True


def test_health_check_is_healthy_after_init() -> None:
    module = EvidenceModule(_manifest())
    module.init(Container())
    assert module.health_check().healthy is True


def test_manifest_requires_no_capabilities() -> None:
    assert _manifest().capabilities_required == ()


def test_init_registers_exactly_one_capability() -> None:
    module = EvidenceModule(_manifest())
    container = Container()

    module.init(container)

    assert container.is_registered(CAPABILITY_EXTRACT_EVIDENCE)
    assert len(_ALL_CAPABILITIES) == 1


def test_init_calls_no_container_resolve() -> None:
    module = EvidenceModule(_manifest())

    module.init(Container())


def test_the_registered_stage_produces_an_evidence_set(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    request = _request(tmp_path)

    module = EvidenceModule(_manifest())
    container = Container()
    module.init(container)

    evidence_set, outcome = container.resolve(CAPABILITY_EXTRACT_EVIDENCE)(request, _context())

    assert outcome is StageOutcome.SUCCESS
    assert isinstance(evidence_set, EvidenceSet)
    assert evidence_set.correlation_id == "corr-1"
    assert evidence_set.evidence


def test_the_registered_stage_matches_the_plain_function_exactly(tmp_path: Path) -> None:
    # The stage wrapper must add nothing: same input, same output as
    # calling extract_evidence() directly (spec SS11 -- "delegates to
    # extract_evidence exactly as-is").
    _build_tree(tmp_path)
    request = _request(tmp_path)

    module = EvidenceModule(_manifest())
    container = Container()
    module.init(container)

    via_stage, _ = container.resolve(CAPABILITY_EXTRACT_EVIDENCE)(request, _context())
    via_plain_function = extract_evidence(request)

    strip = {"evidence_set_id": "x", "extracted_at": "x"}
    stage_normalized = via_stage.model_copy(
        update={
            **strip,
            "evidence": tuple(e.model_copy(update={"collected_at": "x"}) for e in via_stage.evidence),
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
    assert stage_normalized == plain_normalized
