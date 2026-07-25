"""`AnthropicAdapter` — Sprint 8, Phase 4.

Implements the approved Sprint 8 Implementation Plan §4 Phase 4: the one,
minimal adapter proving `IntelligenceEngine` can be satisfied by a real
provider, not just `NullIntelligenceEngine`. Translation only — no
ranking, no citation validation (that remains `ValidatingIntelligenceEngine`'s
job, Phase 2, applied identically regardless of which `IntelligenceEngine`
implementation it wraps), no retry, no caching.

Per the plan's own "never instantiate SDK clients internally" / "every
collaborator arrives through the constructor" rule, this module defines
`AnthropicClientProtocol` — this project's own narrow, structural seam,
not the Anthropic SDK's own client type — and imports no vendor SDK at
all: nothing in this file constructs a client, so nothing here needs the
concrete SDK class to type-check against. This mirrors
`planning.graph_reader.GraphReader`'s and
`execution.connector_invoker.ConnectorInvoker`'s own established "a
structural Protocol, no vendor import required to define it" pattern —
the same discipline applied one layer further out, to an external vendor
boundary instead of an internal one. A future real, `anthropic`-backed
implementation of `AnthropicClientProtocol` may be added later; per the
plan's dependency rule, this package (`intelligence/adapters/`) is the
only place such an import could ever legally live — but writing that
concrete, network-calling implementation is explicitly out of this
phase's scope ("no runtime configuration changes," "zero network
access"), so none exists yet.
"""

from __future__ import annotations

import json
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

from intelligence.contract import (
    ArchitectureCritique,
    AssumptionChallenge,
    Candidate,
    EvidenceItem,
    IntelligenceEngine,
    ProposedArchitecture,
    Requirement,
    RequirementUnderstanding,
    TradeoffAssessment,
)
from intelligence.errors import IntelligenceError_

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class MalformedResponseError(IntelligenceError_):
    """The client's raw response was not valid JSON, or did not match the
    shape the calling method's own contract type requires. Raised
    immediately — never repaired, never returned as a partial result.
    """


@runtime_checkable
class AnthropicClientProtocol(Protocol):
    """The one seam `AnthropicAdapter` depends on — this project's own
    minimal shape, not the Anthropic SDK's own client type. A fake
    satisfying just this one method is enough for every test in this
    package; a real implementation wraps however the actual SDK's calling
    convention shapes up, with no change to `AnthropicAdapter` itself.
    """

    def create_message(self, *, system: str, user: str) -> str:
        """Sends `system` (instructions) and `user` (this adapter's own
        JSON serialization of its typed input) to the model. Returns the
        model's raw text response, unparsed.
        """
        ...


_INTERPRET_REQUIREMENT_SYSTEM_PROMPT = (
    "Restate the given software requirement. Respond with ONLY a JSON "
    'object: {"requirement_id": string (echo the input unchanged), '
    '"key_concepts": array of strings, "ambiguities": array of strings, '
    '"restated_requirement": string}. No other text.'
)

_EVALUATE_TRADEOFF_SYSTEM_PROMPT = (
    "You are given evidence items and candidates. Rank the candidates "
    "using only the supplied evidence. Respond with ONLY a JSON object: "
    '{"ranked_candidate_ids": array of candidate_id strings from the '
    'input, best first, "rationale": string, "cited_evidence_ids": array '
    "of reference_id strings from the input, only ones actually used}. "
    "Never include a candidate_id or reference_id not present in the "
    "input. No other text."
)

_CRITIQUE_ARCHITECTURE_SYSTEM_PROMPT = (
    "You are given a proposed architecture and supporting evidence. "
    "Identify concerns, grounded only in the supplied evidence. Respond "
    'with ONLY a JSON object: {"concerns": array of strings, '
    '"cited_evidence_ids": array of reference_id strings from the input, '
    "only ones actually used}. Never include a reference_id not present "
    "in the input. An empty concerns array is a valid answer. No other "
    "text."
)

_CHALLENGE_ASSUMPTIONS_SYSTEM_PROMPT = (
    "You are given a proposed architecture and supporting evidence. "
    "Question the assumptions it rests on, grounded only in the supplied "
    'evidence. Respond with ONLY a JSON object: {"challenged_assumptions": '
    'array of objects each with "assumption" (string), "challenge" '
    '(string), "resolution" (one of "assumption_holds", '
    '"assumption_rejected", "unresolved"), "resolution_rationale" '
    '(string)}, "cited_evidence_ids": array of reference_id strings from '
    "the input, only ones actually used}. An empty "
    "challenged_assumptions array is a valid answer. Never include a "
    "reference_id not present in the input. No other text."
)


class AnthropicAdapter(IntelligenceEngine):
    """Translates `IntelligenceEngine`'s typed contracts into requests for
    an injected `AnthropicClientProtocol`, and its raw text responses back
    into typed contracts. Nothing else — no ranking, no citation
    enforcement, no retry, no caching; each belongs to a different,
    already-existing layer this class neither re-implements nor bypasses.
    """

    def __init__(self, client: AnthropicClientProtocol) -> None:
        self._client = client

    def interpret_requirement(self, requirement: Requirement) -> RequirementUnderstanding:
        raw = self._client.create_message(
            system=_INTERPRET_REQUIREMENT_SYSTEM_PROMPT, user=requirement.model_dump_json()
        )
        return self._parse(raw, RequirementUnderstanding)

    def evaluate_tradeoff(
        self, evidence: tuple[EvidenceItem, ...], candidates: tuple[Candidate, ...]
    ) -> TradeoffAssessment:
        payload = json.dumps(
            {
                "evidence": [item.model_dump() for item in evidence],
                "candidates": [candidate.model_dump() for candidate in candidates],
            }
        )
        raw = self._client.create_message(system=_EVALUATE_TRADEOFF_SYSTEM_PROMPT, user=payload)
        return self._parse(raw, TradeoffAssessment)

    def critique_architecture(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> ArchitectureCritique:
        payload = json.dumps(
            {"proposed": proposed.model_dump(), "evidence": [item.model_dump() for item in evidence]}
        )
        raw = self._client.create_message(system=_CRITIQUE_ARCHITECTURE_SYSTEM_PROMPT, user=payload)
        return self._parse(raw, ArchitectureCritique)

    def challenge_assumptions(
        self, proposed: ProposedArchitecture, evidence: tuple[EvidenceItem, ...]
    ) -> AssumptionChallenge:
        payload = json.dumps(
            {"proposed": proposed.model_dump(), "evidence": [item.model_dump() for item in evidence]}
        )
        raw = self._client.create_message(system=_CHALLENGE_ASSUMPTIONS_SYSTEM_PROMPT, user=payload)
        return self._parse(raw, AssumptionChallenge)

    @staticmethod
    def _parse(raw: str, model: type[_ModelT]) -> _ModelT:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MalformedResponseError(f"response was not valid JSON: {exc}") from exc
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise MalformedResponseError(
                f"response did not match the expected {model.__name__} shape: {exc}"
            ) from exc
