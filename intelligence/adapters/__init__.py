"""Intelligence Abstraction Layer adapters — Sprint 8, Phase 4.

Per the approved Sprint 8 Implementation Plan §2/§6: this is the only
subpackage inside `intelligence/` permitted to import a vendor AI SDK.
`anthropic_adapter.py` is the one adapter Phase 4 ships — existence proof
that `IntelligenceEngine` can be satisfied by a real provider, not a
general adapter framework. No other adapter (OpenAI, Gemini, a local
model) is implemented in this phase.
"""

from __future__ import annotations
