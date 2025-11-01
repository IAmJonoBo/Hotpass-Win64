"""Tests for Prefect orchestration module."""

# ruff: noqa: E402

import importlib
import sys
import zipfile
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime
from importlib import util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock, patch

import anyio
import pandas as pd
import pytest
from hotpass.telemetry.bootstrap import TelemetryBootstrapOptions

from tests.helpers.fixtures import fixture
from tests.helpers.pytest_marks import anyio_mark
from tests.helpers.stubs import (
    make_duckdb_stub,
    make_pandera_stub,
    make_polars_stub,
    make_rapidfuzz_stub,
)

make_pandera_stub()
make_rapidfuzz_stub()
make_duckdb_stub()
if util.find_spec("polars") is None:
    make_polars_stub()

sys.modules.setdefault("frictionless", ModuleType("frictionless"))

from hotpass.config_schema import HotpassConfig

if TYPE_CHECKING:
    from hotpass.orchestration import PipelineRunOptions as PipelineRunOptionsType
    from hotpass.orchestration import PipelineRunSummary as PipelineRunSummaryType

pytest.importorskip("frictionless")

orchestration = importlib.import_module("hotpass.orchestration")
PipelineOrchestrationError = orchestration.PipelineOrchestrationError
PipelineRunOptions = orchestration.PipelineRunOptions
PipelineRunSummary = orchestration.PipelineRunSummary
backfill_pipeline_flow = orchestration.backfill_pipeline_flow
refinement_pipeline_flow = orchestration.refinement_pipeline_flow
run_pipeline_once = orchestration.run_pipeline_once
run_pipeline_task = orchestration.run_pipeline_task
_run_with_prefect_concurrency = orchestration._run_with_prefect_concurrency
_execute_with_concurrency = orchestration._execute_with_concurrency
_format_archive_path = orchestration._format_archive_path

if not TYPE_CHECKING:
    PipelineRunOptionsType = PipelineRunOptions  # type: ignore[assignment]
    PipelineRunSummaryType = PipelineRunSummary  # type: ignore[assignment]


def expect(condition: bool, message: str) -> None:
    """Raise a descriptive failure when the condition is false."""

    if not condition:
        pytest.fail(message)


@fixture
def anyio_backend() -> str:
    """Limit anyio tests to the asyncio backend to avoid trio dependency."""

    return "asyncio"


@fixture(autouse=True)
def reset_orchestration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Prefect decorators do not retain state between tests."""

    monkeypatch.setattr(orchestration, "flow", orchestration.flow, raising=False)
    monkeypatch.setattr(orchestration, "task", orchestration.task, raising=False)


@fixture(autouse=True)
def disable_prefect_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from starting ephemeral Prefect servers."""

    @asynccontextmanager
    async def _noop_concurrency(*_args, **_kwargs):  # pragma: no cover - helper
        yield

    monkeypatch.setattr(
        orchestration,
        "prefect_concurrency",
        _noop_concurrency,
        raising=False,
    )


@fixture
def mock_pipeline_result():
    """Create a mock pipeline result."""
    result = Mock()
    result.refined = pd.DataFrame({"col": [1, 2, 3]})
    result.quality_report = Mock()
    result.quality_report.to_dict = Mock(return_value={"test": "data"})
    result.quality_report.expectations_passed = True
    return result


def test_run_pipeline_once_success(mock_pipeline_result, tmp_path):
    """The orchestration helper returns a structured summary on success."""
    config = HotpassConfig().merge(
        {
            "pipeline": {
                "input_dir": tmp_path,
                "output_path": tmp_path / "out.xlsx",
                "archive": True,
                "dist_dir": tmp_path / "dist",
            }
        }
    )
    options = PipelineRunOptions(config=config, profile_name="aviation")

    with (
        patch("hotpass.orchestration.run_pipeline") as mock_run,
        patch("hotpass.orchestration.create_refined_archive") as mock_archive,
    ):
        mock_run.return_value = mock_pipeline_result
        mock_archive.return_value = tmp_path / "dist" / "archive.zip"

        summary = run_pipeline_once(options)

    expect(summary.success is True, "Pipeline summary should mark execution as successful")
    expect(summary.total_records == 3, "Expected three records in the refined output")
    expect(
        summary.archive_path == tmp_path / "dist" / "archive.zip",
        "Archive path should include the dist directory",
    )


