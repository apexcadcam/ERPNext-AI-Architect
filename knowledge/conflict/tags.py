"""Tag facets conflict-resolution-relevant code depends on.

Not part of the frozen artifact envelope (KNOWLEDGE_ARTIFACTS.md §1 defines
no per-claim authorship/contradiction fields) — `tags` is the sanctioned
seam, per the convention KNOWLEDGE_EXTRACTION_SPEC.md itself already uses
for `verified-fixed`, `interim-workaround`, `third-party-observed`, etc.
Shared between knowledge/validation/gates.py (which sets/reads them) and
knowledge/conflict/providers.py (which reads them to build a `ConflictClaim`)
so both stay in agreement on the literal strings without either importing
the other.
"""

from __future__ import annotations

#: KNOWLEDGE_CONFLICT_RESOLUTION.md §4: is this claim a staff-authored
#: forum/community reply?
TAG_STAFF_AUTHORED = "staff-authored"
#: §4: was this claim authored after the competing documentation's last
#: confirmed update?
TAG_AFTER_DOCS_UPDATE = "authored-after-docs-update"
#: §6 / KNOWLEDGE_VALIDATION_SPEC.md §6: does this claim's rationale
#: contradict a `Stable` Engineering Rule?
TAG_CONTRADICTS_STABLE_RULE = "contradicts-stable-rule"
