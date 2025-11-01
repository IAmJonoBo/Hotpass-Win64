"""Compatibility layer for legacy pipeline enhancement imports."""

from __future__ import annotations

from .pipeline.features import (
    ComplianceFeature,
    EnhancedPipelineConfig,
    EnrichmentFeature,
    EntityResolutionFeature,
    FeatureContext,
    GeospatialFeature,
    PipelineFeatureStrategy,
    TraceFactory,
    default_trace_factory,
)

__all__ = [
    "ComplianceFeature",
    "EnhancedPipelineConfig",
    "EnrichmentFeature",
    "EntityResolutionFeature",
    "FeatureContext",
    "GeospatialFeature",
    "PipelineFeatureStrategy",
    "TraceFactory",
    "default_trace_factory",
]
