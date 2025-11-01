"""Backfill orchestration command for the Hotpass CLI."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from hotpass.orchestration import backfill_pipeline_flow

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..progress import StructuredLogger
from .run import RunOptions
from .run import _resolve_options as resolve_run_options


@dataclass(slots=True)
class BackfillOptions:
    """Resolved settings required to execute a backfill run."""

    run: RunOptions
    runs: list[dict[str, str]]
    archive_root: Path
    restore_root: Path
    archive_pattern: str
    parameters: Mapping[str, Any]
    concurrency_limit: int
    concurrency_key: str


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "backfill",
        help="Replay archived inputs through the refinement pipeline",
        description=(
            "Extract archived input bundles and orchestrate Prefect backfill runs over "
            "specified date/version windows."
        ),
        parents=[shared.base, shared.pipeline, shared.reporting, shared.excel],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--start-date", type=_parse_date, help="Inclusive ISO start date")
    parser.add_argument("--end-date", type=_parse_date, help="Inclusive ISO end date")
    parser.add_argument(
        "--version",
        dest="versions",
        action="append",
        help="Version identifier to replay (repeat for multiple versions)",
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        help="Directory containing archived input bundles",
    )
    parser.add_argument(
        "--restore-root",
        type=Path,
        help="Directory used to rehydrate archives before execution",
    )
    parser.add_argument(
        "--archive-pattern",
        help=(
            "Format string used to locate archives relative to the archive root. "
            "Supports Python strftime-style placeholders."
        ),
    )
    parser.add_argument(
        "--concurrency-limit",
        type=int,
        help="Maximum concurrent backfill runs to execute",
    )
    parser.add_argument(
        "--concurrency-key",
        help="Prefect concurrency key shared across backfill runs",
    )
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="backfill",
        help="Replay archived inputs through Prefect",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    options = _resolve_backfill_options(namespace, profile)
    logger = StructuredLogger(options.run.log_format, options.run.sensitive_fields)
    console = logger.console if options.run.log_format == "rich" else None

    if not options.runs:
        logger.log_error(
            "No backfill windows available. Provide --start-date/--end-date or "
            "configure orchestrator.backfill.windows."
        )
        return 1

    if console:
        console.print("[bold cyan]Hotpass Backfill[/bold cyan]")
        console.print(f"[dim]Archive root:[/dim] {options.archive_root}")
        console.print(f"[dim]Restore root:[/dim] {options.restore_root}")
        console.print(f"[dim]Run count:[/dim] {len(options.runs)}")
        console.print()

    options.restore_root.mkdir(parents=True, exist_ok=True)

    base_config_payload = options.run.canonical_config.model_dump(mode="python")
    try:
        payload = backfill_pipeline_flow(
            runs=options.runs,
            archive_root=str(options.archive_root),
            restore_root=str(options.restore_root),
            archive_pattern=options.archive_pattern,
            base_config=base_config_payload,
            parameters=dict(options.parameters),
            concurrency_limit=options.concurrency_limit,
            concurrency_key=options.concurrency_key,
        )
    except Exception as exc:  # pragma: no cover - defensive guard for unexpected Prefect errors
        logger.log_error(f"Backfill failed: {exc}")
        return 1

    metrics = payload.get("metrics", {})
    logger.log_event("backfill.summary", metrics)
    for run_result in payload.get("runs", []):
        logger.log_event("backfill.run", run_result)

    if console:
        total = metrics.get("total_runs", len(options.runs))
        successes = metrics.get("successful_runs", 0)
        console.print(
            f"[bold green]✓[/bold green] Completed backfill runs ({successes}/{total} succeeded)."
        )
    return 0


def _resolve_backfill_options(
    namespace: argparse.Namespace, profile: CLIProfile | None
) -> BackfillOptions:
    run_options = resolve_run_options(namespace, profile)
    config = run_options.canonical_config
    backfill_config = config.orchestrator.backfill

    start_date: date | None = getattr(namespace, "start_date", None)
    end_date: date | None = getattr(namespace, "end_date", None)
    cli_versions = _normalise_versions(getattr(namespace, "versions", None))

    runs: list[dict[str, str]]
    if start_date is not None:
        effective_end = end_date or start_date
        if cli_versions is not None:
            versions = cli_versions
        elif backfill_config.windows:
            versions = backfill_config.windows[0].versions
        else:
            versions = ("latest",)
        runs = _expand_runs(start_date, effective_end, versions)
    else:
        runs = []
        if backfill_config.windows:
            for window in backfill_config.windows:
                window_versions = cli_versions or window.versions
                runs.extend(
                    _expand_runs(
                        window.start_date,
                        window.end_date or window.start_date,
                        window_versions,
                    )
                )

    archive_root = getattr(namespace, "archive_root", None) or backfill_config.archive_root
    restore_root = getattr(namespace, "restore_root", None) or backfill_config.restore_root
    archive_pattern = getattr(namespace, "archive_pattern", None) or backfill_config.archive_pattern
    concurrency_limit_raw = getattr(namespace, "concurrency_limit", None)
    concurrency_key = getattr(namespace, "concurrency_key", None) or backfill_config.concurrency_key

    if concurrency_limit_raw is None:
        concurrency_limit_raw = backfill_config.concurrency_limit

    parameters: dict[str, Any] = {}
    parameters.update(config.orchestrator.parameters)
    parameters.update(backfill_config.parameters)

    return BackfillOptions(
        run=run_options,
        runs=runs,
        archive_root=Path(archive_root),
        restore_root=Path(restore_root),
        archive_pattern=str(archive_pattern),
        parameters=parameters,
        concurrency_limit=int(concurrency_limit_raw),
        concurrency_key=str(concurrency_key),
    )


def _expand_runs(start: date, end: date, versions: Iterable[str]) -> list[dict[str, str]]:
    runs: list[dict[str, str]] = []
    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        for version in versions:
            runs.append({"run_date": iso, "version": str(version)})
        cursor += timedelta(days=1)
    return runs


def _normalise_versions(values: Iterable[str] | str | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    cleaned: list[str] = []
    for value in values:
        candidate = str(value).strip()
        if candidate and candidate not in cleaned:
            cleaned.append(candidate)
    return tuple(cleaned)


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:  # pragma: no cover - argparse surfaces message
        msg = f"Invalid date value: {raw}"
        raise argparse.ArgumentTypeError(msg) from exc


__all__ = ["register", "build"]
