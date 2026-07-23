"""Shared fixtures for Knowledge Factory tests.

Every fixture builds fully in-memory, disposable objects — no filesystem,
no shared state, no execution-order dependence, matching the discipline
tests/conftest.py already establishes for the Runtime's own tests.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from knowledge.artifacts import (
    ArtifactMetadata,
    ArtifactVersionInfo,
    KnowledgeAPI,
    KnowledgeAPIContent,
    KnowledgeDocument,
    KnowledgeDocumentContent,
    SourceReference,
)


def _metadata(**overrides: object) -> ArtifactMetadata:
    defaults: dict[str, object] = {
        "extracted_at": "2026-01-01T00:00:00Z",
        "extraction_method": "fixture",
        "extractor_version": "0.1.0",
    }
    defaults.update(overrides)
    return ArtifactMetadata(**defaults)  # type: ignore[arg-type]


def _source_ref(**overrides: object) -> SourceReference:
    defaults: dict[str, object] = {
        "url": "https://example.invalid/doc",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "content_hash": "sha256:fixture",
        "span": "fixture span",
    }
    defaults.update(overrides)
    return SourceReference(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def make_metadata() -> Callable[..., ArtifactMetadata]:
    return _metadata


@pytest.fixture
def make_source_ref() -> Callable[..., SourceReference]:
    return _source_ref


@pytest.fixture
def make_knowledge_document() -> Callable[..., KnowledgeDocument]:
    def _make(doc_id: str = "KD-0001", **overrides: object) -> KnowledgeDocument:
        defaults: dict[str, object] = {
            "id": doc_id,
            "metadata": _metadata(),
            "version": ArtifactVersionInfo(applies_to="v15"),
            "source_references": (_source_ref(),),
            "content": KnowledgeDocumentContent(raw_text="raw", cleaned_text="cleaned", format="markdown"),
        }
        defaults.update(overrides)
        return KnowledgeDocument(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_knowledge_api() -> Callable[..., KnowledgeAPI]:
    def _make(api_id: str = "KA-0001", **overrides: object) -> KnowledgeAPI:
        defaults: dict[str, object] = {
            "id": api_id,
            "metadata": _metadata(),
            "version": ArtifactVersionInfo(applies_to="v15"),
            "confidence": 0.9,
            "source_references": (_source_ref(),),
            "content": KnowledgeAPIContent(
                interface_kind="whitelisted-method",
                name="frappe.client.get_list",
                signature="get_list(doctype, filters=None)",
            ),
        }
        defaults.update(overrides)
        return KnowledgeAPI(**defaults)  # type: ignore[arg-type]

    return _make
