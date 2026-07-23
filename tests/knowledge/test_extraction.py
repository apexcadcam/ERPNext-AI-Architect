"""Tests for Extraction (KNOWLEDGE_EXTRACTION_SPEC.md §§1-2)."""

from __future__ import annotations

import time
from collections.abc import Callable

from knowledge.artifacts import ArtifactType, KnowledgeAPI, KnowledgeDocument, KnowledgeDocumentContent
from knowledge.extraction import IdAllocator, extract
from runtime.events.bus import EventBus
from runtime.pipeline.engine import PipelineContext, StageOutcome


def test_extract_from_official_documentation_produces_a_knowledge_api(
    make_knowledge_document: Callable[..., KnowledgeDocument], pipeline_context: PipelineContext
) -> None:
    document = make_knowledge_document(
        metadata=make_knowledge_document().metadata.model_copy(
            update={"extraction_method": "official_documentation"}
        ),
        content=KnowledgeDocumentContent(
            raw_text="...",
            format="markdown",
            structural_metadata={
                "api_specs": [
                    {
                        "interface_kind": "whitelisted-method",
                        "name": "frappe.client.get_list",
                        "signature": "get_list(doctype, filters=None)",
                        "span": "## get_list",
                    }
                ]
            },
        ),
    )

    produced, outcome = extract(document, pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    assert len(produced) == 1
    api = produced[0]
    assert isinstance(api, KnowledgeAPI)
    assert api.type is ArtifactType.KNOWLEDGE_API
    assert api.content.name == "frappe.client.get_list"
    assert api.source_references[0].span == "## get_list"
    assert api.provenance[0].id == document.id


def test_extract_from_official_documentation_produces_workflow_and_example(
    make_knowledge_document: Callable[..., KnowledgeDocument], pipeline_context: PipelineContext
) -> None:
    document = make_knowledge_document(
        metadata=make_knowledge_document().metadata.model_copy(
            update={"extraction_method": "official_documentation"}
        ),
        content=KnowledgeDocumentContent(
            raw_text="...",
            format="markdown",
            structural_metadata={
                "procedures": [
                    {
                        "title": "Adding a Workflow state",
                        "steps": [
                            {"order": 1, "description": "Open the Workflow doctype"},
                            {"order": 2, "description": "Add a new state", "invokes": "KA-0001"},
                        ],
                    }
                ],
                "examples": [
                    {"title": "Register a hook", "demonstrates": "doc_events", "code_or_steps": "..."}
                ],
            },
        ),
    )

    produced, outcome = extract(document, pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    types = {artifact.type for artifact in produced}
    assert types == {ArtifactType.WORKFLOW, ArtifactType.EXAMPLE}
    workflow = next(a for a in produced if a.type is ArtifactType.WORKFLOW)
    assert len(workflow.content.steps) == 2
    assert workflow.content.steps[1].invokes == "KA-0001"


def test_extract_from_official_source_code_produces_knowledge_apis(
    make_knowledge_document: Callable[..., KnowledgeDocument], pipeline_context: PipelineContext
) -> None:
    document = make_knowledge_document(
        metadata=make_knowledge_document().metadata.model_copy(update={"extraction_method": "source_code"}),
        content=KnowledgeDocumentContent(
            raw_text="...",
            format="python",
            structural_metadata={
                "doctype_schemas": [
                    {
                        "interface_kind": "doctype-field",
                        "name": "Sales Invoice.customer",
                        "doctype_scope": "Sales Invoice",
                    }
                ],
                "whitelisted_methods": [
                    {"interface_kind": "whitelisted-method", "name": "erpnext.get_item_details"}
                ],
            },
        ),
    )

    produced, outcome = extract(document, pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS
    assert len(produced) == 2
    apis = [a for a in produced if isinstance(a, KnowledgeAPI)]
    assert len(apis) == 2
    assert {a.content.name for a in apis} == {"Sales Invoice.customer", "erpnext.get_item_details"}


def test_extract_from_an_out_of_scope_source_type_produces_nothing(
    make_knowledge_document: Callable[..., KnowledgeDocument], pipeline_context: PipelineContext
) -> None:
    document = make_knowledge_document(
        metadata=make_knowledge_document().metadata.model_copy(
            update={"extraction_method": "video_transcript"}
        ),
    )

    produced, outcome = extract(document, pipeline_context, id_allocator=IdAllocator())

    assert outcome is StageOutcome.SUCCESS  # unsupported source type is a scope boundary, not a failure
    assert produced == []


def test_extract_publishes_artifact_created_per_produced_artifact(
    make_knowledge_document: Callable[..., KnowledgeDocument], pipeline_context: PipelineContext
) -> None:
    document = make_knowledge_document(
        metadata=make_knowledge_document().metadata.model_copy(
            update={"extraction_method": "official_documentation"}
        ),
        content=KnowledgeDocumentContent(
            raw_text="...",
            format="markdown",
            structural_metadata={
                "api_specs": [{"interface_kind": "whitelisted-method", "name": "frappe.client.get_list"}]
            },
        ),
    )
    bus = EventBus()
    received: list[dict[str, object]] = []
    bus.subscribe("ArtifactCreated", lambda e: received.append(e.payload))

    extract(document, pipeline_context, id_allocator=IdAllocator(), event_bus=bus)

    _wait_until(lambda: len(received) == 1)
    assert received[0]["artifact_type"] == "knowledge_api"
    bus.shutdown()


def test_id_allocator_issues_unique_sequential_ids_per_type() -> None:
    allocator = IdAllocator()
    first = allocator.next_id(ArtifactType.KNOWLEDGE_API)
    second = allocator.next_id(ArtifactType.KNOWLEDGE_API)
    other_type = allocator.next_id(ArtifactType.WORKFLOW)

    assert first == "KA-0001"
    assert second == "KA-0002"
    assert other_type == "WF-0001"


def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0, interval: float = 0.01) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("condition not met before timeout")
