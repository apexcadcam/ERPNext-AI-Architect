"""Sprint 11, Phase 3 — Provider Integration Validation.

Validates the real, already-wired `intelligence.pipeline` against every
supported `IntelligenceEngine` implementation: `NullIntelligenceEngine`,
`ValidatingIntelligenceEngine` (wrapping either of the other two), and
`AnthropicAdapter`. The Pipeline and Bridge are always real, unmocked
code; only `AnthropicAdapter`'s own external boundary (`AnthropicClientProtocol`)
is faked, mirroring `tests/intelligence/test_anthropic_adapter.py`'s own
`_ScriptedClient` convention exactly — zero network access, zero vendor
SDK import.

No new provider, contract, or pipeline behavior is introduced here. Where
a "candidates only" or a fabricated-citation scenario has no natural
route through the real `analysis.requirements` -> `knowledge.builder` ->
`knowledge.projection` chain, a `KnowledgeCollection`/`Workflow` is
assembled directly from real, frozen Knowledge types (no mocks) — the
same technique already used once in `tests/intelligence/test_pipeline.py`'s
own `_snapshot_with_edge` fixture.

Self-contained, mirroring every other test file in this project's own
discipline: fixtures are rebuilt here, not imported from a sibling test
file.
"""

from __future__ import annotations

import json

import pytest

from analysis.requirements.analyzer import build_analysis_result
from analysis.requirements.raw import RawEntityMention, RawProcessMention, RawRequirement
from knowledge.artifacts import ArtifactMetadata, ArtifactVersionInfo, Workflow, WorkflowContent, WorkflowStep
from knowledge.builder.builder import build_knowledge_snapshot
from knowledge.domain import KnowledgeCollection, KnowledgeSnapshot
from knowledge.projection.projector import project_snapshot

from intelligence.adapters.anthropic_adapter import AnthropicAdapter
from intelligence.contract import TradeoffAssessment
from intelligence.errors import CitationError
from intelligence.null_engine import NullIntelligenceEngine
from intelligence.pipeline import collect_candidates, collect_evidence, evaluate_knowledge_snapshot
from intelligence.validating import ValidatingIntelligenceEngine

_CREATED_AT = "2026-01-01T00:00:00Z"


def _realistic_snapshot() -> KnowledgeSnapshot:
    requirement = RawRequirement(
        requirement_id="REQ-1",
        description="Track patient registration.",
        entities=(RawEntityMention(name="Patient", excerpt="a patient record"),),
        processes=(
            RawProcessMention(
                name="Patient Registration",
                excerpt="register new patients",
                steps=("collect identity",),
                actors=(),
            ),
        ),
    )
    analysis_result = build_analysis_result(requirement)
    built = build_knowledge_snapshot(analysis_result, created_at=_CREATED_AT)
    return project_snapshot(built)


def _empty_snapshot() -> KnowledgeSnapshot:
    requirement = RawRequirement(requirement_id="REQ-EMPTY", description="Nothing to extract.")
    return build_knowledge_snapshot(build_analysis_result(requirement), created_at=_CREATED_AT)


def _evidence_only_snapshot() -> KnowledgeSnapshot:
    """An entity mention with no process -- `knowledge.builder` produces
    only a `KnowledgeReference` for a `BusinessEntity` (never a
    `ContentArtifact`), so this snapshot has evidence but zero candidates.
    """

    requirement = RawRequirement(
        requirement_id="REQ-EVIDENCE-ONLY",
        description="Just an entity, no process.",
        entities=(RawEntityMention(name="Invoice", excerpt="an invoice record"),),
    )
    return build_knowledge_snapshot(build_analysis_result(requirement), created_at=_CREATED_AT)