def test_format_archive_path_invalid_pattern(tmp_path: Path) -> None:
    """Archive path helper should raise an orchestration error when formatting fails."""

    with pytest.raises(PipelineOrchestrationError) as captured:
        _format_archive_path(tmp_path, "{bad", date.today(), "v1")

    expect(
        "Invalid archive pattern" in str(captured.value),
        "Formatting errors should surface as orchestration exceptions",
    )


def test_run_pipeline_task_success(mock_pipeline_result, tmp_path):
    """Test successful pipeline task execution."""
    mock_config = Mock()
    mock_config.input_dir = Path("/tmp")
    mock_config.output_path = Path("/tmp/output.xlsx")

    with (
        patch("hotpass.orchestration.run_pipeline") as mock_run,
        patch("hotpass.orchestration.get_default_profile") as mock_profile,
    ):
        mock_run.return_value = mock_pipeline_result
        mock_profile.return_value = Mock()

        result = run_pipeline_task(mock_config)

        expect(result["success"] is True, "Task helper should mark execution as successful")
        expect(
            result["total_records"] == 3,
            "Expected three refined records in task summary",
        )
        expect(
            "elapsed_seconds" in result,
            "Elapsed time should be reported in task summary",
        )
        expect(result["backfill"] is False, "Backfill flag should default to False")
        expect(result["incremental"] is False, "Incremental flag should default to False")
        expect(result.get("since") is None, "Since parameter should be omitted by default")
        expect(
            "quality_report" in result,
            "Quality report data should be present in summary",
        )


def test_run_pipeline_task_validation_failure(mock_pipeline_result):
    """Test pipeline task with validation failure."""
    mock_config = Mock()
    mock_config.input_dir = Path("/tmp")
    mock_config.output_path = Path("/tmp/output.xlsx")
    mock_pipeline_result.quality_report.expectations_passed = False

    with patch("hotpass.orchestration.run_pipeline") as mock_run:
        mock_run.return_value = mock_pipeline_result

        result = run_pipeline_task(mock_config)

        expect(
            result["success"] is False,
            "Task helper should record failure when validation fails",
        )


def test_run_pipeline_once_archiving_error(mock_pipeline_result, tmp_path):
    """Archiving failures raise a structured orchestration error."""
    config = HotpassConfig().merge(
        {
            "pipeline": {
                "input_dir": tmp_path,
                "output_path": tmp_path / "out.xlsx",
                "archive": True,
                "dist_dir": tmp_path / "dist",
            }
        }
    )
    options = PipelineRunOptions(config=config, profile_name="aviation")

    with (
        patch("hotpass.orchestration.run_pipeline") as mock_run,
        patch(
            "hotpass.orchestration.create_refined_archive",
            side_effect=ValueError("boom"),
        ),
    ):
        mock_run.return_value = mock_pipeline_result

        with pytest.raises(PipelineOrchestrationError) as exc:
            run_pipeline_once(options)

    expect(
        "Failed to create archive" in str(exc.value),
        "Archiving errors should raise a descriptive orchestration error",
    )


