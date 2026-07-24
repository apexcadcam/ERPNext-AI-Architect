"""`ConfirmationGate` — Sprint 5 Architecture Package §8, step 3c; §14.

Distinct from `execution.confirmation.ConfirmationProvider` (the swappable
backend, Phase 3): this is the orchestration-adjacent component that
*consults* a `ConfirmationProvider` at the right moment, matching the
Component Diagram's own separate `ConfirmationGate` box (§7). Not yet
wired into a full orchestration loop — that is `ExecutionEngine`'s job
(Phase 5).
"""

from __future__ import annotations

from planning.contract import PlanStep

from execution.confirmation import ConfirmationProvider
from execution.contract import ExecutionRun


class ConfirmationGate:
    """Wraps one `ConfirmationProvider`. Never consults it at all for a
    step whose `requires_confirmation` is `False` — not merely "returns
    fast," genuinely never calls it.
    """

    def __init__(self, provider: ConfirmationProvider) -> None:
        self._provider = provider

    def evaluate(self, step: PlanStep, run: ExecutionRun) -> bool | None:
        """Returns `None` if `step.requires_confirmation` is `False` (the
        `ConfirmationProvider` is never consulted); otherwise returns
        exactly what `ConfirmationProvider.confirm()` returned — `True` to
        proceed, `False` to skip. Mirrors `StepExecutionRecord.
        confirmation_granted`'s own three-way shape exactly, so a caller
        can populate that field directly from this method's return value.
        """

        if not step.requires_confirmation:
            return None
        return self._provider.confirm(step, run)
