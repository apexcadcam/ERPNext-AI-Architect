"""`RollbackStrategy` — Sprint 5 Architecture Package §9.5, §19.

An **interface** only, this Sprint — no connector shipped so far declares
a compensating action, so the one reference implementation,
`UnsupportedRollbackStrategy`, always reports `supported=False`. A rollback
pass always completes and always honestly reports nothing was undone,
never silently pretends success. Extending the Connector Contract with a
real compensating-action mechanism is a Future ADR candidate (§26), not
decided or implemented here.

`rollback()`'s signature references `ExecutionContext` (`execution.
context`, this same phase) — imported only under `TYPE_CHECKING` here,
since `execution.context.ExecutionContext` itself holds a
`RollbackStrategy` as one of its own fields and needs a real, runtime
import of this module. Breaking the cycle this way (a standard, idiomatic
pattern) avoids deviating from §9.5's own approved signature shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from execution.contract import RollbackOutcome, StepExecutionRecord

if TYPE_CHECKING:
    from execution.context import ExecutionContext


class RollbackStrategy(ABC):
    """Consulted by the optional post-`FAILED` rollback pass (a later
    phase). Exposes exactly one method.
    """

    @abstractmethod
    def rollback(self, record: StepExecutionRecord, context: ExecutionContext) -> RollbackOutcome:
        """Attempts to undo one already-executed step. Always returns a
        `RollbackOutcome` — never raises for "not supported," which is a
        normal, expected answer, not a failure.
        """


class UnsupportedRollbackStrategy(RollbackStrategy):
    """The reference implementation: every rollback attempt, for every
    connector shipped as of this Sprint, honestly reports it cannot be
    done.
    """

    def rollback(self, record: StepExecutionRecord, context: ExecutionContext) -> RollbackOutcome:
        return RollbackOutcome(supported=False, detail="no compensating action declared")
