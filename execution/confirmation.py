"""`ConfirmationProvider` — Sprint 5 Architecture Package §9.4.

One fixed contract, mirroring `planning.strategy.PlannerStrategy`'s exact
"ABC, one abstract method, no additional public surface" shape. The one
reference implementation this Sprint ships, `DenyAllConfirmationProvider`,
always denies — the safest possible default, mirroring
`SPRINT3_ARCHITECTURE_PACKAGE.md §14` item 3's "the safe behavior is the
one requiring no extra decision." A human-facing approval UX remains
named, not built (§3, §26).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from planning.contract import PlanStep

from execution.contract import ExecutionRun


class ConfirmationProvider(ABC):
    """Consulted by the Confirmation Gate (a later phase) for every step
    whose `requires_confirmation` is `True`. Exposes exactly one method —
    no configuration logic, no Runtime wiring.
    """

    @abstractmethod
    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        """Returns `True` to grant the step's confirmation, `False` to deny
        it. A denial is never an error — the caller (a later phase's
        Confirmation Gate) records it as a `SKIPPED` step, never raises.
        """


class DenyAllConfirmationProvider(ConfirmationProvider):
    """The reference implementation: always denies. Safe by construction —
    a run using this provider can never execute a `requires_confirmation`
    step, regardless of what that step is.
    """

    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        return False