def test_run_pipeline_once_injects_metrics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Enhanced runner should receive telemetry metrics when available."""

    config = HotpassConfig().merge(
        {
            "pipeline": {
                "input_dir": tmp_path,
                "output_path": tmp_path / "out.xlsx",
                "archive": False,
                "dist_dir": tmp_path / "dist",
            },
            "features": {"observability": True},
            "telemetry": {
                "enabled": True,
                "service_name": "hotpass-tests",
                "environment": "qa",
                "exporters": ["console"],
                "resource_attributes": {"region": "eu"},
            },
        }
    )

    metrics_token = object()
    captured: dict[str, object] = {}

    @contextmanager
    def _tracking_session(
        options: object,
        *,
        additional_attributes: dict[str, str] | None = None,
        auto_shutdown: bool = True,
    ):
        captured["session_options"] = options
        captured["attributes"] = dict(additional_attributes or {})
        captured["auto_shutdown"] = auto_shutdown
        yield metrics_token

    def _enhanced_runner(
        pipeline_config: object,
        *,
        metrics: object | None = None,
        extra: str | None = None,
    ) -> object:
        captured["runner_config"] = pipeline_config
        captured["metrics"] = metrics
        captured["extra"] = extra
        refined_rows = [{"id": index} for index in range(7)]
        quality_report = SimpleNamespace(
            to_dict=lambda: {"rows": len(refined_rows)},
            expectations_passed=True,
        )
        return SimpleNamespace(refined=refined_rows, quality_report=quality_report)

    _enhanced_runner.__name__ = "run_enhanced_pipeline"

    monkeypatch.setattr(orchestration, "telemetry_session", _tracking_session)

    options = PipelineRunOptions(
        config=config,
        profile_name="aviation",
        runner=_enhanced_runner,
        runner_kwargs={"extra": "value"},
        telemetry_context={"hotpass.custom": "demo", "skip": None},
    )

    summary = run_pipeline_once(options)

    expect(summary.total_records == 7, "Summary should reflect enhanced runner output")
    expect(
        captured["metrics"] is metrics_token,
        "Metrics token should be injected into runner",
    )
    expect(captured.get("extra") == "value", "Additional runner kwargs should propagate")

    attributes = cast(dict[str, object], captured["attributes"])
    expect(
        attributes["hotpass.command"] == "prefect.run_pipeline_once",
        "Default telemetry command should be recorded.",
    )
    expect(
        attributes["hotpass.profile"] == "aviation",
        "Telemetry context should include the profile identifier.",
    )
    expect(
        attributes.get("skip") is None,
        "Telemetry context should drop keys with null values.",
    )
    expect(
        attributes["hotpass.custom"] == "demo",
        "Custom telemetry context entries should propagate.",
    )

    session_options = cast(TelemetryBootstrapOptions, captured["session_options"])
    expect(
        getattr(session_options, "service_name", None) == "hotpass-tests",
        "Telemetry session should receive the configured service name.",
    )
    expect(
        getattr(session_options, "environment", None) == "qa",
        "Telemetry session should receive the configured environment.",
    )


def test_refinement_pipeline_flow(mock_pipeline_result, tmp_path):
    """Test the complete pipeline flow."""
    with (
        patch("hotpass.orchestration.run_pipeline") as mock_run,
        patch("hotpass.orchestration.get_default_profile") as mock_profile,
    ):
        mock_run.return_value = mock_pipeline_result
        mock_profile.return_value = Mock()

        result = refinement_pipeline_flow(
            input_dir=str(tmp_path),
            output_path=str(tmp_path / "output.xlsx"),
            profile_name="aviation",
        )

        expect(
            result["success"] is True,
            "Flow should return successful summary by default",
        )
        expect(
            result["total_records"] == 3,
            "Refinement flow should surface refined row count",
        )
        expect(
            "elapsed_seconds" in result,
            "Refinement flow summary should include elapsed time",
        )


def test_refinement_pipeline_flow_with_options(mock_pipeline_result, tmp_path):
    """Test pipeline flow with optional parameters."""
    with (
        patch("hotpass.orchestration.run_pipeline") as mock_run,
        patch("hotpass.orchestration.get_default_profile") as mock_profile,
        patch("hotpass.orchestration.create_refined_archive") as mock_archive,
    ):
        mock_run.return_value = mock_pipeline_result
        mock_profile.return_value = Mock()
        mock_archive.return_value = tmp_path / "dist" / "archive.zip"

        result = refinement_pipeline_flow(
            input_dir=str(tmp_path),
            output_path=str(tmp_path / "output.xlsx"),
            profile_name="generic",
            excel_chunk_size=1000,
            archive=True,
            dist_dir=str(tmp_path / "dist"),
        )

        expect(result["success"] is True, "Flow should succeed when archive is requested")
        expect(mock_run.call_count == 1, "Pipeline should execute exactly once in flow")

        # Verify config was built with correct options
        config_arg = mock_run.call_args[0][0]
        expect(
            config_arg.excel_options.chunk_size == 1000,
            "Excel chunk size should propagate to pipeline configuration",
        )
        expect(
            config_arg.backfill is False,
            "Backfill flag should default to False in flow",
        )
        expect(
            config_arg.incremental is False,
            "Incremental flag should default to False in flow",
        )
        expect(config_arg.since is None, "Since parameter should default to None in flow")


def test_refinement_pipeline_flow_propagates_runtime_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Runtime flags should populate the canonical pipeline configuration."""

    captured: list[PipelineRunOptionsType] = []

    def _record_run(
        options: PipelineRunOptionsType,
    ) -> PipelineRunSummaryType:
        captured.append(options)
        return cast(
            PipelineRunSummaryType,
            PipelineRunSummary(
                success=True,
                total_records=1,
                elapsed_seconds=0.25,
                output_path=tmp_path / "outputs" / "refined.xlsx",
                quality_report={"rows": 1},
            ),
        )

    monkeypatch.setattr(orchestration, "run_pipeline_once", _record_run)
    monkeypatch.setattr(
        orchestration,
        "get_default_profile",
        lambda _name: SimpleNamespace(model_dump=lambda: {"profile": "aviation"}),
    )
    monkeypatch.setattr(
        orchestration,
        "create_refined_archive",
        lambda *_args, **_kwargs: tmp_path / "dist" / "archive.zip",
    )

    since_iso = "2024-01-01T05:06:07+00:00"
    result = refinement_pipeline_flow(
        input_dir=str(tmp_path / "inputs"),
        output_path=str(tmp_path / "outputs" / "refined.xlsx"),
        profile_name="aviation",
        backfill=True,
        incremental=True,
        since=since_iso,
        telemetry_enabled=True,
        telemetry_exporters=["console"],
        telemetry_service_name="hotpass-prefect",
        telemetry_environment="staging",
        telemetry_resource_attributes={"deployment": "prefect"},
        telemetry_otlp_endpoint="http://localhost:4317",
        telemetry_otlp_metrics_endpoint="http://localhost:4318",
        telemetry_otlp_headers={"authorization": "token"},
        telemetry_otlp_insecure=True,
        telemetry_otlp_timeout=5.5,
    )

    expect(result["success"] is True, "Flow should surface success from pipeline summary.")
    expect(len(captured) == 1, "Pipeline should execute exactly once.")

    options = captured[0]
    config = options.config

    expect(
        config.pipeline.backfill is True,
        "Backfill flag should propagate to pipeline config.",
    )
    expect(
        config.pipeline.incremental is True,
        "Incremental flag should propagate to pipeline config.",
    )
    expected_since = datetime.fromisoformat(since_iso)
    expect(
        config.pipeline.since == expected_since,
        "Since value should be parsed into a datetime instance.",
    )
    expect(config.telemetry.enabled is True, "Telemetry enabled flag should propagate.")
    expect(
        config.telemetry.exporters == ("console",),
        "Telemetry exporters should include the console exporter.",
    )
    expect(
        config.telemetry.service_name == "hotpass-prefect",
        "Telemetry service name should propagate to config.",
    )
    expect(
        config.telemetry.environment == "staging",
        "Telemetry environment should propagate to config.",
    )
    expect(
        config.telemetry.resource_attributes["deployment"] == "prefect",
        "Telemetry resource attributes should include deployment marker.",
    )
    expect(
        config.telemetry.otlp_endpoint == "http://localhost:4317",
        "OTLP endpoint should propagate to telemetry settings.",
    )
    expect(
        config.telemetry.otlp_metrics_endpoint == "http://localhost:4318",
        "OTLP metrics endpoint should propagate to telemetry settings.",
    )
    expect(
        config.telemetry.otlp_headers["authorization"] == "token",
        "Telemetry headers should propagate to telemetry settings.",
    )
    expect(
        config.telemetry.otlp_insecure is True,
        "Telemetry insecure flag should propagate to telemetry settings.",
    )
    expect(
        config.telemetry.otlp_timeout == 5.5,
        "Telemetry timeout should propagate to telemetry settings.",
    )
    telemetry_context = options.telemetry_context
    expect(
        telemetry_context is not None,
        "Telemetry context should be populated when telemetry is enabled.",
    )
    context = cast(dict[str, Any], telemetry_context)
    expect(
        context["hotpass.flow"] == "hotpass-refinement-pipeline",
        "Telemetry context should include flow identifier.",
    )
    expect(
        context["hotpass.command"] == "prefect.refinement_flow",
        "Telemetry context should include command identifier.",
    )


