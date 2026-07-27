"""The deterministic Knowledge Query service — Sprint 10, Phase 4.

A read-only, in-memory API over one `knowledge.domain.KnowledgeSnapshot`
— no graph traversal, no indexing, no caching, no persistence, no
reasoning. See `service.py`'s own module docstring for the full API
derivation against `KnowledgeCollection`'s existing fields.
"""

from __future__ import annotations

from knowledge.query.service import KnowledgeQueryService

__all__ = ["KnowledgeQueryService"]
