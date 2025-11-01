"""Orchestrates the optional feature set for the enhanced pipeline."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from .pipeline.base import PipelineConfig, PipelineResult
from .pipeline.features import EnhancedPipelineConfig
from .pipeline.orchestrator import (
    PipelineExecutionConfig,
    PipelineOrchestrator,
    default_feature_bundle,
)
from .telemetry.bootstrap import TelemetryBootstrapOptions, bootstrap_metrics
from .telemetry.metrics import PipelineMetrics

logger = logging.getLogger(__name__)

__all__ = ["EnhancedPipelineConfig", "run_enhanced_pipeline"]


def run_enhanced_pipeline(
    config: PipelineConfig,
    enhanced_config: EnhancedPipelineConfig | None = None,
    *,
    metrics: PipelineMetrics | None = None,
) -> PipelineResult:
    """Run the enhanced pipeline with all features enabled.

    Args:
        config: Base pipeline configuration
        enhanced_config: Enhanced feature configuration

    Returns:
        Pipeline result with enhanced features applied
    """
    if enhanced_config is None:
        enhanced_config = EnhancedPipelineConfig()

    if enhanced_config.linkage_output_dir is None:
        enhanced_config.linkage_output_dir = str(config.output_path.parent / "linkage")

    metrics_instance = metrics
    if metrics_instance is None:
        metrics_instance = _initialize_observability(enhanced_config)

    orchestrator = PipelineOrchestrator()
    execution = PipelineExecutionConfig(
        base_config=config,
        enhanced_config=enhanced_config,
        features=default_feature_bundle(),
        metrics=metrics_instance,
    )

    return orchestrator.run(execution)


def _initialize_observability(
    config: EnhancedPipelineConfig,
    *,
    additional_attributes: Mapping[str, str] | None = None,
) -> PipelineMetrics | None:
    """Initialise observability when requested and return the metrics sink."""

    if not config.enable_observability:
        return None

    options = TelemetryBootstrapOptions(
        enabled=True,
        service_name=config.telemetry_service_name,
        environment=config.telemetry_environment,
        exporters=config.telemetry_exporters,
        resource_attributes=config.telemetry_attributes,
        exporter_settings=config.telemetry_exporter_settings,
    )
    metrics = bootstrap_metrics(options, additional_attributes=additional_attributes)
    logger.info("Observability initialized")
    return metrics