def _write_archive(
    archive_root: Path, run_date: date, version: str, payload: str = "sample"
) -> Path:
    archive_root.mkdir(parents=True, exist_ok=True)
    archive_path = archive_root / f"hotpass-inputs-{run_date:%Y%m%d}-v{version}.zip"
    staging_dir = archive_root / f"staging-{run_date:%Y%m%d}-{version}"
    staging_dir.mkdir(exist_ok=True)
    source_file = staging_dir / "input.csv"
    source_file.write_text(payload)
    with zipfile.ZipFile(archive_path, "w") as zip_handle:
        zip_handle.write(source_file, arcname="input.csv")
    return archive_path


def test_backfill_flow_processes_multiple_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_root = tmp_path / "archives"
    restore_root = tmp_path / "rehydrated"
    base_config = HotpassConfig().merge(
        {
            "pipeline": {
                "output_path": tmp_path / "outputs" / "refined.xlsx",
                "archive": False,
            }
        }
    )
    runs = [
        {"run_date": "2024-01-01", "version": "v1"},
        {"run_date": "2024-01-02", "version": "v2"},
    ]
    for run in runs:
        _write_archive(
            archive_root,
            date.fromisoformat(run["run_date"]),
            run["version"],
            payload=run["version"],
        )

    captured_configs: list[HotpassConfig] = []

    def fake_run_pipeline_once(
        options: PipelineRunOptionsType,
    ) -> PipelineRunSummaryType:
        captured_configs.append(options.config)
        pipeline_output = options.config.pipeline.output_path
        return cast(
            PipelineRunSummaryType,
            PipelineRunSummary(
                success=True,
                total_records=5,
                elapsed_seconds=1.5,
                output_path=pipeline_output,
                quality_report={"rows": 5},
            ),
        )

    monkeypatch.setattr(orchestration, "run_pipeline_once", fake_run_pipeline_once)

    result = backfill_pipeline_flow(
        runs=runs,
        archive_root=str(archive_root),
        restore_root=str(restore_root),
        base_config=base_config.model_dump(mode="python"),
    )

    expect(len(captured_configs) == 2, "Flow should orchestrate two scheduled runs")
    expect(result["metrics"]["total_runs"] == 2, "Metrics should record two runs")
    expect(
        result["metrics"]["successful_runs"] == 2,
        "Metrics should record both runs as successful",
    )
    expect(
        result["metrics"]["total_records"] == 10,
        "Total records should aggregate across runs",
    )

    for run, config in zip(runs, captured_configs, strict=True):
        extracted = restore_root / f"{run['run_date']}--{run['version']}"
        expect(
            config.pipeline.input_dir == extracted,
            "Run configuration should point to extracted archive path",
        )
        expect(
            (extracted / "input.csv").read_text() == run["version"],
            "Extracted payload should match archived version identifier",
        )
        expected_output = (
            restore_root / "outputs" / f"refined-{run['run_date']}-{run['version']}.xlsx"
        )
        expect(
            config.pipeline.output_path == expected_output,
            "Output path should include run-specific suffix",
        )

    expect(
        all(run_entry["success"] for run_entry in result["runs"]),
        "All runs should succeed",
    )


