"""Tests for `AnthropicAdapter` (Sprint 8 Implementation Plan, Phase 4).
Uses only a scripted fake `AnthropicClientProtocol` — zero network access,
the real Anthropic API is never called. Valid parsing, malformed/missing/
schema-invalid responses, and the citation guard when wrapped by
`ValidatingIntelligenceEngine` (Phase 2, unmodified).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from intelligence.adapters.anthropic_adapter import (
    AnthropicAdapter,
    AnthropicClientProtocol,
    MalformedResponseError,
)
from intelligence.contract import (
    ArchitectureCritique,
    AssumptionChallenge,
    Candidate,
    EvidenceItem,
    ProposedArchitecture,
    Requirement,
    RequirementUnderstanding,
    TradeoffAssessment,
)
from intelligence.errors import CitationError
from intelligence.validating import ValidatingIntelligenceEngine

INTELLIGENCE_DIR = Path(__file__).resolve().parents[2] / "intelligence"


class _ScriptedClient:
    """A fake `AnthropicClientProtocol` returning one fixed, pre-scripted
    raw response regardless of what it's asked — proves `AnthropicAdapter`
    depends only on the Protocol's shape, never a concrete SDK type, and
    never touches the network.
    """

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    def create_message(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._response


def _adapter(response: str) -> AnthropicAdapter:
    return AnthropicAdapter(_ScriptedClient(response))


# -- Protocol shape -------------------------------------------------------------------------------


def test_scripted_client_structurally_satisfies_the_protocol() -> None:
    assert isinstance(_ScriptedClient("{}"), AnthropicClientProtocol)


def test_adapter_is_an_intelligence_engine() -> None:
    from intelligence.contract import IntelligenceEngine

    assert isinstance(_adapter("{}"), IntelligenceEngine)


# -- interpret_requirement --------------------------------------------------------------------


def test_interpret_requirement_parses_a_valid_response() -> None:
    response = json.dumps(
        {
            "requirement_id": "R-1",
            "key_concepts": ["patient identity", "billing"],
            "ambiguities": [],
            "restated_requirement": "track patient identity and billing",
        }
    )
    understanding = _adapter(response).interpret_requirement(
        Requirement(requirement_id="R-1", description="track patients")
    )
    assert understanding == RequirementUnderstanding(
        requirement_id="R-1",
        key_concepts=("patient identity", "billing"),
        ambiguities=(),
        restated_requirement="track patient identity and billing",
    )


def test_interpret_requirement_sends_the_requirement_as_the_user_payload() -> None:
    client = _ScriptedClient(json.dumps({"requirement_id": "R-1", "restated_requirement": "x"}))
    AnthropicAdapter(client).interpret_requirement(Requirement(requirement_id="R-1", description="x"))
    (_, user) = client.calls[0]
    assert json.loads(user) == {"requirement_id": "R-1", "description": "x", "context_notes": ""}


def test_interpret_requirement_raises_on_malformed_json() -> None:
    with pytest.raises(MalformedResponseError, match="not valid JSON"):
        _adapter("not json at all {{{").interpret_requirement(
            Requirement(requirement_id="R-1", description="x")
        )


def test_interpret_requirement_raises_on_missing_required_field() -> None:
    # "restated_requirement" is required and missing.
    response = json.dumps({"requirement_id": "R-1"})
    with pytest.raises(MalformedResponseError, match="RequirementUnderstanding"):
        _adapter(response).interpret_requirement(Requirement(requirement_id="R-1", description="x"))


# -- evaluate_tradeoff --------------------------------------------------------------------------


def test_evaluate_tradeoff_parses_a_valid_response() -> None:
    response = json.dumps(
        {"ranked_candidate_ids": ["C-1", "C-2"], "rationale": "x", "cited_evidence_ids": ["E-1"]}
    )
    assessment = _adapter(response).evaluate_tradeoff(
        (EvidenceItem(reference_id="E-1", summary="x"),),
        (Candidate(candidate_id="C-1", description="x"), Candidate(candidate_id="C-2", description="y")),
    )
    assert assessment == TradeoffAssessment(
        ranked_candidate_ids=("C-1", "C-2"), rationale="x", cited_evidence_ids=("E-1",)
    )


def test_evaluate_tradeoff_raises_on_malformed_json() -> None:
    with pytest.raises(MalformedResponseError, match="not valid JSON"):
        _adapter("{not valid").evaluate_tradeoff((), ())


def test_evaluate_tradeoff_raises_on_missing_required_field() -> None:
    # "rationale" is required and missing.
    response = json.dumps({"ranked_candidate_ids": ["C-1"]})
    with pytest.raises(MalformedResponseError, match="TradeoffAssessment"):
        _adapter(response).evaluate_tradeoff((), (Candidate(candidate_id="C-1", description="x"),))


def test_evaluate_tradeoff_raises_on_a_schema_violation() -> None:
    # "ranked_candidate_ids" must be an array of strings, not a single string.
    response = json.dumps({"ranked_candidate_ids": "C-1", "rationale": "x"})
    with pytest.raises(MalformedResponseError, match="TradeoffAssessment"):
        _adapter(response).evaluate_tradeoff((), (Candidate(candidate_id="C-1", description="x"),))


# -- critique_architecture ------------------------------------------------------------------------


def test_critique_architecture_parses_a_valid_response() -> None:
    response = json.dumps({"concerns": ["duplicates Customer"], "cited_evidence_ids": ["E-1"]})
    critique = _adapter(response).critique_architecture(
        ProposedArchitecture(summary="x"), (EvidenceItem(reference_id="E-1", summary="y"),)
    )
    assert critique == ArchitectureCritique(concerns=("duplicates Customer",), cited_evidence_ids=("E-1",))


def test_critique_architecture_parses_an_empty_valid_response() -> None:
    critique = _adapter("{}").critique_architecture(ProposedArchitecture(summary="x"), ())
    assert critique == ArchitectureCritique()


def test_critique_architecture_raises_on_malformed_json() -> None:
    with pytest.raises(MalformedResponseError, match="not valid JSON"):
        _adapter("<<not json>>").critique_architecture(ProposedArchitecture(summary="x"), ())


def test_critique_architecture_raises_on_a_schema_violation() -> None:
    # "concerns" must be an array, not an object.
    response = json.dumps({"concerns": {"not": "an array"}})
    with pytest.raises(MalformedResponseError, match="ArchitectureCritique"):
        _adapter(response).critique_architecture(ProposedArchitecture(summary="x"), ())


# -- challenge_assumptions ------------------------------------------------------------------------


def test_challenge_assumptions_parses_a_valid_response() -> None:
    response = json.dumps(
        {
            "challenged_assumptions": [
                {
                    "assumption": "Patient should be a new DocType",
                    "challenge": "why not extend Customer?",
                    "resolution": "assumption_rejected",
                    "resolution_rationale": "Customer already models identity and billing",
                }
            ],
            "cited_evidence_ids": ["E-1"],
        }
    )
    challenge = _adapter(response).challenge_assumptions(
        ProposedArchitecture(summary="x"), (EvidenceItem(reference_id="E-1", summary="y"),)
    )
    assert len(challenge.challenged_assumptions) == 1
    assert challenge.challenged_assumptions[0].resolution == "assumption_rejected"


def test_challenge_assumptions_parses_an_empty_valid_response() -> None:
    challenge = _adapter("{}").challenge_assumptions(ProposedArchitecture(summary="x"), ())
    assert challenge == AssumptionChallenge()


def test_challenge_assumptions_raises_on_missing_required_field() -> None:
    # "resolution_rationale" is required and missing.
    response = json.dumps(
        {"challenged_assumptions": [{"assumption": "x", "challenge": "y", "resolution": "unresolved"}]}
    )
    with pytest.raises(MalformedResponseError, match="AssumptionChallenge"):
        _adapter(response).challenge_assumptions(ProposedArchitecture(summary="x"), ())


def test_challenge_assumptions_raises_on_a_schema_violation() -> None:
    # "resolution" must be one of the three approved literals.
    response = json.dumps(
        {
            "challenged_assumptions": [
                {
                    "assumption": "x",
                    "challenge": "y",
                    "resolution": "maybe",
                    "resolution_rationale": "z",
                }
            ]
        }
    )
    with pytest.raises(MalformedResponseError, match="AssumptionChallenge"):
        _adapter(response).challenge_assumptions(ProposedArchitecture(summary="x"), ())


# -- Citation enforcement, applied unchanged from Phase 2 -----------------------------------------


def test_fabricated_evidence_id_is_rejected_when_wrapped_by_validating_engine() -> None:
    response = json.dumps({"rationale": "x", "cited_evidence_ids": ["E-999"]})
    wrapper = ValidatingIntelligenceEngine(_adapter(response))
    with pytest.raises(CitationError, match="evidence"):
        wrapper.evaluate_tradeoff(
            (EvidenceItem(reference_id="E-1", summary="x"),),
            (Candidate(candidate_id="C-1", description="x"),),
        )


def test_fabricated_candidate_id_is_rejected_when_wrapped_by_validating_engine() -> None:
    response = json.dumps({"rationale": "x", "ranked_candidate_ids": ["C-999"]})
    wrapper = ValidatingIntelligenceEngine(_adapter(response))
    with pytest.raises(CitationError, match="candidate"):
        wrapper.evaluate_tradeoff(
            (EvidenceItem(reference_id="E-1", summary="x"),),
            (Candidate(candidate_id="C-1", description="x"),),
        )


def test_a_conforming_response_passes_through_the_validating_wrapper_unchanged() -> None:
    response = json.dumps({"rationale": "x", "cited_evidence_ids": ["E-1"], "ranked_candidate_ids": ["C-1"]})
    wrapper = ValidatingIntelligenceEngine(_adapter(response))
    result = wrapper.evaluate_tradeoff(
        (EvidenceItem(reference_id="E-1", summary="x"),), (Candidate(candidate_id="C-1", description="x"),)
    )
    assert result.ranked_candidate_ids == ("C-1",)
    assert result.cited_evidence_ids == ("E-1",)


# -- Dependency verification ------------------------------------------------------------------


def _direct_imports(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


_FORBIDDEN_SDKS = {"anthropic", "openai", "google", "cohere"}


def test_no_intelligence_file_outside_adapters_imports_a_vendor_sdk() -> None:
    non_adapter_files = [
        py_file
        for py_file in INTELLIGENCE_DIR.rglob("*.py")
        if "__pycache__" not in py_file.parts
        and "adapters" not in py_file.relative_to(INTELLIGENCE_DIR).parts
    ]
    violations = {
        str(py_file.relative_to(INTELLIGENCE_DIR)): sorted(_direct_imports(py_file) & _FORBIDDEN_SDKS)
        for py_file in non_adapter_files
        if _direct_imports(py_file) & _FORBIDDEN_SDKS
    }
    assert violations == {}


def test_anthropic_adapter_module_itself_imports_no_vendor_sdk_either() -> None:
    # Disclosed design choice (see anthropic_adapter.py's own module
    # docstring): AnthropicClientProtocol is this project's own structural
    # seam, never the real SDK's client type, so nothing here needs to
    # import the SDK to type-check -- this test proves that choice holds,
    # not merely documents it.
    imports = _direct_imports(INTELLIGENCE_DIR / "adapters" / "anthropic_adapter.py")
    assert imports & _FORBIDDEN_SDKS == set()


def test_adapters_init_imports_no_vendor_sdk() -> None:
    imports = _direct_imports(INTELLIGENCE_DIR / "adapters" / "__init__.py")
    assert imports & _FORBIDDEN_SDKS == set()


def test_anthropic_adapter_module_imports_only_stdlib_pydantic_and_intelligence_contracts() -> None:
    imports = _direct_imports(INTELLIGENCE_DIR / "adapters" / "anthropic_adapter.py")
    assert imports <= {"__future__", "json", "typing", "pydantic", "intelligence"}
