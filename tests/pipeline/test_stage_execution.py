"""Regression coverage for modular pipeline stage orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hotpass.compliance import PIIRedactionConfig
from hotpass.pipeline import (
    PIPELINE_EVENT_AGGREGATE_COMPLETED,
    PIPELINE_EVENT_AGGREGATE_PROGRESS,
    PIPELINE_EVENT_AGGREGATE_STARTED,
    PIPELINE_EVENT_COMPLETED,
    PIPELINE_EVENT_EXPECTATIONS_COMPLETED,
    PIPELINE_EVENT_EXPECTATIONS_STARTED,
    PIPELINE_EVENT_LOAD_COMPLETED,
    PIPELINE_EVENT_LOAD_STARTED,
    PIPELINE_EVENT_SCHEMA_COMPLETED,
    PIPELINE_EVENT_SCHEMA_STARTED,
    PIPELINE_EVENT_START,
    PIPELINE_EVENT_WRITE_COMPLETED,
    PIPELINE_EVENT_WRITE_STARTED,
    PipelineConfig,
)
from hotpass.pipeline.base import execute_pipeline
from hotpass.pipeline.config import PipelineResult

from tests.pipeline.fixtures import (
    ModularStageArtifacts,
    build_aggregation_result,
    build_modular_stage_artifacts,
    build_validation_result,
)

pytestmark = pytest.mark.bandwidth("smoke")


def expect(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def _filtered_events(events: list[str]) -> list[str]:
    expected = {
        PIPELINE_EVENT_START,
        PIPELINE_EVENT_LOAD_STARTED,
        PIPELINE_EVENT_LOAD_COMPLETED,
        PIPELINE_EVENT_AGGREGATE_STARTED,
        PIPELINE_EVENT_AGGREGATE_PROGRESS,
        PIPELINE_EVENT_AGGREGATE_COMPLETED,
        PIPELINE_EVENT_SCHEMA_STARTED,
        PIPELINE_EVENT_SCHEMA_COMPLETED,
        PIPELINE_EVENT_EXPECTATIONS_STARTED,
        PIPELINE_EVENT_EXPECTATIONS_COMPLETED,
        PIPELINE_EVENT_WRITE_STARTED,
        PIPELINE_EVENT_WRITE_COMPLETED,
        PIPELINE_EVENT_COMPLETED,
    }
    return [event for event in events if event in expected]


def _configure_pipeline(tmp_path: Path, listener: Any) -> PipelineConfig:
    return PipelineConfig(
        input_dir=tmp_path,
        output_path=tmp_path / "refined.parquet",
        enable_formatting=False,
        enable_audit_trail=False,
        enable_recommendations=False,
        pii_redaction=PIIRedactionConfig(enabled=False),
        progress_listener=listener,
    )


def test_execute_pipeline_invokes_modular_stages_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifacts: ModularStageArtifacts = build_modular_stage_artifacts()
    stage_calls: list[str] = []
    progress_events: list[str] = []

    def listener(event: str, payload: dict[str, Any]) -> None:
        progress_events.append(event)

    def fake_ingest(config: PipelineConfig):
        stage_calls.append("ingest")
        expect(
            isinstance(config, PipelineConfig),
            "ingest should receive pipeline configuration",
        )
        return (
            artifacts.combined.copy(deep=True),
            {"Contact Database": 0.25},
            [],
        )

    def fake_aggregate(
        config: PipelineConfig,
        combined: pd.DataFrame,
        intent_summary_lookup: Any,
        notify_progress: Any,
    ):
        stage_calls.append("aggregate")
        expect(
            combined.equals(artifacts.combined),
            "aggregator should receive combined dataframe from ingestion",
        )
        notify_progress("aggregate_started", {"total": len(combined)})
        notify_progress(
            "aggregate_progress",
            {"completed": len(combined), "total": len(combined), "slug": "alpha-org"},
        )
        notify_progress(
            "aggregate_completed",
            {
                "total": len(combined),
                "aggregated_records": len(artifacts.refined),
                "conflicts": 0,
            },
        )
        return build_aggregation_result(artifacts)

    def fake_validate(
        config: PipelineConfig,
        refined_df: pd.DataFrame,
        notify_progress: Any,
    ):
        stage_calls.append("validate")
        expect(
            refined_df.equals(artifacts.refined),
            "validation stage should operate on aggregated dataframe",
        )
        notify_progress("schema_started", {"total_records": len(refined_df)})
        notify_progress("schema_completed", {"errors": 0})
        notify_progress("expectations_started", {"total_records": len(refined_df)})
        notify_progress(
            "expectations_completed",
            {"success": True, "failure_count": 0},
        )
        return build_validation_result(artifacts)

    def fake_publish(
        config: PipelineConfig,
        validated_df: pd.DataFrame,
        refined_df: pd.DataFrame,
        expectation_summary: Any,
        metrics: dict[str, Any],
        pipeline_start: float,
        notify_progress: Any,
        *,
        intent_result: Any = None,
    ):
        stage_calls.append("export")
        expect(
            validated_df.equals(artifacts.validated),
            "export should receive validated dataframe",
        )
        expect(
            refined_df.equals(artifacts.refined),
            "export should also receive aggregated dataframe",
        )
        expect(
            expectation_summary == artifacts.expectation_summary,
            "expectation summary should flow through to export stage",
        )
        notify_progress("write_started", {"path": str(config.output_path)})
        notify_progress(
            "write_completed",
            {"path": str(config.output_path), "write_seconds": 0.01},
        )
        return (
            {
                "write_seconds": 0.01,
                "total_seconds": metrics.get("load_seconds", 0.0) + 0.01,
                "rows_per_second": len(validated_df),
            },
            None,
            None,
        )

    monkeypatch.setattr("hotpass.pipeline.base.ingest_sources", fake_ingest)
    monkeypatch.setattr("hotpass.pipeline.base.aggregate_records", fake_aggregate)
    monkeypatch.setattr("hotpass.pipeline.base.validate_dataset", fake_validate)
    monkeypatch.setattr("hotpass.pipeline.base.publish_outputs", fake_publish)

    config = _configure_pipeline(tmp_path, listener)
    result: PipelineResult = execute_pipeline(config)

    expect(
        stage_calls == ["ingest", "aggregate", "validate", "export"],
        "Pipeline should execute modular stages in order",
    )

    filtered = _filtered_events(progress_events)
    expect(
        filtered
        == [
            PIPELINE_EVENT_START,
            PIPELINE_EVENT_LOAD_STARTED,
            PIPELINE_EVENT_LOAD_COMPLETED,
            PIPELINE_EVENT_AGGREGATE_STARTED,
            PIPELINE_EVENT_AGGREGATE_PROGRESS,
            PIPELINE_EVENT_AGGREGATE_COMPLETED,
            PIPELINE_EVENT_SCHEMA_STARTED,
            PIPELINE_EVENT_SCHEMA_COMPLETED,
            PIPELINE_EVENT_EXPECTATIONS_STARTED,
            PIPELINE_EVENT_EXPECTATIONS_COMPLETED,
            PIPELINE_EVENT_WRITE_STARTED,
            PIPELINE_EVENT_WRITE_COMPLETED,
            PIPELINE_EVENT_COMPLETED,
        ],
        "Pipeline progress events should mirror stage execution",
    )

    expect(
        result.quality_report.total_records == len(artifacts.refined),
        "Quality report should capture aggregated record count",
    )
    expect(
        result.quality_report.source_breakdown == artifacts.source_breakdown,
        "Source breakdown should propagate from aggregation",
    )
    expect(
        result.performance_metrics.get("aggregation_seconds") == 0.12,
        "Aggregation metrics should be merged into performance output",
    )
    expect(
        "write_seconds" in result.performance_metrics,
        "Export stage should contribute write metrics",
    )
    expect(
        result.quality_report.expectations_passed,
        "Validation summary should mark expectations as passed",
    )
