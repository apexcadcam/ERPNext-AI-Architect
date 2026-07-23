"""Conflict resolution: the fixed precedence hierarchy plus the five named
scenarios and the non-negotiable "undecided" fallback.

Implements docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md in full.
A plain, stateless library — not a `runtime.modules.base.Module` — invoked
directly by the Validator's Version Conflict Detection gate
(knowledge/validation/gates.py) and by the graph_build Pipeline Definition's
Conflict Resolution stage, per SPRINT2_IMPLEMENTATION_PLAN.md §6: it has no
lifecycle of its own and is shared logic within the Knowledge Factory
grouping, not a separate domain module.
"""

from __future__ import annotations

import enum
import re

from pydantic import BaseModel, ConfigDict


class PrecedenceTier(enum.IntEnum):
    """The 9-level precedence hierarchy, KNOWLEDGE_CONFLICT_RESOLUTION.md §1.

    Lower value outranks higher value — never by confidence score alone,
    because confidence measures how sure extraction is, not how
    authoritative the source is.
    """

    OFFICIAL_SOURCE_CODE = 1
    MERGED_PULL_REQUEST = 2
    OFFICIAL_DOCUMENTATION = 3
    OFFICIAL_RELEASE_NOTES = 4
    STAFF_FORUM_REPLY = 5
    COMMUNITY_FORUM_CONSENSUS = 6
    VETTED_MARKETPLACE = 7
    TUTORIALS_BLOGS_TALKS = 8
    UNVETTED_COMMUNITY = 9


class ConflictClaim(BaseModel):
    """One side of a two-claim conflict case.

    The boolean flags carry exactly the facts KNOWLEDGE_CONFLICT_RESOLUTION.md
    §§2-6's named scenarios distinguish on — they are not general-purpose
    metadata, only what resolution actually needs to tell the scenarios apart.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str
    precedence_tier: PrecedenceTier
    version_applies_to: str | None = None
    #: Confidence band for `version_applies_to`, per KNOWLEDGE_PIPELINE.md §4.
    version_confidence: str = "explicit"
    #: §4: is this claim a staff-authored forum/community reply?
    staff_authored: bool = False
    #: §4: was this claim authored after the competing documentation's last
    #: confirmed update?
    authored_after_docs_last_update: bool = False
    #: §6: does this claim's rationale contradict a `Stable` Engineering Rule?
    contradicts_stable_rule: bool = False


class ConflictCase(BaseModel):
    """Two claims genuinely in tension, submitted for resolution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_a: ConflictClaim
    claim_b: ConflictClaim


class ConflictOutcomeKind(str, enum.Enum):
    """Which of KNOWLEDGE_CONFLICT_RESOLUTION.md's rules decided the case."""

    #: §1's general precedence hierarchy decided it.
    WINNER_BY_PRECEDENCE = "winner_by_precedence"
    #: §2 / §6: not really a conflict — a version-scoped or version-transition
    #: fact; both claims retained, newer supersedes older for current queries.
    BOTH_VALID_VERSION_SCOPED = "both_valid_version_scoped"
    #: §4: staff forum reply postdates the docs — flagged, not resolved.
    FLAGGED_DOCS_MAY_BE_STALE = "flagged_docs_may_be_stale"
    #: §6: a claim's rationale contradicts a Stable rule — never automatic.
    ESCALATED_RULE_CONTRADICTION = "escalated_rule_contradiction"
    #: Same tier, genuinely disagreeing, no version difference — never guessed.
    UNDECIDED = "undecided"