def test_backfill_flow_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    restore_root = tmp_path / "rehydrated"
    run_info = {"run_date": "2024-02-01", "version": "baseline"}
    _write_archive(
        archive_root,
        date.fromisoformat(run_info["run_date"]),
        run_info["version"],
        payload="initial",
    )

    call_paths: list[Path] = []

    def fake_run_pipeline_once(
        options: PipelineRunOptionsType,
    ) -> PipelineRunSummaryType:
        call_paths.append(options.config.pipeline.input_dir)
        return cast(
            PipelineRunSummaryType,
            PipelineRunSummary(
                success=True,
                total_records=3,
                elapsed_seconds=1.0,
                output_path=options.config.pipeline.output_path,
                quality_report={"rows": 3},
            ),
        )

    monkeypatch.setattr(orchestration, "run_pipeline_once", fake_run_pipeline_once)

    backfill_pipeline_flow(
        runs=[run_info],
        archive_root=str(archive_root),
        restore_root=str(restore_root),
        base_config=HotpassConfig().model_dump(mode="python"),
    )

    extracted = call_paths[0]
    marker = extracted / "leftover.txt"
    marker.write_text("stale")

    # Update archive payload to ensure rehydration refreshes content
    _write_archive(
        archive_root,
        date.fromisoformat(run_info["run_date"]),
        run_info["version"],
        payload="fresh",
    )

    backfill_pipeline_flow(
        runs=[run_info],
        archive_root=str(archive_root),
        restore_root=str(restore_root),
        base_config=HotpassConfig().model_dump(mode="python"),
    )

    expect(marker.exists() is False, "Marker file should be removed after backfill")
    expect(
        (extracted / "input.csv").read_text() == "fresh",
        "Restored dataset should reflect latest archive payload",
    )
    expect(len(call_paths) == 2, "Backfill should execute the pipeline twice")