def _candidates_only_snapshot() -> KnowledgeSnapshot:
    """A hand-assembled snapshot with one real `Workflow` artifact and no
    references/nodes/edges -- the real builder always pairs a `Workflow`
    with a same-subject `KnowledgeReference` (see `knowledge.builder.
    builder`'s own `build_knowledge_collection`), so "candidates only,
    zero evidence" has no natural route through the real pipeline; this
    fixture proves the scenario directly instead, using only real, frozen
    Knowledge types.
    """

    requirement = RawRequirement(requirement_id="REQ-CANDIDATES-ONLY", description="An option, no evidence.")
    analysis_result = build_analysis_result(requirement)
    workflow = Workflow(
        id="WF-manual",
        metadata=ArtifactMetadata(
            extracted_at=_CREATED_AT, extraction_method="test", extractor_version="0.1.0"
        ),
        version=ArtifactVersionInfo(),
        content=WorkflowContent(title="Manual Workflow", steps=(WorkflowStep(order=0, description="step"),)),
    )
    collection = KnowledgeCollection(collection_id="collection:manual", name="manual", artifacts=(workflow,))
    return KnowledgeSnapshot(
        snapshot_id="snapshot:manual",
        created_at=_CREATED_AT,
        source=analysis_result,
        collections=(collection,),
    )


