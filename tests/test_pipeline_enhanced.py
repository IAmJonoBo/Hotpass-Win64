from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pandas as pd
import pytest

from tests.helpers.fixtures import fixture

pytest.importorskip("frictionless")

import hotpass.pipeline_enhanced as pipeline_enhanced
from hotpass.pipeline import (
    PIIRedactionConfig,
    PipelineConfig,
    PipelineExecutionConfig,
    PipelineOrchestrator,
    PipelineResult,
    QualityReport,
    default_feature_bundle,
)
from hotpass.pipeline.features import EnhancedPipelineConfig
from hotpass.pipeline_enhanced import _initialize_observability, run_enhanced_pipeline
from hotpass.telemetry.bootstrap import TelemetryBootstrapOptions


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@fixture(autouse=True)
def reset_observability(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Ensure observability state resets between tests."""

    import hotpass.observability as observability

    yield

    observability.shutdown_observability()


@fixture
def base_pipeline_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        input_dir=tmp_path,
        output_path=tmp_path / "refined.xlsx",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )


@fixture
def sample_result() -> PipelineResult:
    frame = pd.DataFrame({"organization_name": ["Alpha"]})
    report = QualityReport(
        total_records=1,
        invalid_records=0,
        schema_validation_errors=[],
        expectations_passed=True,
        expectation_failures=[],
        source_breakdown={},
        data_quality_distribution={"mean": 1.0},
        performance_metrics={},
    )
    return PipelineResult(refined=frame, quality_report=report, performance_metrics={})


def test_enhanced_pipeline_config_defaults():
    config = EnhancedPipelineConfig()

    expect(
        not config.enable_entity_resolution,
        "Entity resolution should be disabled by default.",
    )
    expect(
        not config.enable_geospatial,
        "Geospatial enrichment should be disabled by default.",
    )
    expect(not config.enable_enrichment, "Web enrichment should be disabled by default.")
    expect(not config.enable_compliance, "Compliance checks should be disabled by default.")
    expect(not config.enable_observability, "Observability should be disabled by default.")
    expect(
        config.entity_resolution_threshold == 0.75,
        "Default entity resolution threshold should be 0.75.",
    )
    expect(
        config.enrichment_concurrency == 8,
        "Default enrichment concurrency should be 8 workers.",
    )


def test_initialize_observability_disabled_returns_none(monkeypatch):
    config = EnhancedPipelineConfig(enable_observability=False)
    called = False

    def _guard(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(pipeline_enhanced, "bootstrap_metrics", _guard)

    expect(
        _initialize_observability(config) is None,
        "Telemetry bootstrap should not run when observability is disabled.",
    )
    expect(called is False, "Bootstrap helper should not be invoked when disabled.")


def test_initialize_observability_enabled_invokes_dependencies(monkeypatch):
    config = EnhancedPipelineConfig(
        enable_observability=True,
        telemetry_environment="qa",
        telemetry_attributes={
            "deployment.environment": "qa",
            "hotpass.profile": "aviation",
        },
    )
    metrics_mock = Mock()
    captured: dict[str, object] = {}

    def _fake_bootstrap(
        options: TelemetryBootstrapOptions,
        *,
        additional_attributes: Mapping[str, str] | None,
    ) -> Mock:
        captured["options"] = options
        captured["attributes"] = dict(additional_attributes or {})
        return metrics_mock

    monkeypatch.setattr(pipeline_enhanced, "bootstrap_metrics", _fake_bootstrap)

    expect(
        _initialize_observability(config, additional_attributes={"hotpass.command": "prefect"})
        is metrics_mock,
        "Bootstrap should return the metrics instance from the delegate.",
    )
    options = cast(TelemetryBootstrapOptions, captured["options"])
    expect(
        isinstance(options, TelemetryBootstrapOptions),
        "Bootstrap should receive telemetry bootstrap options.",
    )
    expect(options.enabled is True, "Telemetry should be enabled when requested.")
    expect(options.environment == "qa", "Environment override should propagate.")
    expect(options.service_name == "hotpass", "Default service name should be 'hotpass'.")
    expect(
        options.resource_attributes["hotpass.profile"] == "aviation",
        "Profile attribute should propagate to resource attributes.",
    )
    attributes = cast(dict[str, object], captured["attributes"])
    expect(
        attributes.get("hotpass.command") == "prefect",
        "Additional telemetry attributes should be forwarded.",
    )


def test_run_enhanced_pipeline_uses_orchestrator(monkeypatch, base_pipeline_config, sample_result):
    orchestrator_mock = Mock(spec=PipelineOrchestrator)
    orchestrator_mock.run.return_value = sample_result
    monkeypatch.setattr(pipeline_enhanced, "PipelineOrchestrator", lambda: orchestrator_mock)
    monkeypatch.setattr(pipeline_enhanced, "_initialize_observability", lambda *_: None)

    enhanced_config = EnhancedPipelineConfig(enable_entity_resolution=True)
    result = run_enhanced_pipeline(base_pipeline_config, enhanced_config)

    expect(result is sample_result, "Pipeline should return orchestrator result.")
    expect(
        orchestrator_mock.run.call_count == 1,
        "Orchestrator should be invoked once.",
    )
    (execution_config,) = orchestrator_mock.run.call_args.args
    expect(
        isinstance(execution_config, PipelineExecutionConfig),
        "Execution config should be constructed for the orchestrator.",
    )
    expect(
        execution_config.base_config is base_pipeline_config,
        "Base pipeline config should be forwarded unchanged.",
    )
    expect(
        execution_config.enhanced_config is enhanced_config,
        "Enhanced config should be forwarded unchanged.",
    )
    expect(
        execution_config.features == default_feature_bundle(),
        "Default feature bundle should be applied to the execution config.",
    )


def test_run_enhanced_pipeline_sets_default_linkage_dir(monkeypatch, tmp_path, sample_result):
    orchestrator_mock = Mock(spec=PipelineOrchestrator)
    orchestrator_mock.run.return_value = sample_result
    monkeypatch.setattr(pipeline_enhanced, "PipelineOrchestrator", lambda: orchestrator_mock)
    monkeypatch.setattr(pipeline_enhanced, "_initialize_observability", lambda *_: None)

    config = PipelineConfig(
        input_dir=tmp_path,
        output_path=tmp_path / "refined.xlsx",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )
    enhanced_config = EnhancedPipelineConfig(linkage_output_dir=None)

    run_enhanced_pipeline(config, enhanced_config)

    (execution_config,) = orchestrator_mock.run.call_args.args
    expect(
        execution_config.enhanced_config.linkage_output_dir
        == str(config.output_path.parent / "linkage"),
        "Linkage directory should default to the output parent when unset.",
    )


def test_run_enhanced_pipeline_initializes_observability(monkeypatch, base_pipeline_config):
    metrics_mock = Mock()
    orchestrator_mock = Mock(spec=PipelineOrchestrator)
    orchestrator_mock.run.return_value = Mock(spec=PipelineResult)
    monkeypatch.setattr(pipeline_enhanced, "PipelineOrchestrator", lambda: orchestrator_mock)
    monkeypatch.setattr(
        pipeline_enhanced,
        "_initialize_observability",
        lambda config: metrics_mock if config.enable_observability else None,
    )

    enhanced_config = EnhancedPipelineConfig(enable_observability=True)
    run_enhanced_pipeline(base_pipeline_config, enhanced_config)

    (execution_config,) = orchestrator_mock.run.call_args.args
    expect(
        execution_config.metrics is metrics_mock,
        "Metrics from observability bootstrap should be attached to execution config.",
    )


def test_run_enhanced_pipeline_uses_provided_metrics(monkeypatch, base_pipeline_config) -> None:
    orchestrator_mock = Mock(spec=PipelineOrchestrator)
    orchestrator_mock.run.return_value = Mock(spec=PipelineResult)
    monkeypatch.setattr(pipeline_enhanced, "PipelineOrchestrator", lambda: orchestrator_mock)
    sentinel_metrics = Mock()
    called = False

    def _guard(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(pipeline_enhanced, "_initialize_observability", _guard)

    enhanced_config = EnhancedPipelineConfig(enable_observability=True)
    run_enhanced_pipeline(
        base_pipeline_config,
        enhanced_config,
        metrics=sentinel_metrics,
    )

    (execution_config,) = orchestrator_mock.run.call_args.args
    expect(
        execution_config.metrics is sentinel_metrics,
        "Explicit metrics argument should override bootstrap results.",
    )
    expect(called is False, "Bootstrap should be skipped when metrics are supplied.")