def test_backfill_flow_missing_archive(tmp_path: Path) -> None:
    restore_root = tmp_path / "rehydrated"

    with pytest.raises(PipelineOrchestrationError):
        backfill_pipeline_flow(
            runs=[{"run_date": "2024-03-01", "version": "unknown"}],
            archive_root=str(tmp_path / "archives"),
            restore_root=str(restore_root),
        )


def test_backfill_flow_falls_back_when_concurrency_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_root = tmp_path / "archives"
    restore_root = tmp_path / "rehydrated"
    run_info = {"run_date": "2024-04-01", "version": "replay"}
    _write_archive(archive_root, date.fromisoformat(run_info["run_date"]), run_info["version"])

    calls: list[Path] = []

    def fake_run_pipeline_once(
        options: PipelineRunOptionsType,
    ) -> PipelineRunSummaryType:
        calls.append(options.config.pipeline.input_dir)
        return cast(
            PipelineRunSummaryType,
            PipelineRunSummary(
                success=True,
                total_records=2,
                elapsed_seconds=0.5,
                output_path=options.config.pipeline.output_path,
                quality_report={"rows": 2},
            ),
        )

    class _RaiseOnEnter:
        def __init__(self, exc: Exception) -> None:
            self.exc = exc

        async def __aenter__(self) -> None:
            raise self.exc

        async def __aexit__(self, *_exc: object) -> None:
            return None

    def _failing_concurrency(*_args: object, **_kwargs: object) -> _RaiseOnEnter:
        return _RaiseOnEnter(RuntimeError("test concurrency failure"))

    monkeypatch.setattr(orchestration, "run_pipeline_once", fake_run_pipeline_once)
    monkeypatch.setattr(orchestration, "prefect_concurrency", _failing_concurrency, raising=False)

    result = backfill_pipeline_flow(
        runs=[run_info],
        archive_root=str(archive_root),
        restore_root=str(restore_root),
        concurrency_limit=1,
    )

    expect(len(calls) == 1, "Backfill flow should invoke the pipeline exactly once")
    expect(
        result["metrics"]["total_runs"] == 1,
        "Metrics should reflect a single run when concurrency fails",
    )


@anyio_mark("asyncio")
async def test_run_with_prefect_concurrency_acquires_and_releases(
    tmp_path: Path,
) -> None:
    events: list[tuple[str, ...]] = []

    summary: PipelineRunSummaryType = cast(
        PipelineRunSummaryType,
        PipelineRunSummary(
            success=True,
            total_records=5,
            elapsed_seconds=0.25,
            output_path=tmp_path / "refined.xlsx",
            quality_report={"rows": 5},
        ),
    )

    @asynccontextmanager
    async def _tracking_concurrency(key: str, occupy: int):
        events.append(("enter", key, str(occupy)))
        try:
            yield
        finally:
            events.append(("exit", key, str(occupy)))

    async def _run_sync(
        func: Callable[[], PipelineRunSummaryType],
        *_args: object,
        **_kwargs: object,
    ) -> PipelineRunSummaryType:
        events.append(("run_sync",))
        return func()

    def _callback() -> PipelineRunSummaryType:
        events.append(("callback",))
        return summary

    result = await _run_with_prefect_concurrency(
        _tracking_concurrency,
        "hotpass/tests",
        2,
        _callback,
        run_sync=_run_sync,
    )

    expect(result is summary, "Expected concurrency helper to return callback result")
    expect(("callback",) in events, "Callback should execute within the concurrency guard")
    expect(
        ("enter", "hotpass/tests", "2") in events,
        "Concurrency context should be entered",
    )
    expect(("exit", "hotpass/tests", "2") in events, "Concurrency context should be exited")


