from __future__ import annotations

from aggregation.contract import (
    AggregationRequest,
    AggregationStatistics,
    AggregationStatus,
    CorpusRef,
    ObservedBelowThreshold,
    Pattern,
    PatternSet,
    PopulationBasis,
    ResolutionProvenance,
    ResolutionStrategy,
    SkippedAggregation,
    ThresholdSpec,
)
from aggregation.engine import aggregate_patterns
from aggregation.errors import AggregationError_
from aggregation.persistence import read_pattern_set, write_pattern_set

__all__ = [
    "AggregationError_",
    "AggregationRequest",
    "AggregationStatistics",
    "AggregationStatus",
    "CorpusRef",
    "ObservedBelowThreshold",
    "Pattern",
    "PatternSet",
    "PopulationBasis",
    "ResolutionProvenance",
    "ResolutionStrategy",
    "SkippedAggregation",
    "ThresholdSpec",
    "aggregate_patterns",
    "read_pattern_set",
    "write_pattern_set",
]