class _ScriptedClient:
    """A fake `AnthropicClientProtocol` (structural, no import of it
    required) returning one fixed, pre-scripted raw response -- mirrors
    `tests/intelligence/test_anthropic_adapter.py`'s own fixture exactly.
    Zero network access; the real Anthropic API is never called.
    """

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    def create_message(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._response


def _scripted_tradeoff_response(*, candidate_ids: list[str], evidence_ids: list[str]) -> str:
    return json.dumps(
        {"ranked_candidate_ids": candidate_ids, "rationale": "scripted", "cited_evidence_ids": evidence_ids}
    )


# == 1. NullIntelligenceEngine ========================================================================


def test_null_engine_successful_execution() -> None:
    snapshot = _realistic_snapshot()
    result = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    assert isinstance(result, TradeoffAssessment)
    assert set(result.ranked_candidate_ids) == {c.candidate_id for c in collect_candidates(snapshot)}


def test_null_engine_deterministic_repeated_execution() -> None:
    snapshot = _realistic_snapshot()
    first = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    second = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    assert first == second


def test_null_engine_empty_snapshot() -> None:
    result = evaluate_knowledge_snapshot(_empty_snapshot(), NullIntelligenceEngine())
    assert result == TradeoffAssessment(
        ranked_candidate_ids=(), rationale="no candidates supplied to rank", cited_evidence_ids=()
    )


def test_null_engine_evidence_only_snapshot() -> None:
    snapshot = _evidence_only_snapshot()
    assert collect_evidence(snapshot) != ()
    assert collect_candidates(snapshot) == ()
    result = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    assert result.ranked_candidate_ids == ()
    assert result.rationale == "no candidates supplied to rank"


def test_null_engine_candidates_only_snapshot() -> None:
    snapshot = _candidates_only_snapshot()
    assert collect_evidence(snapshot) == ()
    assert collect_candidates(snapshot) != ()
    result = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    assert result.ranked_candidate_ids == ("WF-manual",)
    assert result.cited_evidence_ids == ()


# == 2. ValidatingIntelligenceEngine ===================================================================


def test_validating_engine_wrapping_null_engine_passes_through_unchanged() -> None:
    snapshot = _realistic_snapshot()
    unwrapped = evaluate_knowledge_snapshot(snapshot, NullIntelligenceEngine())
    wrapped = evaluate_knowledge_snapshot(snapshot, ValidatingIntelligenceEngine(NullIntelligenceEngine()))
    assert wrapped == unwrapped


def test_validating_engine_accepts_a_real_valid_citation_from_anthropic_adapter() -> None:
    snapshot = _realistic_snapshot()
    candidates = collect_candidates(snapshot)
    evidence = collect_evidence(snapshot)
    response = _scripted_tradeoff_response(
        candidate_ids=[c.candidate_id for c in candidates], evidence_ids=[evidence[0].reference_id]
    )
    engine = ValidatingIntelligenceEngine(AnthropicAdapter(_ScriptedClient(response)))
    result = evaluate_knowledge_snapshot(snapshot, engine)
    assert result.cited_evidence_ids == (evidence[0].reference_id,)


def test_validating_engine_rejects_a_fabricated_evidence_citation() -> None:
    snapshot = _realistic_snapshot()
    candidates = collect_candidates(snapshot)
    response = _scripted_tradeoff_response(
        candidate_ids=[c.candidate_id for c in candidates], evidence_ids=["fabricated-id-not-in-input"]
    )
    engine = ValidatingIntelligenceEngine(AnthropicAdapter(_ScriptedClient(response)))
    with pytest.raises(CitationError):
        evaluate_knowledge_snapshot(snapshot, engine)


def test_validating_engine_rejects_a_fabricated_candidate_citation() -> None:
    snapshot = _realistic_snapshot()
    response = _scripted_tradeoff_response(
        candidate_ids=["fabricated-candidate-not-in-input"], evidence_ids=[]
    )
    engine = ValidatingIntelligenceEngine(AnthropicAdapter(_ScriptedClient(response)))
    with pytest.raises(CitationError):
        evaluate_knowledge_snapshot(snapshot, engine)


def test_validating_engine_enforcement_applies_identically_regardless_of_wrapped_provider() -> None:
    # Same fabricated-citation scenario, both supported non-Null providers
    # this project ships -- proves the wrapper's enforcement is a property
    # of ValidatingIntelligenceEngine itself, not something each provider
    # must separately opt into.
    snapshot = _realistic_snapshot()
    bad_response = _scripted_tradeoff_response(candidate_ids=[], evidence_ids=["not-real"])
    with pytest.raises(CitationError):
        evaluate_knowledge_snapshot(
            snapshot, ValidatingIntelligenceEngine(AnthropicAdapter(_ScriptedClient(bad_response)))
        )
    # NullIntelligenceEngine can never produce a fabricated citation by
    # construction (it only ever echoes ids it was actually given), so
    # the wrapper has nothing to reject for it -- the absence of an error
    # here is the expected, honest outcome, not a gap in enforcement.
    evaluate_knowledge_snapshot(snapshot, ValidatingIntelligenceEngine(NullIntelligenceEngine()))


# == 3. AnthropicAdapter ================================================================================


def test_anthropic_adapter_produces_a_valid_tradeoff_assessment_via_the_real_pipeline() -> None:
    snapshot = _realistic_snapshot()
    candidates = collect_candidates(snapshot)
    evidence = collect_evidence(snapshot)
    response = _scripted_tradeoff_response(
        candidate_ids=[c.candidate_id for c in candidates], evidence_ids=[e.reference_id for e in evidence]
    )
    result = evaluate_knowledge_snapshot(snapshot, AnthropicAdapter(_ScriptedClient(response)))
    assert result == TradeoffAssessment(
        ranked_candidate_ids=tuple(c.candidate_id for c in candidates),
        rationale="scripted",
        cited_evidence_ids=tuple(e.reference_id for e in evidence),
    )


def test_anthropic_adapter_receives_exactly_the_pipelines_own_translated_evidence_and_candidates() -> None:
    snapshot = _realistic_snapshot()
    candidates = collect_candidates(snapshot)
    evidence = collect_evidence(snapshot)
    client = _ScriptedClient(_scripted_tradeoff_response(candidate_ids=[], evidence_ids=[]))
    evaluate_knowledge_snapshot(snapshot, AnthropicAdapter(client))

    assert len(client.calls) == 1
    _system, user_payload = client.calls[0]
    sent = json.loads(user_payload)
    assert {item["reference_id"] for item in sent["evidence"]} == {item.reference_id for item in evidence}
    assert {item["candidate_id"] for item in sent["candidates"]} == {c.candidate_id for c in candidates}


def test_anthropic_adapter_never_receives_a_raw_knowledge_object() -> None:
    # The payload sent to the client must contain only EvidenceItem/
    # Candidate's own field names -- proof the provider consumes Bridge's
    # translated shape, never a raw Knowledge object's own fields
    # (e.g. no "wraps_type", "content", or "subject_kind" anywhere).
    snapshot = _realistic_snapshot()
    client = _ScriptedClient(_scripted_tradeoff_response(candidate_ids=[], evidence_ids=[]))
    evaluate_knowledge_snapshot(snapshot, AnthropicAdapter(client))
    _system, user_payload = client.calls[0]
    sent = json.loads(user_payload)
    for item in sent["evidence"]:
        assert set(item) == {"reference_id", "summary", "weight"}
    for item in sent["candidates"]:
        assert set(item) == {"candidate_id", "description", "supporting_evidence_ids"}


def test_anthropic_adapter_empty_snapshot() -> None:
    client = _ScriptedClient(_scripted_tradeoff_response(candidate_ids=[], evidence_ids=[]))
    result = evaluate_knowledge_snapshot(_empty_snapshot(), AnthropicAdapter(client))
    assert result == TradeoffAssessment(rationale="scripted")