class ConflictResolution(BaseModel):
    """The result of resolving one `ConflictCase`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: ConflictOutcomeKind
    winning_claim_id: str | None = None
    losing_claim_id: str | None = None
    reason: str
    requires_human_review: bool


def resolve_conflict(case: ConflictCase) -> ConflictResolution:
    """Resolve one conflict case deterministically wherever the frozen
    precedence rules allow it, and escalate — never guess — otherwise.

    Checked in this fixed order, each narrower than the next:
      1. §6 rule-contradiction escalation (bypasses precedence entirely)
      2. §2/§6 differing-but-confident version scope (not a real conflict)
      3. §4 staff-forum-postdates-docs (a precedence override, not a result)
      4. §1's general precedence hierarchy
      5. same-tier, unresolvable → undecided
    """

    a, b = case.claim_a, case.claim_b

    contradicting = _rule_contradiction(a, b)
    if contradicting is not None:
        return ConflictResolution(
            outcome=ConflictOutcomeKind.ESCALATED_RULE_CONTRADICTION,
            reason=(
                f"claim '{contradicting.artifact_id}' contradicts a Stable Engineering Rule — "
                "escalated to human review per KNOWLEDGE_CONFLICT_RESOLUTION.md § 6, "
                "never resolved automatically"
            ),
            requires_human_review=True,
        )

    version_scoped = _version_scoped_pair(a, b)
    if version_scoped is not None:
        newer, older = version_scoped
        return ConflictResolution(
            outcome=ConflictOutcomeKind.BOTH_VALID_VERSION_SCOPED,
            winning_claim_id=newer.artifact_id,
            losing_claim_id=older.artifact_id,
            reason=(
                "both claims are version-scoped facts, both true within their own scope — "
                f"'{newer.artifact_id}' supersedes '{older.artifact_id}' for current-version queries "
                "only, per KNOWLEDGE_CONFLICT_RESOLUTION.md § 2; neither is deleted or demoted"
            ),
            requires_human_review=False,
        )

    docs_vs_staff_forum = _docs_vs_staff_forum(a, b)
    if docs_vs_staff_forum is not None:
        docs_claim, forum_claim = docs_vs_staff_forum
        return ConflictResolution(
            outcome=ConflictOutcomeKind.FLAGGED_DOCS_MAY_BE_STALE,
            reason=(
                f"'{forum_claim.artifact_id}' is a staff-authored forum reply dated after "
                f"'{docs_claim.artifact_id}''s last documentation update — flagged docs-may-be-stale "
                "per KNOWLEDGE_CONFLICT_RESOLUTION.md § 4; both claims retained and surfaced "
                "together, routed to human review rather than resolved either way"
            ),
            requires_human_review=True,
        )

    if a.precedence_tier != b.precedence_tier:
        winner, loser = (a, b) if a.precedence_tier < b.precedence_tier else (b, a)
        return ConflictResolution(
            outcome=ConflictOutcomeKind.WINNER_BY_PRECEDENCE,
            winning_claim_id=winner.artifact_id,
            losing_claim_id=loser.artifact_id,
            reason=(
                f"'{winner.artifact_id}' (tier {winner.precedence_tier.name}) outranks "
                f"'{loser.artifact_id}' (tier {loser.precedence_tier.name}) per the fixed "
                "precedence hierarchy in KNOWLEDGE_CONFLICT_RESOLUTION.md § 1"
            ),
            requires_human_review=False,
        )

    return ConflictResolution(
        outcome=ConflictOutcomeKind.UNDECIDED,
        reason="Undecided — surface to a human per AGENTS.md, do not resolve silently.",
        requires_human_review=True,
    )


def _rule_contradiction(a: ConflictClaim, b: ConflictClaim) -> ConflictClaim | None:
    if a.contradicts_stable_rule:
        return a
    if b.contradicts_stable_rule:
        return b
    return None


def _version_scoped_pair(a: ConflictClaim, b: ConflictClaim) -> tuple[ConflictClaim, ConflictClaim] | None:
    """§2/§6: differing, confidently-scoped versions are not a real conflict.

    Returns (newer, older) if this scenario applies, else None.
    """

    if a.version_applies_to is None or b.version_applies_to is None:
        return None
    if a.version_applies_to == b.version_applies_to:
        return None
    if a.version_confidence == "inferred" or b.version_confidence == "inferred":
        return None  # ambiguous scoping — treated as same-version-until-proven-otherwise

    return (a, b) if _version_is_newer(a.version_applies_to, b.version_applies_to) else (b, a)


def _docs_vs_staff_forum(a: ConflictClaim, b: ConflictClaim) -> tuple[ConflictClaim, ConflictClaim] | None:
    """§4: official docs vs. a staff-authored forum reply postdating them.

    Returns (docs_claim, forum_claim) if this scenario applies, else None.
    """

    for docs_claim, other_claim in ((a, b), (b, a)):
        if (
            docs_claim.precedence_tier is PrecedenceTier.OFFICIAL_DOCUMENTATION
            and other_claim.staff_authored
            and other_claim.authored_after_docs_last_update
        ):
            return docs_claim, other_claim
    return None


def _version_is_newer(version_a: str, version_b: str) -> bool:
    """Best-effort comparison of ERPNext/Frappe version strings (e.g. "v15",
    "15", "v14.1"). Falls back to lexicographic order if no leading number
    can be parsed from either side — good enough for the fixture-scale
    inputs Sprint 2 operates on; a real semver comparator is not required
    while there is no live source feeding this function real version
    strings.
    """

    number_a = _leading_number(version_a)
    number_b = _leading_number(version_b)
    if number_a is not None and number_b is not None and number_a != number_b:
        return number_a > number_b
    return version_a > version_b


def _leading_number(version: str) -> float | None:
    match = re.search(r"\d+(\.\d+)?", version)
    return float(match.group()) if match else None
