"""The Composition Root — Sprint 13, Phase 2.

Wires the already-frozen `analysis` -> `knowledge` -> `intelligence` ->
`planning` -> `execution` -> `orchestration` -> `runtime` chain into one
live, end-to-end call. See `root.py`'s own module docstring for the full,
disclosed design reasoning.
"""

from __future__ import annotations

from composition_root.root import run_goal_end_to_end

__all__ = ["run_goal_end_to_end"]
