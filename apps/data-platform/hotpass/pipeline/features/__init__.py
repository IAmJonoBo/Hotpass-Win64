"""Feature strategies for the Hotpass pipeline orchestrator."""

from .base import (
    FeatureContext,
    PipelineFeatureStrategy,
    TraceFactory,
    default_trace_factory,
    ensure_feature_sequence,
)
from .compliance import ComplianceFeature
from .config import EnhancedPipelineConfig
from .enrichment import EnrichmentFeature
from .entity_resolution import EntityResolutionFeature
from .geospatial import GeospatialFeature

__all__ = [
    "FeatureContext",
    "PipelineFeatureStrategy",
    "TraceFactory",
    "default_trace_factory",
    "ensure_feature_sequence",
    "EnhancedPipelineConfig",
    "ComplianceFeature",
    "EnrichmentFeature",
    "EntityResolutionFeature",
    "GeospatialFeature",
]
