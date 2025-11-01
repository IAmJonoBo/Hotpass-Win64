"""Intent-driven pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data_sources.agents import run_plan as run_acquisition_plan
from ..observability import PipelineMetrics
from .base import BasePipelineExecutor
from .config import PipelineConfig, PipelineResult
from .features import (
    ComplianceFeature,
    EnhancedPipelineConfig,
    EnrichmentFeature,
    EntityResolutionFeature,
    FeatureContext,
    GeospatialFeature,
    PipelineFeatureStrategy,
    TraceFactory,
    default_trace_factory,
    ensure_feature_sequence,
)


@dataclass(slots=True)
class PipelineExecutionConfig:
    """Configuration describing how the orchestrator should execute the pipeline."""

    base_config: PipelineConfig
    enhanced_config: EnhancedPipelineConfig = field(default_factory=EnhancedPipelineConfig)
    features: tuple[PipelineFeatureStrategy, ...] = field(default_factory=tuple)
    trace_factory: TraceFactory | None = None
    metrics: PipelineMetrics | None = None

    def with_default_trace_factory(self) -> PipelineExecutionConfig:
        if self.trace_factory is None:
            self.trace_factory = default_trace_factory(self.enhanced_config.enable_observability)
        return self


class PipelineOrchestrator:
    """Coordinate the base pipeline and optional feature strategies."""

    def __init__(self, base_executor: BasePipelineExecutor | None = None):
        self._base_executor = base_executor or BasePipelineExecutor()

    def run(self, execution: PipelineExecutionConfig) -> PipelineResult:
        execution = execution.with_default_trace_factory()
        execution.features = ensure_feature_sequence(execution.features)

        if (
            execution.enhanced_config.enable_acquisition
            and execution.base_config.acquisition_plan
            and execution.base_config.acquisition_plan.enabled
        ):
            agent_frame, agent_timings, agent_warnings = run_acquisition_plan(
                execution.base_config.acquisition_plan,
                country_code=execution.base_config.country_code,
                credentials=execution.base_config.agent_credentials,
            )
            execution.base_config.preloaded_agent_frame = agent_frame.copy(deep=True)
            execution.base_config.preloaded_agent_timings = list(agent_timings)
            execution.base_config.preloaded_agent_warnings.extend(agent_warnings)
            if execution.metrics and not agent_frame.empty:
                execution.metrics.record_records_processed(
                    len(agent_frame), source="acquisition_agents"
                )

        result: PipelineResult = self._base_executor.run(execution.base_config)

        if execution.metrics:
            execution.metrics.record_records_processed(len(result.refined), source="base_pipeline")

        if execution.trace_factory is None:
            raise RuntimeError(
                "PipelineExecutionConfig.trace_factory must be set before running the orchestrator."
            )

        context = FeatureContext(
            base_config=execution.base_config,
            enhanced_config=execution.enhanced_config,
            trace_factory=execution.trace_factory,
            metrics=execution.metrics,
        )

        for feature in execution.features:
            if feature.is_enabled(context):
                result = feature.apply(result, context)

        if execution.metrics:
            execution.metrics.record_records_processed(
                len(result.refined), source="enhanced_pipeline"
            )
            if (
                result.quality_report
                and result.quality_report.total_records > 0
                and "mean" in result.quality_report.data_quality_distribution
            ):
                execution.metrics.update_quality_score(
                    result.quality_report.data_quality_distribution.get("mean", 0.0)
                )

        return result


def default_feature_bundle() -> tuple[PipelineFeatureStrategy, ...]:
    """Return the default ordering of enhanced pipeline features."""

    return (
        EntityResolutionFeature(),
        GeospatialFeature(),
        EnrichmentFeature(),
        ComplianceFeature(),
    )
