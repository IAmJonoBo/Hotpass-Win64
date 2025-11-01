from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest

from hotpass.data_sources.agents.runner import AgentTiming
from hotpass.pipeline.base import BasePipelineExecutor
from hotpass.pipeline.config import PipelineConfig, PipelineResult, QualityReport
from hotpass.pipeline.features import FeatureContext
from hotpass.pipeline.ingestion import _normalise_source_frame, ingest_sources
from hotpass.pipeline.orchestrator import PipelineExecutionConfig, PipelineOrchestrator
from hotpass.telemetry.metrics import PipelineMetrics


pytestmark = pytest.mark.bandwidth("smoke")


def _quality_report() -> QualityReport:
    return QualityReport(
        total_records=1,
        invalid_records=0,
        schema_validation_errors=[],
        expectations_passed=True,
        expectation_failures=[],
        source_breakdown={"agent": 1},
        data_quality_distribution={"mean": 0.9, "min": 0.9, "max": 0.9},
    )


class RecordingMetrics:
    def __init__(self) -> None:
        self.records_calls: list[tuple[int, str]] = []
        self.latest_quality: float | None = None

    def record_records_processed(self, count: int, source: str = "unknown") -> None:
        self.records_calls.append((count, source))

    def update_quality_score(self, score: float) -> None:
        self.latest_quality = score


def test_pipeline_orchestrator_runs_features_and_records_metrics(tmp_path: Path) -> None:
    """Pipeline orchestrator should execute base pipeline, optional features, and metrics hooks."""

    base_df = pd.DataFrame({"organization_name": ["Alpha"]})
    base_result = PipelineResult(
        refined=base_df,
        quality_report=_quality_report(),
        performance_metrics={},
    )

    class StubExecutor:
        def __init__(self) -> None:
            self.calls: list[PipelineConfig] = []

        def run(self, config: PipelineConfig) -> PipelineResult:
            self.calls.append(config)
            return base_result

    class RecordingFeature:
        name = "recording"

        def __init__(self) -> None:
            self.applied = False
            self.context: FeatureContext | None = None

        def is_enabled(self, context: FeatureContext) -> bool:
            self.context = context
            return True

        def apply(
            self, result: PipelineResult, context: FeatureContext
        ) -> PipelineResult:
            self.applied = True
            enhanced = result.refined.copy()
            enhanced["enhanced"] = True
            return PipelineResult(
                refined=enhanced,
                quality_report=result.quality_report,
                performance_metrics=result.performance_metrics,
                compliance_report=result.compliance_report,
                party_store=result.party_store,
                linkage=result.linkage,
                pii_redaction_events=list(result.pii_redaction_events),
                intent_signals=result.intent_signals,
                intent_digest=result.intent_digest,
                daily_list=result.daily_list,
            )

    executor = StubExecutor()
    metrics = RecordingMetrics()
    feature = RecordingFeature()

    execution = PipelineExecutionConfig(
        base_config=PipelineConfig(
            input_dir=(tmp_path / "input").resolve(),
            output_path=(tmp_path / "dist" / "refined.xlsx").resolve(),
        ),
        features=(feature,),
        metrics=cast(PipelineMetrics, metrics),
    )
    execution.base_config.input_dir.mkdir(parents=True, exist_ok=True)
    execution.base_config.output_path.parent.mkdir(parents=True, exist_ok=True)

    orchestrator = PipelineOrchestrator(
        base_executor=cast(BasePipelineExecutor, executor)
    )
    result = orchestrator.run(execution)

    assert executor.calls, "Base executor should be invoked."
    assert feature.applied, "Feature should be applied when enabled."
    assert feature.context is not None
    assert feature.context.metrics is execution.metrics
    assert list(result.refined.columns) == ["organization_name", "enhanced"]
    assert metrics.records_calls == [(1, "base_pipeline"), (1, "enhanced_pipeline")]
    assert metrics.latest_quality == pytest.approx(0.9)
    assert execution.trace_factory is not None, "Trace factory should be defaulted."


def test_ingest_sources_merges_agent_and_source_frames(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ingestion should combine preloaded agent data with discovered sources."""

    agent_frame = pd.DataFrame(
        [
            {
                "organization_name": "Alpha Air",
                "province": "GPretoria",
                "contact_emails": "ops@example.com",
            }
        ]
    )
    agent_timings = [AgentTiming(agent_name="agents", seconds=1.25, record_count=1)]

    source_frame = pd.DataFrame(
        [
            {
                "organization_name": "Beta Flyers",
                "province": "western cape",
                "contact_emails": "hello@beta.test",
            }
        ]
    )
    source_frame.attrs["load_seconds"] = 2.0

    def _fake_load_sources(
        input_dir: Path, country_code: str, excel_options: Any
    ) -> dict[str, pd.DataFrame]:
        return {"Contact Database": source_frame}

    monkeypatch.setattr("hotpass.pipeline.ingestion.load_sources", _fake_load_sources)

    config = PipelineConfig(
        input_dir=(tmp_path / "input").resolve(),
        output_path=(tmp_path / "dist" / "refined.xlsx").resolve(),
    )
    config.input_dir.mkdir(parents=True, exist_ok=True)
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    config.preloaded_agent_frame = agent_frame
    config.preloaded_agent_timings = agent_timings

    combined, timings, warnings = ingest_sources(config)

    assert len(combined) == 2
    assert combined.loc[0, "organization_slug"] == "alpha-air"
    assert combined.loc[0, "province"] == "Gauteng"
    assert combined.loc[1, "province"] == "Western Cape"
    assert timings == {"agent:agents": 1.25, "Contact Database": 2.0}
    assert warnings == []
    assert "contact_emails" in combined.columns


def test_normalise_source_frame_handles_duplicate_columns() -> None:
    """Normalisation should deduplicate column labels while preserving data."""

    frame = pd.DataFrame([[1, 2]], columns=["organization_name", "organization_name"])

    normalised = _normalise_source_frame(frame)

    assert normalised.columns.is_unique is True
    assert normalised.columns.tolist().count("organization_name") == 1
    assert "organization_name__dup1" in normalised.columns
    assert "province" in normalised.columns
    # Original frame columns are re-bound to match the deduplicated names.
    assert frame.columns.tolist().count("organization_name") == 1
    assert "organization_name__dup1" in frame.columns
