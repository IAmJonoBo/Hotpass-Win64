"""Integration-style tests for the `hotpass run` subcommand."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

pytest.importorskip("frictionless")

from hotpass import cli
from hotpass.pipeline import QualityReport
from hotpass.pipeline.orchestrator import PipelineExecutionConfig, PipelineOrchestrator


def _collect_json_lines(output: str) -> list[dict[str, Any]]:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_run_command_outputs_json_summary(
    sample_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_path = tmp_path / "refined.xlsx"

    exit_code = cli.main(
        [
            "run",
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(output_path),
            "--log-format",
            "json",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    log_records = _collect_json_lines(captured.out)
    summary = next(item for item in log_records if item["event"] == "pipeline.summary")

    assert summary["data"]["total_records"] == 2
    assert summary["data"]["expectations_passed"] is True
    metrics = summary["data"].get("performance_metrics")
    assert metrics is not None
    assert metrics["total_seconds"] >= 0.0
    assert metrics["rows_per_second"] > 0.0
    assert output_path.exists()


def test_run_command_writes_markdown_report(
    sample_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_path = tmp_path / "refined.xlsx"
    report_path = tmp_path / "report.md"

    exit_code = cli.main(
        [
            "run",
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(output_path),
            "--report-path",
            str(report_path),
            "--report-format",
            "markdown",
            "--log-format",
            "json",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    log_records = _collect_json_lines(captured.out)
    assert any(item["event"] == "report.write" for item in log_records)

    assert report_path.exists()
    contents = report_path.read_text()
    assert "Hotpass Quality Report" in contents
    assert "Total records" in contents
    assert "Performance Metrics" in contents


def test_run_command_merges_config_file(
    sample_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_path = tmp_path / "refined.xlsx"
    dist_dir = tmp_path / "dist"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"archive": True, "log_format": "json", "dist_dir": str(dist_dir)})
    )

    exit_code = cli.main(
        [
            "run",
            "--config",
            str(config_path),
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(output_path),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    log_records = _collect_json_lines(captured.out)
    archive_event = next(item for item in log_records if item["event"] == "archive.created")

    assert output_path.exists()
    assert Path(archive_event["data"]["path"]).exists()
    assert archive_event["data"]["path"].startswith(str(dist_dir))


def test_run_command_dispatches_automation_hooks(
    sample_data_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "refined.xlsx"
    signal_store = tmp_path / "intent-signals.json"
    daily_list_path = tmp_path / "daily.csv"

    webhook_calls: list[tuple[tuple[str, ...], int]] = []
    crm_calls: list[tuple[str, int]] = []

    def fake_dispatch(
        digest: pd.DataFrame,
        *,
        webhooks: tuple[str, ...],
        daily_list: pd.DataFrame | None = None,
        logger: object | None = None,
        **_: object,
    ) -> None:
        webhook_calls.append((webhooks, int(digest.shape[0])))

    def fake_push(
        daily: pd.DataFrame,
        endpoint: str,
        *,
        token: str | None = None,
        logger: object | None = None,
        **_: object,
    ) -> None:
        crm_calls.append((endpoint, int(daily.shape[0])))

    monkeypatch.setattr("hotpass.cli.commands.run.dispatch_webhooks", fake_dispatch)
    monkeypatch.setattr("hotpass.cli.commands.run.push_crm_updates", fake_push)

    exit_code = cli.main(
        [
            "run",
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(output_path),
            "--log-format",
            "json",
            "--intent-signal-store",
            str(signal_store),
            "--daily-list-path",
            str(daily_list_path),
            "--daily-list-size",
            "1",
            "--intent-webhook",
            "https://webhook.test/intent",
            "--crm-endpoint",
            "https://crm.test/api/leads",
            "--crm-token",
            "secret-token",
        ]
    )

    assert exit_code == 0
    capsys.readouterr()
    assert webhook_calls
    assert crm_calls
    assert signal_store.exists()
    assert daily_list_path.exists()


def test_run_command_supports_rich_logging(
    sample_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_path = tmp_path / "refined.xlsx"
    report_path = tmp_path / "report.html"
    dist_dir = tmp_path / "dist"

    exit_code = cli.main(
        [
            "run",
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(output_path),
            "--log-format",
            "rich",
            "--report-path",
            str(report_path),
            "--archive",
            "--dist-dir",
            str(dist_dir),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Hotpass Quality Report" in captured.out
    assert "Archive created" in captured.out
    assert "Load seconds" in captured.out
    assert report_path.exists()
    assert report_path.suffix == ".html"


def test_run_command_attaches_progress_listener_when_rich_logging(
    sample_data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_listener: Callable[[str, dict[str, Any]], None] | None = None

    class DummyResult:
        def __init__(self) -> None:
            self.party_store = None
            self.quality_report = QualityReport(
                total_records=0,
                invalid_records=0,
                schema_validation_errors=[],
                expectations_passed=True,
                expectation_failures=[],
                source_breakdown={},
                data_quality_distribution={"mean": 0.0, "min": 0.0, "max": 0.0},
                performance_metrics={},
            )
            self.intent_digest = pd.DataFrame()
            self.daily_list = pd.DataFrame()

    def fake_run_pipeline(
        self: PipelineOrchestrator, execution: PipelineExecutionConfig
    ) -> DummyResult:
        nonlocal captured_listener
        captured_listener = execution.base_config.progress_listener
        return DummyResult()

    monkeypatch.setattr(PipelineOrchestrator, "run", fake_run_pipeline, raising=False)

    exit_code = cli.main(
        [
            "run",
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(tmp_path / "refined.xlsx"),
            "--log-format",
            "rich",
        ]
    )

    assert exit_code == 0
    assert captured_listener is not None


def test_run_command_accepts_excel_tuning_options(
    sample_data_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "refined.xlsx"
    stage_dir = tmp_path / "stage"

    calls: list[Path] = []

    def _fake_to_parquet(_df: pd.DataFrame, path: Path, *, index: bool = False) -> None:
        calls.append(Path(path))

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _fake_to_parquet, raising=False)

    exit_code = cli.main(
        [
            "run",
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(output_path),
            "--log-format",
            "json",
            "--excel-chunk-size",
            "1",
            "--excel-stage-dir",
            str(stage_dir),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    summary = next(
        item for item in _collect_json_lines(captured.out) if item["event"] == "pipeline.summary"
    )
    assert summary["data"]["total_records"] == 2
    assert calls, "staging to parquet should be attempted when a stage directory is provided"


def test_structured_logger_json_logs_redact_sensitive_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    logger = cli.StructuredLogger("json", ["email"])
    report = QualityReport(
        total_records=1,
        invalid_records=0,
        schema_validation_errors=[],
        expectations_passed=True,
        expectation_failures=[],
        source_breakdown={},
        data_quality_distribution={"mean": 1.0, "min": 1.0, "max": 1.0},
        performance_metrics={},
        audit_trail=[{"contact_email": "sensitive@example.com"}],
    )

    logger.log_summary(report)

    captured = capsys.readouterr()
    records = _collect_json_lines(captured.out)
    summary = next(item for item in records if item["event"] == "pipeline.summary")
    masked = summary["data"]["audit_trail"][0]["contact_email"]
    assert masked == cli.REDACTED_PLACEHOLDER


def test_structured_logger_rich_error_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    logger = cli.StructuredLogger("rich")
    logger.log_error("something went wrong")

    captured = capsys.readouterr()
    assert "something went wrong" in captured.out
