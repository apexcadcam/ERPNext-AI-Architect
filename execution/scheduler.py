"""`StepScheduler` — Sprint 5 Architecture Package §7, §24's Scheduling
Tie-Breaking subsection.

Produces one, precisely specified, stable topological order over a
`Plan`'s steps: at each point, from the set of steps whose `depends_on`
have all already been placed in the order (their "ready set"), the one
chosen is whichever appears **earliest in `plan.steps`' own original
tuple order** — never a `set`'s iteration order (not guaranteed stable
across process runs for string keys, under Python's default hash
randomization) and never any other implementation-chosen structure.

This produces one fixed *attempt order*, computed once, up front, assuming
every step eventually succeeds. It is deliberately **not** the same as
runtime dependency satisfaction: a later phase's `ExecutionEngine` walks
this order and independently checks, at each step's own turn, whether that
step's dependencies actually succeeded by then (§8 step 3a) — skipping it
if not. `StepScheduler` only orders; it never decides pass/skip.

Assumes `plan` has already passed Sprint 4's `validate_plan` — no
`depends_on` cycle and no reference to an unknown `step_id` — since only a
validated `Plan` can ever reach Execution. This module performs no
re-validation of either fact (`execution/` must not contain planning
logic).
"""

from __future__ import annotations

import heapq

from planning.contract import Plan, PlanStep


class StepScheduler:
    """Stateless — one method, no configuration, no Runtime wiring."""

    def order(self, plan: Plan) -> tuple[PlanStep, ...]:
        steps_by_id = {step.step_id: step for step in plan.steps}
        original_index = {step.step_id: index for index, step in enumerate(plan.steps)}
        in_degree = {step.step_id: len(step.depends_on) for step in plan.steps}
        dependents: dict[str, list[str]] = {step.step_id: [] for step in plan.steps}
        for step in plan.steps:
            for dependency_id in step.depends_on:
                if dependency_id in dependents:
                    dependents[dependency_id].append(step.step_id)

        ready: list[tuple[int, str]] = [
            (original_index[step_id], step_id) for step_id, degree in in_degree.items() if degree == 0
        ]
        heapq.heapify(ready)

        ordered_ids: list[str] = []
        while ready:
            _, next_id = heapq.heappop(ready)
            ordered_ids.append(next_id)
            for dependent_id in dependents[next_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    heapq.heappush(ready, (original_index[dependent_id], dependent_id))

        return tuple(steps_by_id[step_id] for step_id in ordered_ids)
