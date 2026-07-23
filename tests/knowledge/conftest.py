"""Shared fixtures for Knowledge Factory tests.

Every fixture builds fully in-memory, disposable objects — no filesystem,
no shared state, no execution-order dependence, matching the discipline
tests/conftest.py already establishes for the Runtime's own tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from knowledge.artifacts import (
    ArtifactMetadata,
    ArtifactVersionInfo,
    BestPractice,
    BestPracticeContent,
    ContentArtifact,
    KnowledgeAPI,
    KnowledgeAPIContent,
    KnowledgeDocument,
    KnowledgeDocumentContent,
    Pattern,
    PatternContent,
    SourceReference,
)
from knowledge.conflict import PrecedenceTier
from knowledge.conflict.providers import PRECEDENCE_PROVIDER_CAPABILITY
from knowledge.extraction.module import EVENT_BUS_CAPABILITY as _EXTRACTOR_EVENT_BUS_CAPABILITY
from knowledge.pipelines import register_knowledge_pipelines
from knowledge.validation.module import ValidatorModule
from runtime.container.di import Container
from runtime.events.bus import EventBus
from runtime.pipeline.engine import PipelineContext, PipelineEngine
from runtime.registry.plugin_registry import PluginRegistry

_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


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


@pytest.fixture
def make_pattern() -> Callable[..., Pattern]:
    def _make(pattern_id: str = "PAT-0001", **overrides: object) -> Pattern:
        defaults: dict[str, object] = {
            "id": pattern_id,
            "metadata": _metadata(),
            "version": ArtifactVersionInfo(applies_to="v15"),
            "confidence": 0.9,
            "source_references": (_source_ref(),),
            "content": PatternContent(
                title="Thin Hooks, Centralized Service Layer",
                problem="fat hooks with business logic inline",
                solution_shape="hook delegates to a testable service module",
            ),
        }
        defaults.update(overrides)
        return Pattern(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_best_practice() -> Callable[..., BestPractice]:
    def _make(bp_id: str = "BP-0001", **overrides: object) -> BestPractice:
        defaults: dict[str, object] = {
            "id": bp_id,
            "metadata": _metadata(),
            "version": ArtifactVersionInfo(applies_to="v15"),
            "confidence": 0.7,
            "source_references": (_source_ref(),),
            "content": BestPracticeContent(
                title="Prefer Workflow over Client Script for state transitions",
                recommendation="use the Workflow doctype",
            ),
        }
        defaults.update(overrides)
        return BestPractice(**defaults)  # type: ignore[arg-type]

    return _make


class StaticSourceVerifier:
    """A `SourceVerifier` test double returning a fixed, configurable result."""

    def __init__(self, result: bool = True) -> None:
        self.result = result

    def verify(self, artifact: ContentArtifact) -> bool:
        del artifact
        return self.result


class StaticTrustScoreProvider:
    """A `TrustScoreProvider` test double: a default score, with optional
    per-artifact-id overrides for tests that need one artifact to differ.
    """

    def __init__(self, score: int = 100, overrides: dict[str, int] | None = None) -> None:
        self.score = score
        self.overrides = overrides or {}

    def trust_score(self, artifact: ContentArtifact) -> int:
        return self.overrides.get(artifact.id, self.score)


class StaticPrecedenceProvider:
    """A `PrecedenceProvider` test double: a default tier, with optional
    per-artifact-id overrides.
    """

    def __init__(
        self,
        tier: PrecedenceTier = PrecedenceTier.OFFICIAL_DOCUMENTATION,
        overrides: dict[str, PrecedenceTier] | None = None,
    ) -> None:
        self.tier = tier
        self.overrides = overrides or {}

    def precedence_tier(self, artifact: ContentArtifact) -> PrecedenceTier:
        return self.overrides.get(artifact.id, self.tier)


@pytest.fixture
def source_verifier() -> StaticSourceVerifier:
    return StaticSourceVerifier(result=True)


@pytest.fixture
def trust_score_provider() -> StaticTrustScoreProvider:
    return StaticTrustScoreProvider(score=100)


@pytest.fixture
def precedence_provider() -> StaticPrecedenceProvider:
    return StaticPrecedenceProvider(tier=PrecedenceTier.OFFICIAL_DOCUMENTATION)


@pytest.fixture
def pipeline_context() -> PipelineContext:
    return PipelineContext(
        pipeline_run_id="run-1", correlation_id="run-1", pipeline_name="test", started_at=datetime.now(UTC)
    )


def fixture_document() -> KnowledgeDocument:
    """A `Knowledge Document` shaped for `official_documentation` extraction
    (knowledge/extraction/rules.py), reused by the end-to-end integration
    and event-publication tests.
    """

    return KnowledgeDocument(
        id="KD-0001",
        metadata=_metadata(extraction_method="official_documentation"),
        version=ArtifactVersionInfo(applies_to="v15"),
        source_references=(_source_ref(url="https://docs.frappe.io/framework/user/en/api/client"),),
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


@pytest.fixture
def wired_engine() -> PipelineEngine:
    """Discovers and boots the real `extractor`/`validator` plugins from the
    repository's own `plugins/` directory — the same directory
    `architect doctor`/`Runtime.boot()` would scan — against a fresh
    Container, EventBus, and PipelineEngine with both Sprint 2 Pipeline
    Definitions registered. Used by the end-to-end integration and
    event-publication tests.
    """

    registry = PluginRegistry()
    registry.register_all(registry.discover([_PLUGINS_DIR]))
    registry.validate_dependencies()

    container = Container()
    container.register(ValidatorModule.SOURCE_VERIFIER_CAPABILITY, lambda: StaticSourceVerifier(True))
    container.register(
        ValidatorModule.TRUST_SCORE_PROVIDER_CAPABILITY, lambda: StaticTrustScoreProvider(score=90)
    )
    container.register(PRECEDENCE_PROVIDER_CAPABILITY, lambda: StaticPrecedenceProvider())
    bus = EventBus()
    container.register(_EXTRACTOR_EVENT_BUS_CAPABILITY, lambda: bus)

    for module_id in registry.dependency_order():
        instance = registry.instantiate(module_id)
        instance.validate()
        instance.init(container)
        instance.start()

    engine = PipelineEngine(container, event_bus=bus)
    register_knowledge_pipelines(engine)
    return engine