@anyio_mark("asyncio")
async def test_run_with_prefect_concurrency_falls_back_on_error(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    summary: PipelineRunSummaryType = cast(
        PipelineRunSummaryType,
        PipelineRunSummary(
            success=True,
            total_records=1,
            elapsed_seconds=0.1,
            output_path=tmp_path / "fallback.xlsx",
            quality_report={"rows": 1},
        ),
    )

    class _RaiseOnEnter:
        def __init__(self, exc: Exception) -> None:
            self.exc = exc

        async def __aenter__(self) -> None:
            raise self.exc

        async def __aexit__(self, *_exc: object) -> None:
            return None

    def _failing_concurrency(*_args: object, **_kwargs: object) -> _RaiseOnEnter:
        return _RaiseOnEnter(RuntimeError("boom"))

    async def _run_sync(
        func: Callable[[], PipelineRunSummaryType],
        *_args: object,
        **_kwargs: object,
    ) -> PipelineRunSummaryType:
        events.append("run_sync")
        return func()

    def _callback() -> PipelineRunSummaryType:
        events.append("callback")
        return summary

    result = await _run_with_prefect_concurrency(
        _failing_concurrency,
        "hotpass/tests",
        1,
        _callback,
        run_sync=_run_sync,
    )

    expect(result is summary, "Concurrency fallback should return callback result")
    expect(
        events.count("run_sync") == 1,
        "Thread runner should execute once when falling back",
    )
    expect(
        "callback" in events,
        "Callback must still execute when concurrency acquisition fails",
    )


@anyio_mark("asyncio")
async def test_run_with_prefect_concurrency_releases_on_callback_error() -> None:
    """Concurrency guard should release slots when the callback raises."""

    events: list[tuple[str, ...]] = []

    @asynccontextmanager
    async def _tracking_concurrency(key: str, occupy: int):
        events.append(("enter", key, str(occupy)))
        try:
            yield
        finally:
            events.append(("exit", key, str(occupy)))

    async def _run_sync(
        func: Callable[[], PipelineRunSummaryType],
        *_args: object,
        **_kwargs: object,
    ) -> PipelineRunSummaryType:
        events.append(("run_sync",))
        return func()

    def _callback() -> PipelineRunSummaryType:
        events.append(("callback",))
        raise RuntimeError("callback failure")

    with pytest.raises(RuntimeError):
        await _run_with_prefect_concurrency(
            _tracking_concurrency,
            "hotpass/tests",
            1,
            _callback,
            run_sync=_run_sync,
        )

    expect(
        ("run_sync",) in events,
        "Thread runner should still be invoked when callback fails",
    )
    expect(("callback",) in events, "Callback should run even when it raises")
    expect(
        ("exit", "hotpass/tests", "1") in events,
        "Concurrency context should release resources after callback failure",
    )


@anyio_mark("asyncio")
async def test_run_with_prefect_concurrency_releases_on_run_sync_error() -> None:
    """Concurrency guard should release slots when the thread runner fails."""

    events: list[tuple[str, ...]] = []

    @asynccontextmanager
    async def _tracking_concurrency(key: str, occupy: int):
        events.append(("enter", key, str(occupy)))
        try:
            yield
        finally:
            events.append(("exit", key, str(occupy)))

    async def _run_sync(
        func: Callable[[], PipelineRunSummaryType],
        *_args: object,
        **_kwargs: object,
    ) -> PipelineRunSummaryType:
        events.append(("run_sync",))
        raise RuntimeError("run_sync failure")

    def _callback() -> PipelineRunSummaryType:
        events.append(("callback",))
        return cast(
            PipelineRunSummaryType,
            PipelineRunSummary(
                success=True,
                total_records=0,
                elapsed_seconds=0.0,
                output_path=Path("/tmp/unused.xlsx"),
                quality_report={},
            ),
        )

    with pytest.raises(RuntimeError):
        await _run_with_prefect_concurrency(
            _tracking_concurrency,
            "hotpass/tests",
            2,
            _callback,
            run_sync=_run_sync,
        )

    expect(
        ("run_sync",) in events,
        "Thread runner should be invoked before propagating errors",
    )
    expect(
        ("callback",) not in events,
        "Callback should not execute when run_sync fails early",
    )
    expect(
        ("exit", "hotpass/tests", "2") in events,
        "Concurrency context should exit after run_sync failure",
    )


def test_execute_with_concurrency_uses_async_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[str, ...]] = []

    summary: PipelineRunSummaryType = cast(
        PipelineRunSummaryType,
        PipelineRunSummary(
            success=True,
            total_records=4,
            elapsed_seconds=0.4,
            output_path=tmp_path / "concurrency.xlsx",
            quality_report={"rows": 4},
        ),
    )

    @asynccontextmanager
    async def _tracking_concurrency(key: str, occupy: int):
        events.append(("enter", key, str(occupy)))
        try:
            yield
        finally:
            events.append(("exit", key, str(occupy)))

    async def _run_sync(
        func: Callable[[], PipelineRunSummaryType],
        *_args: object,
        **_kwargs: object,
    ) -> PipelineRunSummaryType:
        events.append(("run_sync",))
        return func()

    def _callback() -> PipelineRunSummaryType:
        events.append(("callback",))
        return summary

    monkeypatch.setattr(orchestration, "prefect_concurrency", _tracking_concurrency, raising=False)
    monkeypatch.setattr(anyio.to_thread, "run_sync", _run_sync)

    result = _execute_with_concurrency("hotpass/tests", 3, _callback)

    expect(result is summary, "Execute with concurrency should return callback result")
    expect(("callback",) in events, "Callback should execute through async runner")
    expect(
        ("enter", "hotpass/tests", "3") in events,
        "Concurrency context should be entered",
    )
    expect(("exit", "hotpass/tests", "3") in events, "Concurrency context should be exited")


