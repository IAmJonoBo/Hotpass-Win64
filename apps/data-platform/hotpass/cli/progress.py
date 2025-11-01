"""Shared logging and progress utilities for the Hotpass CLI."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Mapping
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from types import TracebackType
from typing import Any, cast

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

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
    QualityReport,
)

DEFAULT_SENSITIVE_FIELD_TOKENS: tuple[str, ...] = (
    "email",
    "phone",
    "contact",
    "cell",
    "mobile",
    "whatsapp",
)
"""Default tokens used to identify sensitive fields for log redaction."""


REDACTED_PLACEHOLDER = "***redacted***"
"""Placeholder written to the logs when sensitive payloads are masked."""


_PERFORMANCE_FIELDS: list[tuple[str, str]] = [
    ("Load seconds", "load_seconds"),
    ("Aggregation seconds", "aggregation_seconds"),
    ("Expectations seconds", "expectations_seconds"),
    ("Write seconds", "write_seconds"),
    ("Total seconds", "total_seconds"),
    ("Rows per second", "rows_per_second"),
    ("Load rows per second", "load_rows_per_second"),
]


class StructuredLogger:
    """Emit structured telemetry for CLI commands."""

    def __init__(self, log_format: str, sensitive_tokens: Iterable[str] | None = None) -> None:
        self.log_format = log_format
        tokens = (
            sensitive_tokens if sensitive_tokens is not None else DEFAULT_SENSITIVE_FIELD_TOKENS
        )
        self.console: Console | None = Console() if log_format == "rich" else None
        self._sensitive_tokens = tuple(sorted({token.lower() for token in tokens}))

    def _emit_json(self, event: str, data: dict[str, Any]) -> None:
        serialisable = {
            "event": event,
            "data": _convert_paths(self._mask_payload(data)),
        }
        print(json.dumps(serialisable))

    def _get_console(self) -> Console:
        if self.console is None:  # pragma: no cover - defensive safeguard
            msg = "Rich console not initialised"
            raise RuntimeError(msg)
        return self.console

    def _mask_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        return {key: self._redact_value(key, value) for key, value in data.items()}

    def _redact_value(self, key: str, value: Any) -> Any:
        if self._should_redact(key):
            if isinstance(value, list):
                return [REDACTED_PLACEHOLDER for _ in value]
            if isinstance(value, dict):
                return {nested_key: REDACTED_PLACEHOLDER for nested_key in value}
            return REDACTED_PLACEHOLDER
        if isinstance(value, dict):
            return {
                nested_key: self._redact_value(nested_key, nested_value)
                for nested_key, nested_value in value.items()
            }
        if isinstance(value, list):
            return [self._redact_value(key, item) for item in value]
        return value

    def _should_redact(self, key: str) -> bool:
        lowered = key.lower()
        return any(token in lowered for token in self._sensitive_tokens)

    def log_summary(self, report: QualityReport) -> None:
        if self.log_format == "json":
            self._emit_json("pipeline.summary", report.to_dict())
            return

        console = self._get_console()
        from rich.table import Table  # local import to avoid unconditional dependency in JSON mode

        table = Table(
            title="Hotpass Quality Report",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Total records", str(report.total_records))
        table.add_row("Invalid records", str(report.invalid_records))
        table.add_row("Expectations passed", "Yes" if report.expectations_passed else "No")
        mean_score = f"{report.data_quality_distribution.get('mean', 0.0):.2f}"
        min_score = f"{report.data_quality_distribution.get('min', 0.0):.2f}"
        max_score = f"{report.data_quality_distribution.get('max', 0.0):.2f}"
        table.add_row("Mean quality score", mean_score)
        table.add_row("Min quality score", min_score)
        table.add_row("Max quality score", max_score)
        console.print(table)

        if report.source_breakdown:
            breakdown = Table(title="Source Breakdown", show_header=True)
            breakdown.add_column("Source", style="cyan")
            breakdown.add_column("Records", justify="right")
            for source, count in sorted(report.source_breakdown.items()):
                breakdown.add_row(source, str(count))
            console.print(breakdown)

        if report.schema_validation_errors:
            console.print("[bold yellow]Schema Validation Errors:[/bold yellow]")
            for error in report.schema_validation_errors:
                console.print(f"  • {error}")
        if report.expectation_failures:
            console.print("[bold yellow]Expectation Failures:[/bold yellow]")
            for failure in report.expectation_failures:
                console.print(f"  • {failure}")

        if report.performance_metrics:
            metrics_table = Table(title="Performance Metrics", show_header=True)
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", justify="right")
            for label, key in _PERFORMANCE_FIELDS:
                value = report.performance_metrics.get(key)
                if value is None:
                    continue
                metrics_table.add_row(label, _format_metric_value(value))
            console.print(metrics_table)

            source_metrics = report.performance_metrics.get("source_load_seconds", {})
            if source_metrics:
                source_table = Table(title="Source Load Durations", show_header=True)
                source_table.add_column("Loader", style="cyan")
                source_table.add_column("Seconds", justify="right")
                for loader, seconds in sorted(source_metrics.items()):
                    source_table.add_row(loader, _format_metric_value(seconds))
                console.print(source_table)
        else:
            console.print("[italic]No performance metrics recorded.[/italic]")

    def log_archive(self, archive_path: Path) -> None:
        if self.log_format == "json":
            self._emit_json("archive.created", {"path": archive_path})
            return

        self._get_console().print(f"[green]Archive created:[/green] {archive_path}")

    def log_report_write(self, report_path: Path, report_format: str | None) -> None:
        payload = {"path": report_path, "format": report_format}
        if self.log_format == "json":
            self._emit_json("report.write", payload)
            return

        label = report_format or "auto"
        self._get_console().print(f"[green]Quality report written ({label}):[/green] {report_path}")

    def log_party_store(self, output_path: Path) -> None:
        if self.log_format == "json":
            self._emit_json("party_store.write", {"path": output_path})
            return

        self._get_console().print(f"[green]Party store exported:[/green] {output_path}")

    def log_intent_digest(self, output_path: Path, record_count: int) -> None:
        payload = {"path": output_path, "records": record_count}
        if self.log_format == "json":
            self._emit_json("intent.digest", payload)
            return

        self._get_console().print(
            f"[green]Intent digest written ({record_count} records):[/green] {output_path}"
        )

    def log_error(self, message: str) -> None:
        if self.log_format == "json":
            self._emit_json("error", {"message": message})
            return

        self._get_console().print(f"[bold red]Error:[/bold red] {message}")

    def log_validation_artifact(self, artifact_type: str, artifact_path: Path) -> None:
        """Log the creation of a validation artifact like Data Docs."""
        if self.log_format == "json":
            self._emit_json(
                "validation.artifact",
                {"artifact_type": artifact_type, "artifact_path": str(artifact_path)},
            )
            return

        self._get_console().print(
            f"[green]Validation artifact ({artifact_type}):[/green] {artifact_path}"
        )

    def log_event(self, event: str, data: Mapping[str, Any]) -> None:
        payload = dict(data)
        if self.log_format == "json":
            self._emit_json(event, payload)
            return

        serialised = json.dumps(_convert_paths(payload), indent=2)
        self._get_console().print(f"[cyan]{event}[/cyan] {serialised}")


class PipelineProgress:
    """Rich progress renderer that mirrors pipeline lifecycle events."""

    def __init__(
        self,
        console: Console,
        *,
        progress_factory: Callable[..., Any] = Progress,
        throttle_seconds: float = 0.05,
    ) -> None:
        self._progress = progress_factory(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        )
        self._tasks: dict[str, TaskID] = {}
        self._aggregate_total = 0
        self._aggregate_progress_total = 1
        self._aggregate_last_completed = 0
        self._aggregate_last_update_time = 0.0
        self._aggregate_throttled_updates = 0
        self._throttle_seconds = max(0.0, throttle_seconds)

    def __enter__(self) -> PipelineProgress:
        self._progress.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - delegated cleanup
        self._progress.__exit__(exc_type, exc, tb)

    def handle_event(self, event: str, payload: dict[str, Any]) -> None:
        if event == PIPELINE_EVENT_START:
            self._progress.log("[bold cyan]Starting pipeline[/bold cyan]")
        elif event == PIPELINE_EVENT_LOAD_STARTED:
            self._start_task("load", "Loading source files")
        elif event == PIPELINE_EVENT_LOAD_COMPLETED:
            rows = int(payload.get("total_rows", 0))
            sources = payload.get("sources", []) or []
            message = f"[green]Loaded {rows} rows from {len(sources)} source(s)[/green]"
            self._complete_task("load", message)
        elif event == PIPELINE_EVENT_AGGREGATE_STARTED:
            total = int(payload.get("total", 0))
            self._aggregate_total = total if total > 0 else 0
            self._aggregate_progress_total = self._aggregate_total or 1
            self._aggregate_last_completed = 0
            self._aggregate_last_update_time = 0.0
            self._aggregate_throttled_updates = 0
            self._start_task(
                "aggregate",
                "Aggregating organisations",
                total=self._aggregate_progress_total,
            )
        elif event == PIPELINE_EVENT_AGGREGATE_PROGRESS:
            task_id = self._tasks.get("aggregate")
            if task_id is not None:
                if self._aggregate_total <= 0:
                    self._aggregate_last_completed = self._aggregate_progress_total
                    self._aggregate_last_update_time = time.perf_counter()
                    self._progress.update(task_id, completed=self._aggregate_progress_total)
                else:
                    completed = int(payload.get("completed", 0))
                    completed = max(0, min(completed, self._aggregate_progress_total))
                    now = time.perf_counter()
                    final_update = completed >= self._aggregate_progress_total
                    if not final_update and completed == self._aggregate_last_completed:
                        return
                    if (
                        not final_update
                        and self._throttle_seconds > 0.0
                        and now - self._aggregate_last_update_time < self._throttle_seconds
                    ):
                        self._aggregate_throttled_updates += 1
                        return
                    self._aggregate_last_update_time = now
                    self._aggregate_last_completed = completed
                    self._progress.update(task_id, completed=completed)
        elif event == PIPELINE_EVENT_AGGREGATE_COMPLETED:
            aggregated = int(payload.get("aggregated_records", 0))
            conflicts = int(payload.get("conflicts", 0))
            message = f"[green]Aggregated {aggregated} record(s)[/green]"
            if conflicts:
                message += f" with [yellow]{conflicts}[/yellow] conflict(s) resolved"
            self._complete_task("aggregate", message)
            self._emit_throttle_summary()
        elif event == PIPELINE_EVENT_SCHEMA_STARTED:
            self._start_task("schema", "Validating schema")
        elif event == PIPELINE_EVENT_SCHEMA_COMPLETED:
            self._complete_task("schema", "[green]Schema validation completed[/green]")
        elif event == PIPELINE_EVENT_EXPECTATIONS_STARTED:
            self._start_task("expectations", "Running expectations")
        elif event == PIPELINE_EVENT_EXPECTATIONS_COMPLETED:
            passed = payload.get("passed", True)
            message = (
                "[green]Expectations passed[/green]"
                if passed
                else "[yellow]Expectations completed with warnings[/yellow]"
            )
            self._complete_task("expectations", message)
        elif event == PIPELINE_EVENT_WRITE_STARTED:
            self._start_task("write", "Writing refined workbook")
        elif event == PIPELINE_EVENT_WRITE_COMPLETED:
            output_path = payload.get("output_path")
            message = "[green]Refined workbook written[/green]"
            if output_path:
                message += f" to {output_path}"
            self._complete_task("write", message)
        elif event == PIPELINE_EVENT_COMPLETED:
            summary = payload.get("summary", "Pipeline completed")
            self._progress.log(f"[bold green]✓[/bold green] {summary}")

    def _start_task(self, name: str, description: str, *, total: int = 1) -> None:
        if name in self._tasks:
            return
        task_id = self._progress.add_task(description, total=total or 1)
        self._tasks[name] = task_id

    def _complete_task(self, name: str, message: str | None = None) -> None:
        task_id = self._tasks.pop(name, None)
        if task_id is not None:
            task = next((task for task in self._progress.tasks if task.id == task_id), None)
            total = task.total if task and task.total else 1
            self._progress.update(task_id, total=total, completed=total)
        if message:
            self._progress.log(message)

    def _emit_throttle_summary(self) -> None:
        if self._aggregate_throttled_updates:
            suppressed = self._aggregate_throttled_updates
            self._aggregate_throttled_updates = 0
            self._progress.log(f"[dim]Suppressed {suppressed} aggregate progress update(s)[/dim]")


def render_progress(
    console: Console | None,
) -> AbstractContextManager[PipelineProgress | None]:
    """Return a context manager for pipeline progress rendering."""

    if console is None:
        return nullcontext(None)
    return cast(AbstractContextManager[PipelineProgress | None], PipelineProgress(console))


def _convert_paths(data: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, Path):
            converted[key] = str(value)
        else:
            converted[key] = value
    return converted


def _format_metric_value(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{float(value):.4f}"
    return str(value)


__all__ = [
    "DEFAULT_SENSITIVE_FIELD_TOKENS",
    "REDACTED_PLACEHOLDER",
    "StructuredLogger",
    "PipelineProgress",
    "render_progress",
]
