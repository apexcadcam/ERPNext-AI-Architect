"""End-to-end tests: the real `extractor`/`validator` plugins, discovered
from the actual `plugins/` directory and run through a real
`runtime.pipeline.engine.PipelineEngine`, exactly the path a real Runtime
boot would take (runtime/boot.py's `_start_modules`/`_start_one_module`),
proving the Sprint 2 wiring — not just the underlying gate/extraction
functions in isolation — actually works. See `wired_engine`/`fixture_document`
in conftest.py for the shared setup.
"""

from __future__ import annotations

from knowledge.artifacts import ArtifactStatus, ArtifactType
from runtime.pipeline.engine import PipelineEngine

from tests.knowledge.conftest import fixture_document


def test_knowledge_graph_build_produces_a_knowledge_api(wired_engine: PipelineEngine) -> None:
    result = wired_engine.run("knowledge.graph_build", initial_input=fixture_document())

    assert result.succeeded
    assert len(result.output) == 1
    assert result.output[0].type is ArtifactType.KNOWLEDGE_API


def test_the_extracted_artifact_passes_end_to_end_through_validation(wired_engine: PipelineEngine) -> None:
    extraction_result = wired_engine.run("knowledge.graph_build", initial_input=fixture_document())
    extracted_artifact = extraction_result.output[0]

    validation_result = wired_engine.run("knowledge.validation", initial_input=extracted_artifact)

    assert validation_result.succeeded
    validated = validation_result.output
    assert validated.status is ArtifactStatus.VALIDATED
    assert 0.0 < validated.confidence <= 1.0
    assert [r.stage_name for r in validation_result.stage_records] == [
        "schema_validation",
        "duplicate_detection",
        "version_conflict_detection",
        "source_verification",
        "trust_verification",
        "engineering_review",
        "human_approval_gate",
        "confidence_scoring",
    ]


def test_an_artifact_with_no_source_references_is_rejected_and_retained(wired_engine: PipelineEngine) -> None:
    extraction_result = wired_engine.run("knowledge.graph_build", initial_input=fixture_document())
    extracted_artifact = extraction_result.output[0]
    unsourced = extracted_artifact.model_copy(update={"source_references": ()})

    validation_result = wired_engine.run("knowledge.validation", initial_input=unsourced)

    assert validation_result.succeeded  # the pipeline run itself succeeds
    assert validation_result.output.status is ArtifactStatus.REJECTED  # the artifact is rejected, not lost


def test_registered_pipelines_are_exactly_the_two_sprint_2_definitions(wired_engine: PipelineEngine) -> None:
    assert set(wired_engine.registered_pipelines()) == {"knowledge.validation", "knowledge.graph_build"}