def test_execute_with_concurrency_returns_immediate_without_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execution should fall back to a direct callback when slots are disabled."""

    def _callback() -> PipelineRunSummaryType:
        return cast(
            PipelineRunSummaryType,
            PipelineRunSummary(
                success=True,
                total_records=2,
                elapsed_seconds=0.1,
                output_path=Path("/tmp/out.xlsx"),
                quality_report={"rows": 2},
            ),
        )

    monkeypatch.setattr(orchestration, "prefect_concurrency", None, raising=False)

    result = _execute_with_concurrency("hotpass/tests", 0, _callback)

    expect(
        result.total_records == 2,
        "Callback result should be returned immediately when slots disabled",
    )


def test_execute_with_concurrency_falls_back_when_anyio_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execution should fall back to synchronous run when anyio.run raises."""

    events: list[str] = []

    @asynccontextmanager
    async def _tracking_concurrency(*_args: object, **_kwargs: object):
        yield

    def _callback() -> PipelineRunSummaryType:
        events.append("callback")
        return cast(
            PipelineRunSummaryType,
            PipelineRunSummary(
                success=True,
                total_records=1,
                elapsed_seconds=0.1,
                output_path=Path("/tmp/out.xlsx"),
                quality_report={"rows": 1},
            ),
        )

    def _failing_run(*_args: object, **_kwargs: object) -> PipelineRunSummaryType:
        raise RuntimeError("anyio unavailable")

    monkeypatch.setattr(orchestration, "prefect_concurrency", _tracking_concurrency, raising=False)
    monkeypatch.setattr(anyio, "run", _failing_run)

    result = _execute_with_concurrency("hotpass/tests", 1, _callback)

    expect(
        result.total_records == 1,
        "Execution should return callback result when async path fails",
    )
    expect(
        events.count("callback") == 1,
        "Callback should execute once when falling back to sync path",
    )
