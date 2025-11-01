"""Public pipeline API backed by the intent-driven orchestrator."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from ..quality import build_ssot_schema as _default_build_ssot_schema

if TYPE_CHECKING:  # pragma: no cover - typing only
    from hotpass.config_schema import HotpassConfig

    from .base import PipelineConfig, PipelineResult

__all__ = [
    "PIIRedactionConfig",
    "PipelineConfig",
    "PipelineResult",
    "QualityReport",
    "PipelineExecutionConfig",
    "PipelineOrchestrator",
    "EnhancedPipelineConfig",
    "default_feature_bundle",
    "PIPELINE_EVENT_START",
    "PIPELINE_EVENT_LOAD_STARTED",
    "PIPELINE_EVENT_LOAD_COMPLETED",
    "PIPELINE_EVENT_AGGREGATE_STARTED",
    "PIPELINE_EVENT_AGGREGATE_PROGRESS",
    "PIPELINE_EVENT_AGGREGATE_COMPLETED",
    "PIPELINE_EVENT_SCHEMA_STARTED",
    "PIPELINE_EVENT_SCHEMA_COMPLETED",
    "PIPELINE_EVENT_EXPECTATIONS_STARTED",
    "PIPELINE_EVENT_EXPECTATIONS_COMPLETED",
    "PIPELINE_EVENT_WRITE_STARTED",
    "PIPELINE_EVENT_WRITE_COMPLETED",
    "PIPELINE_EVENT_COMPLETED",
    "SSOT_COLUMNS",
    "_aggregate_group",
    "build_ssot_schema",
    "run_pipeline",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "PIIRedactionConfig": ("hotpass.compliance", "PIIRedactionConfig"),
    "PipelineConfig": ("hotpass.pipeline.config", "PipelineConfig"),
    "PipelineResult": ("hotpass.pipeline.config", "PipelineResult"),
    "QualityReport": ("hotpass.pipeline.config", "QualityReport"),
    "PipelineExecutionConfig": (
        "hotpass.pipeline.orchestrator",
        "PipelineExecutionConfig",
    ),
    "PipelineOrchestrator": ("hotpass.pipeline.orchestrator", "PipelineOrchestrator"),
    "EnhancedPipelineConfig": (
        "hotpass.pipeline.features",
        "EnhancedPipelineConfig",
    ),
    "default_feature_bundle": (
        "hotpass.pipeline.orchestrator",
        "default_feature_bundle",
    ),
    "PIPELINE_EVENT_START": ("hotpass.pipeline.events", "PIPELINE_EVENT_START"),
    "PIPELINE_EVENT_LOAD_STARTED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_LOAD_STARTED",
    ),
    "PIPELINE_EVENT_LOAD_COMPLETED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_LOAD_COMPLETED",
    ),
    "PIPELINE_EVENT_AGGREGATE_STARTED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_AGGREGATE_STARTED",
    ),
    "PIPELINE_EVENT_AGGREGATE_PROGRESS": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_AGGREGATE_PROGRESS",
    ),
    "PIPELINE_EVENT_AGGREGATE_COMPLETED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_AGGREGATE_COMPLETED",
    ),
    "PIPELINE_EVENT_SCHEMA_STARTED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_SCHEMA_STARTED",
    ),
    "PIPELINE_EVENT_SCHEMA_COMPLETED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_SCHEMA_COMPLETED",
    ),
    "PIPELINE_EVENT_EXPECTATIONS_STARTED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_EXPECTATIONS_STARTED",
    ),
    "PIPELINE_EVENT_EXPECTATIONS_COMPLETED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_EXPECTATIONS_COMPLETED",
    ),
    "PIPELINE_EVENT_WRITE_STARTED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_WRITE_STARTED",
    ),
    "PIPELINE_EVENT_WRITE_COMPLETED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_WRITE_COMPLETED",
    ),
    "PIPELINE_EVENT_COMPLETED": (
        "hotpass.pipeline.events",
        "PIPELINE_EVENT_COMPLETED",
    ),
    "SSOT_COLUMNS": ("hotpass.pipeline.config", "SSOT_COLUMNS"),
    "_aggregate_group": ("hotpass.pipeline.aggregation", "_aggregate_group"),
    "run_pipeline": ("hotpass.pipeline.orchestrator", "run_pipeline"),
}


def __getattr__(name: str) -> Any:
    """Load pipeline exports lazily to avoid heavy optional imports."""

    try:
        module_name, attribute = _LAZY_ATTRS[name]
    except KeyError as exc:  # pragma: no cover - mirrors default behaviour
        raise AttributeError(f"module 'hotpass.pipeline' has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attribute)
    globals()[name] = value
    return value


def build_ssot_schema() -> Any:
    """Return the default SSOT schema descriptor."""

    return _default_build_ssot_schema()


def run_pipeline(config: PipelineConfig | HotpassConfig) -> PipelineResult:
    """Execute the pipeline using the orchestrator interface."""

    from hotpass.config_schema import HotpassConfig as HotpassConfigType

    from .orchestrator import PipelineExecutionConfig, PipelineOrchestrator, default_feature_bundle

    orchestrator = PipelineOrchestrator()

    if isinstance(config, HotpassConfigType):
        execution = PipelineExecutionConfig(
            base_config=config.to_pipeline_config(),
            enhanced_config=config.to_enhanced_config(),
            features=default_feature_bundle(),
        )
        return orchestrator.run(execution)

    execution = PipelineExecutionConfig(base_config=config)
    return orchestrator.run(execution)
