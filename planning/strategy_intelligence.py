"""`IntelligenceAwarePlannerStrategy` — Sprint 12, Phase 1.

The second `PlannerStrategy` implementation (`planning.strategy`, Sprint 4,
unmodified) — a structural translator from an already-produced
`intelligence.contract.TradeoffAssessment` into a `Plan`. It performs no
reasoning, no ranking, no rescoring, and no reinterpretation of evidence:
every judgment this strategy acts on already happened upstream, in
Intelligence, before this class ever sees it. It never calls
`IntelligenceEngine`, never imports `intelligence.pipeline` or
`intelligence.bridge`, and never imports `knowledge.*`/`analysis.*` —
its one and only import outside `planning/` itself is
`intelligence.contract`.

**Constructor injection, not `PlanningContext` extension:** per this
Sprint's own ADR-003 decision, Intelligence's output reaches Planning
through this strategy's constructor — `PlanningContext`, `Plan`,
`PlanStep`, and `Goal` (all frozen since Sprint 4) are completely
unmodified. `create_plan(goal, context) -> Plan` keeps the exact
`PlannerStrategy` signature every other strategy already implements.

**Why `created_at` is a required constructor parameter, not a fixed
placeholder constant like `RuleBasedPlannerStrategy._CREATED_AT_PLACEHOLDER`:**
that placeholder exists specifically because `create_plan`'s own signature
was already fixed and approved with no room for an extra parameter by the
time `RuleBasedPlannerStrategy` was written. This class's constructor is
being designed fresh, with room to spare, so requiring the real value from
the caller — the same "caller-supplied, never fabricated" discipline
`knowledge.builder.build_knowledge_snapshot`'s own `created_at` parameter
already established — is the more honest option available here, not a
deviation from precedent but the same precedent applied where signature
freedom actually exists.

**`ranked_candidate_ids` -> `PlanStep.capability`, verbatim, disclosed
assumption:** `TradeoffAssessment.ranked_candidate_ids` holds
`Candidate.candidate_id` values (Bridge's own translation, Sprint 11
Phase 1) — this strategy treats each one as *being* the capability name a
`PlanStep` should reference, the same zero-translation assumption
`RuleBasedPlannerStrategy` already makes about `Goal.desired_capabilities`
entries. Nothing here invents a mapping from an artifact id to a
capability name that does not already exist; whoever assembles the
`Candidate`s that feed a `TradeoffAssessment` intended for this strategy
is responsible for using capability names as their `candidate_id`s. If a
ranked id has no matching `CapabilityDescriptor` in
`PlanningContext.available_capabilities`, it is silently skipped — the
same "skip, do not fabricate a descriptor" behavior
`RuleBasedPlannerStrategy._step_for` already established for an unmatched
desired capability.

**`Goal.desired_capabilities` is deliberately never read.** Ranking
already happened upstream, using whatever `Candidate`s Intelligence was
given — re-consulting `Goal.desired_capabilities` here would be a second,
competing source of truth for "what should be planned," which this
strategy does not do. `goal` is consulted only for `goal_id` (`Plan`'s own
required field). This is the one deliberate behavioral difference from
`RuleBasedPlannerStrategy`, disclosed rather than left implicit.

**Ranking becomes step order, never a fabricated dependency graph.**
`TradeoffAssessment` asserts an ordering, not a dependency requirement — a
lower-ranked step is not necessarily blocked on a higher-ranked one having
run first. Inventing `depends_on` edges to encode ranking would assert
something Intelligence never stated. Every produced `PlanStep.depends_on`
is therefore always empty; ranking is expressed only through each step's
position in `Plan.steps`' own tuple order.

**`rationale` propagation.** Each step's own `rationale` embeds
`TradeoffAssessment.rationale` verbatim alongside its own `candidate_id` —
a plain, disclosed provenance string, mirroring
`RuleBasedPlannerStrategy._step_for`'s identical "state which upstream
fact justified this step" discipline; never a new judgment authored by
this class.

**Deterministic by construction.** No randomness, no clock access beyond
the caller-supplied `created_at`, no I/O, no graph access (`context.graph`
is never touched, exactly like `RuleBasedPlannerStrategy`). The same
`(goal, context)` pair, against the same constructed instance (i.e. the
same `TradeoffAssessment`/`created_at`), always produces an
identical `Plan`.
"""

from __future__ import annotations

from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep
from planning.context import PlanningContext
from planning.strategy import PlannerStrategy

from intelligence.contract import TradeoffAssessment


class IntelligenceAwarePlannerStrategy(PlannerStrategy):
    """Translates one, already-computed `TradeoffAssessment` into a `Plan`
    — structural translation only. See this module's own docstring for
    the full, disclosed mapping rules.
    """

    _STRATEGY_NAME = "intelligence_aware"

    def __init__(self, tradeoff_assessment: TradeoffAssessment, *, created_at: str) -> None:
        if not created_at:
            raise ValueError("created_at must be a non-empty string")
        self._tradeoff_assessment = tradeoff_assessment
        self._created_at = created_at

    def create_plan(self, goal: Goal, context: PlanningContext) -> Plan:
        capabilities_by_name = {
            descriptor.capability: descriptor for descriptor in context.available_capabilities
        }

        steps: list[PlanStep] = []
        already_planned: set[str] = set()
        for index, candidate_id in enumerate(self._tradeoff_assessment.ranked_candidate_ids, start=1):
            if candidate_id in already_planned:
                continue
            descriptor = capabilities_by_name.get(candidate_id)
            if descriptor is None:
                continue
            already_planned.add(candidate_id)
            steps.append(self._step_for(descriptor, index=index))

        return Plan(
            plan_id=f"plan-for-{goal.goal_id}",
            goal_id=goal.goal_id,
            steps=tuple(steps),
            created_at=self._created_at,
            strategy_name=self._STRATEGY_NAME,
        )

    def _step_for(self, descriptor: CapabilityDescriptor, *, index: int) -> PlanStep:
        return PlanStep(
            step_id=f"step-{index}",
            capability=descriptor.capability,
            requires_confirmation=descriptor.requires_confirmation,
            rationale=(
                f"ranked by Intelligence for candidate '{descriptor.capability}': "
                f"{self._tradeoff_assessment.rationale}"
            ),
        )
