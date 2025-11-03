from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from ..domain.party import PartyStore
from ..normalization import slugify
from .config import (
    SSOT_COLUMNS,
    PipelineConfig,
    PipelineResult,
    QualityReport,
)
from .events import (
    PIPELINE_EVENT_AGGREGATE_COMPLETED,
    PIPELINE_EVENT_AGGREGATE_STARTED,
    PIPELINE_EVENT_COMPLETED,
    PIPELINE_EVENT_WRITE_COMPLETED,
    PIPELINE_EVENT_WRITE_STARTED,
)

if TYPE_CHECKING:
    from ..enrichment.intent.runner import IntentRunResult


def notify_progress(config: PipelineConfig, event: str, **payload: Any) -> None:
    """Send progress updates to the configured listener."""

    listener = config.progress_listener
    if listener is not None:
        listener(event, payload)


def relay_progress(
    config: PipelineConfig,
    event: str,
    payload: Mapping[str, Any],
    mapping: Mapping[str, str],
) -> None:
    """Translate domain events to pipeline progress notifications."""

    mapped = mapping.get(event)
    if mapped is None:
        return
    notify_progress(config, mapped, **payload)


def persist_contract_notices(
    config: PipelineConfig,
    notices: list[dict[str, Any]],
    datetime_factory: Callable[[], Any],
) -> list[dict[str, Any]]:
    """Write duplicate contract records to disk and return sanitised metadata."""

    if not notices:
        return []

    timestamp = config.run_id or datetime_factory().strftime("%Y%m%dT%H%M%SZ")
    root: Path = config.dist_dir / "contract-notices" / timestamp
    root.mkdir(parents=True, exist_ok=True)

    sanitized: list[dict[str, Any]] = []
    for index, notice in enumerate(notices, start=1):
        duplicate_rows = notice.get("duplicate_rows")
        table_name = str(notice.get("table_name", f"table-{index}"))
        dataset = notice.get("source_dataset")
        primary_key = list(notice.get("primary_key") or [])
        sample_keys = list(notice.get("sample_keys") or [])
        duplicate_count = int(notice.get("duplicate_count", 0))

        artifact_path: Path | None = None
        if isinstance(duplicate_rows, pd.DataFrame) and not duplicate_rows.empty:
            slug = slugify(table_name) or f"table-{index}"
            artifact_path = root / f"{slug}-duplicates.csv"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            duplicate_rows.to_csv(artifact_path, index=False)

        sanitized.append(
            {
                "table_name": table_name,
                "source_dataset": dataset,
                "source_file": notice.get("source_file"),
                "primary_key": primary_key,
                "duplicate_count": duplicate_count,
                "sample_keys": sample_keys,
                "artifact_path": str(artifact_path) if artifact_path else None,
            }
        )

    return sanitized


def handle_empty_pipeline(
    config: PipelineConfig,
    pipeline_start: float,
    metrics: dict[str, Any],
    audit_trail: list[dict[str, Any]],
    redaction_events: list[dict[str, Any]],
    intent_result: IntentRunResult | None,
) -> PipelineResult:
    """Short-circuit the pipeline when no rows are ingested."""

    hooks = config.runtime_hooks
    perf_counter = hooks.perf_counter
    time_fn = hooks.time_fn
    refined = pd.DataFrame(columns=SSOT_COLUMNS)
    notify_progress(config, PIPELINE_EVENT_AGGREGATE_STARTED, total=0)
    notify_progress(
        config,
        PIPELINE_EVENT_AGGREGATE_COMPLETED,
        total=0,
        aggregated_records=0,
        conflicts=0,
    )
    notify_progress(config, PIPELINE_EVENT_WRITE_STARTED, path=str(config.output_path))

    write_start = perf_counter()
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    refined.to_excel(config.output_path, index=False)
    metrics.update(
        {
            "write_seconds": perf_counter() - write_start,
            "total_seconds": perf_counter() - pipeline_start,
            "rows_per_second": 0.0,
        }
    )
    notify_progress(
        config,
        PIPELINE_EVENT_WRITE_COMPLETED,
        path=str(config.output_path),
        write_seconds=metrics["write_seconds"],
    )

    recommendations = ["No data loaded. Check input directory and source files."]
    if config.enable_audit_trail:
        audit_trail.append(
            {
                "timestamp": time_fn(),
                "event": "pipeline_complete",
                "details": {
                    "total_records": 0,
                    "invalid_records": 0,
                    "duration_seconds": metrics.get("total_seconds", 0.0),
                },
            }
        )
    report = QualityReport(
        total_records=0,
        invalid_records=0,
        schema_validation_errors=[],
        expectations_passed=True,
        expectation_failures=[],
        source_breakdown={},
        data_quality_distribution={"mean": 0.0, "min": 0.0, "max": 0.0},
        performance_metrics=dict(metrics),
        recommendations=recommendations,
        audit_trail=audit_trail if config.enable_audit_trail else [],
        conflict_resolutions=[],
    )

    notify_progress(
        config,
        PIPELINE_EVENT_COMPLETED,
        total_records=0,
        invalid_records=0,
        duration=metrics["total_seconds"],
    )

    intent_signals = intent_result.signals if intent_result is not None else None
    intent_digest = intent_result.digest if intent_result is not None else None

    return PipelineResult(
        refined=refined,
        quality_report=report,
        performance_metrics=dict(metrics),
        party_store=PartyStore(),
        pii_redaction_events=redaction_events,
        intent_signals=intent_signals,
        intent_digest=intent_digest,
        daily_list=None,
    )
