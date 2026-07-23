"""Extraction and Pattern Extraction: KNOWLEDGE_EXTRACTION_SPEC.md."""

from __future__ import annotations

from knowledge.extraction.ids import IdAllocator
from knowledge.extraction.module import ExtractorModule
from knowledge.extraction.pattern_extraction import (
    ANTI_PATTERN_CANDIDATE_TAG_PREFIX,
    PATTERN_CANDIDATE_TAG_PREFIX,
    extract_patterns,
)
from knowledge.extraction.stage import extract

__all__ = [
    "ANTI_PATTERN_CANDIDATE_TAG_PREFIX",
    "PATTERN_CANDIDATE_TAG_PREFIX",
    "ExtractorModule",
    "IdAllocator",
    "extract",
    "extract_patterns",
]
