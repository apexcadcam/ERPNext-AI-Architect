<!-- Copy to rules/metadata/R0NN.rm.yaml (matching the rule's own number). Fill in every field per docs/ai-retrieval/METADATA_SCHEMA.yaml, then delete this comment block and the guidance comments inline below. Full field-by-field rationale: docs/ai-retrieval/RULE_METADATA_SPECIFICATION.md. Never copy the rule's own prose into any field here — point at it or restructure it, per that spec's §2. -->

```yaml
schema_version: "1.0.0"
rule_metadata_id: "RM-0NN"        # matches rule_id numerically
rule_id: "R0NN"
rule_er_id: "ER-0NN"
title: ""                          # exact mirror of the rule's H1 title
source_file: "rules/R0NN-slug.md"
version: "1.0.0"
status: Draft                      # mirror rules/R0NN-*.md "## Status" exactly
sync_state: generated              # generated | validated | synced | stale
risk_level: Medium                 # mirror rules/R0NN-*.md "## Risk Level" exactly
priority: P2                       # Critical->P0, High->P1, Medium->P2, Low->P3

category: Architecture             # exactly one, from METADATA_SCHEMA.yaml's fixed enum
tags: []                           # kebab-case facets, at least one
keywords: []                       # free-text lexical search terms, incl. synonyms not in the rule's own wording

intent: ""                         # one sentence: the good outcome this rule protects
problem_statement: ""              # one sentence: the situation an agent is in when this rule applies

requirements:                      # decompose "## Rule" into discrete RFC 2119 clauses — do not invent beyond the prose
  - id: "R0NN-REQ-1"
    modal: MUST                    # MUST | MUST_NOT | SHOULD | SHOULD_NOT | MAY
    statement: ""
    source_anchor: "#rule"

good_examples:                     # pointers into "## Good Pattern" — never copy the code block itself
  - source_anchor: "#good-pattern"
    description: ""

bad_examples:                      # pointers into "## Bad Pattern"
  - source_anchor: "#bad-pattern"
    description: ""

anti_patterns: []                  # AP-#### once anti-patterns/ is populated, else mirror "## Related Anti-Patterns"
exceptions_present: false          # true only if "## Exceptions" states more than "None"
related_rules: []                  # mirror "## Related Rules", undirected

dependencies: []                   # directed: rules that MUST be understood alongside this one, with why
  # - rule_id: "R0NN"
  #   reason: ""

conflicts: []                      # documented cases where two Good Patterns can't both hold; empty is a real, valid state
  # - rule_id: "R0NN"
  #   scenario: ""
  #   resolution: "Undecided — surface to a human per AGENTS.md, do not resolve silently"

replacement:
  supersedes: []
  superseded_by: null

references: []                     # only real external URLs; leave empty rather than invent one
  # - title: ""
  #   url: ""

ai_retrieval:
  semantic_summary: ""             # 1-2 sentences, different wording from the rule's own Rationale
  embedding_text: ""               # deterministic concat per RULE_INDEX_SPEC.md's template; regenerate on any input change
  trigger_intents: []              # canonical task phrasings that should route here
  applicability_signals: []        # cheap, deterministic pattern-match hints (file paths, DocType ops, API calls)
  negative_signals: []             # look-alike patterns that should NOT trigger this rule
  confidence_weight: 1.0           # 0.0-1.0 ranking multiplier; 1.0 unless a curator has a reason to adjust

workflow_ref: null                 # DT-#### or SK-#### once one exists; null is correct today (ROADMAP Stage 2+ not started)

revision_history:
  - version: "1.0.0"
    date: "YYYY-MM-DD"
    change: "Initial AI retrieval metadata generated."
    reason: "First RM record authored for this rule."
```
