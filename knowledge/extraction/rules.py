"""Extraction rules for a first, deliberately small subset of
docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md's ten source types:
Official Documentation (§1) and Official Source Code (§2) — the two whose
rules are concrete, field-level, and mechanically followable without a real
Parser (docs/crawler/PARSER_SPEC.md, out of Sprint 2's scope) to normalize
arbitrary HTML/source text first.

Every rule function reads `KnowledgeDocument.content.structural_metadata` —
already-parsed structure KNOWLEDGE_PIPELINE.md §4's Normalization stage is
specified to produce. Sprint 2 has no real Normalization stage (see
SPRINT2_IMPLEMENTATION_PLAN.md §3), so this Sprint's own fixtures populate
`structural_metadata` directly, in the shape these rules expect:

    {
      "api_specs": [{"interface_kind", "name", "signature"?, "parameters"?,
                      "return_shape"?, "doctype_scope"?, "span"?}, ...],
      "procedures": [{"title", "steps": [{"order", "description", "invokes"?}], "span"?}, ...],
      "examples":   [{"title", "demonstrates", "code_or_steps", "span"?}, ...],
      "doctype_schemas":     [{same shape as api_specs}, ...],
      "whitelisted_methods": [{same shape as api_specs}, ...],
    }

Per KNOWLEDGE_EXTRACTION_SPEC.md §0, `span` (when present) is carried
forward into the produced artifact's `source_references` as the exact
anchor the claim came from — never a paraphrase with no anchor.
"""

from __future__ import annotations

from typing import Any

from knowledge.artifacts import (
    ArtifactMetadata,
    ArtifactType,
    ContentArtifact,
    Example,
    ExampleContent,
    KnowledgeAPI,
    KnowledgeAPIContent,
    KnowledgeDocument,
    ProvenanceLink,
    SourceReference,
    Workflow,
    WorkflowContent,
    WorkflowStep,
)
from knowledge.extraction.ids import IdAllocator


def extract_from_official_documentation(
    document: KnowledgeDocument, *, id_allocator: IdAllocator
) -> list[ContentArtifact]:
    """KNOWLEDGE_EXTRACTION_SPEC.md §1: field/parameter specs → Knowledge
    API; canonical step-by-step procedures → Workflow; worked examples →
    Example.
    """

    structural = document.content.structural_metadata
    produced: list[ContentArtifact] = []

    for spec in structural.get("api_specs", []):
        produced.append(_build_knowledge_api(document, spec, id_allocator))
    for procedure in structural.get("procedures", []):
        produced.append(_build_workflow(document, procedure, id_allocator))
    for example in structural.get("examples", []):
        produced.append(_build_example(document, example, id_allocator))

    return produced


def extract_from_official_source_code(
    document: KnowledgeDocument, *, id_allocator: IdAllocator
) -> list[ContentArtifact]:
    """KNOWLEDGE_EXTRACTION_SPEC.md §2: DocType JSON schema field
    definitions and `@frappe.whitelist()` method signatures → Knowledge API,
    the highest-confidence source for this artifact type.
    """

    structural = document.content.structural_metadata
    produced: list[ContentArtifact] = []

    for spec in structural.get("doctype_schemas", []):
        produced.append(_build_knowledge_api(document, spec, id_allocator))
    for spec in structural.get("whitelisted_methods", []):
        produced.append(_build_knowledge_api(document, spec, id_allocator))

    return produced


def _source_reference_for(document: KnowledgeDocument, spec: dict[str, Any]) -> SourceReference:
    base = document.source_references[0] if document.source_references else None
    return SourceReference(
        url=base.url if base is not None else "unknown://source",
        retrieved_at=base.retrieved_at if base is not None else document.metadata.extracted_at,
        content_hash=base.content_hash if base is not None else "unknown",
        span=spec.get("span"),
    )


def _provenance_for(document: KnowledgeDocument) -> tuple[ProvenanceLink, ...]:
    return (ProvenanceLink(id=document.id, artifact_type="knowledge_document"),)


def _metadata_for(document: KnowledgeDocument) -> ArtifactMetadata:
    return ArtifactMetadata(
        extracted_at=document.metadata.extracted_at,
        extraction_method=document.metadata.extraction_method,
        extractor_version="0.1.0",
    )


def _build_knowledge_api(
    document: KnowledgeDocument, spec: dict[str, Any], id_allocator: IdAllocator
) -> KnowledgeAPI:
    return KnowledgeAPI(
        id=id_allocator.next_id(ArtifactType.KNOWLEDGE_API),
        metadata=_metadata_for(document),
        version=document.version,
        provenance=_provenance_for(document),
        source_references=(_source_reference_for(document, spec),),
        content=KnowledgeAPIContent(
            interface_kind=spec["interface_kind"],
            name=spec["name"],
            signature=spec.get("signature", ""),
            parameters=tuple(spec.get("parameters", ())),
            return_shape=spec.get("return_shape", ""),
            doctype_scope=spec.get("doctype_scope"),
        ),
    )


def _build_workflow(
    document: KnowledgeDocument, procedure: dict[str, Any], id_allocator: IdAllocator
) -> Workflow:
    steps = tuple(
        WorkflowStep(order=step["order"], description=step["description"], invokes=step.get("invokes"))
        for step in procedure.get("steps", [])
    )
    return Workflow(
        id=id_allocator.next_id(ArtifactType.WORKFLOW),
        metadata=_metadata_for(document),
        version=document.version,
        provenance=_provenance_for(document),
        source_references=(_source_reference_for(document, procedure),),
        content=WorkflowContent(title=procedure["title"], steps=steps),
    )


def _build_example(
    document: KnowledgeDocument, example: dict[str, Any], id_allocator: IdAllocator
) -> Example:
    return Example(
        id=id_allocator.next_id(ArtifactType.EXAMPLE),
        metadata=_metadata_for(document),
        version=document.version,
        provenance=_provenance_for(document),
        source_references=(_source_reference_for(document, example),),
        tags=tuple(example.get("tags", ())),
        content=ExampleContent(
            title=example["title"],
            demonstrates=example["demonstrates"],
            code_or_steps=example["code_or_steps"],
        ),
    )
