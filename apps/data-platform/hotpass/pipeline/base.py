from __future__ import annotations

import logging
import random
from dataclasses import asdict
from typing import Any

import numpy as np

from ..imports.preprocess import apply_import_preprocessing
from ..pipeline_reporting import generate_recommendations
from .aggregation import aggregate_records
from .config import (
    PipelineConfig,
    PipelineResult,
    QualityReport,
    initialise_config,
)
from .enrichment import collect_intent_signals
from .events import (
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
)
from .export import publish_outputs
from .helpers import (
    handle_empty_pipeline,
    notify_progress,
    persist_contract_notices,
    relay_progress,
)
from .ingestion import apply_redaction, ingest_sources
from .validation import validate_dataset

logger = logging.getLogger(__name__)

__all__ = ["PipelineConfig", "PipelineResult", "execute_pipeline"]


def execute_pipeline(config: PipelineConfig) -> PipelineResult:
    config = initialise_config(config)
    hooks = config.runtime_hooks
    perf_counter = hooks.perf_counter
    time_fn = hooks.time_fn

    if config.random_seed is not None:
        random.seed(config.random_seed)
        np.random.seed(config.random_seed)

    pipeline_start = perf_counter()

    audit_trail: list[dict[str, Any]] = []
    redaction_events: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {
        "load_seconds": 0.0,
        "aggregation_seconds": 0.0,
        "expectations_seconds": 0.0,
        "write_seconds": 0.0,
        "total_seconds": 0.0,
        "rows_per_second": 0.0,
        "load_rows_per_second": 0.0,
        "source_load_seconds": {},
    }
    profile_name = config.industry_profile.name if config.industry_profile else "default"
    if config.preloaded_agent_warnings:
        metrics["agent_warnings"] = list(config.preloaded_agent_warnings)

    notify_progress(
        config,
        PIPELINE_EVENT_START,
        input_dir=str(config.input_dir),
        output_path=str(config.output_path),
    )

    if config.enable_audit_trail:
        audit_trail.append(
            {
                "timestamp": time_fn(),
                "event": "pipeline_start",
                "details": {
                    "input_dir": str(config.input_dir),
                    "output_path": str(config.output_path),
                    "profile": profile_name,
                },
            }
        )

    logger.info(
        "Starting pipeline execution",
        extra={
            "profile": profile_name,
            "input_dir": str(config.input_dir),
        },
    )

    notify_progress(config, PIPELINE_EVENT_LOAD_STARTED)
    ingest_start = perf_counter()
    combined, source_timings, contract_notices = ingest_sources(config)
    metrics["source_load_seconds"] = dict(source_timings)
    load_seconds = perf_counter() - ingest_start
    metrics["load_seconds"] = load_seconds
    if load_seconds > 0 and not combined.empty:
        metrics["load_rows_per_second"] = len(combined) / load_seconds

    if not combined.empty:
        combined, preprocess_issues = apply_import_preprocessing(config, combined)
        if preprocess_issues:
            metrics["import_preprocess_issues"] = [asdict(issue) for issue in preprocess_issues]
            if config.enable_audit_trail:
                audit_trail.append(
                    {
                        "timestamp": time_fn(),
                        "event": "import_preprocess",
                        "details": {
                            "issue_count": len(preprocess_issues),
                            "issues": [asdict(issue) for issue in preprocess_issues],
                        },
                    }
                )

    if config.pii_redaction.enabled:
        combined, initial_redactions = apply_redaction(config, combined)
        if initial_redactions:
            redaction_events.extend(initial_redactions)
            if config.enable_audit_trail:
                audit_trail.append(
                    {
                        "timestamp": time_fn(),
                        "event": "pii_redacted",
                        "details": {
                            "columns": sorted({event["column"] for event in initial_redactions}),
                            "redacted_cells": len(initial_redactions),
                            "operator": config.pii_redaction.operator,
                        },
                    }
                )

    notify_progress(
        config,
        PIPELINE_EVENT_LOAD_COMPLETED,
        total_rows=len(combined),
        sources=list(source_timings.keys()),
        load_seconds=load_seconds,
    )

    if config.enable_audit_trail:
        audit_trail.append(
            {
                "timestamp": time_fn(),
                "event": "sources_loaded",
                "details": {
                    "total_rows": len(combined),
                    "load_seconds": load_seconds,
                    "sources": list(source_timings.keys()),
                },
            }
        )

    logger.info(
        "Loaded %s rows from %s sources in %.2fs",
        len(combined),
        len(source_timings),
        load_seconds,
    )

    intent_summary_lookup = None
    intent_result = None
    intent_start = perf_counter()
    result, summary = collect_intent_signals(config)
    if result is not None:
        intent_result = result
        intent_summary_lookup = summary
        metrics["intent_collection_seconds"] = perf_counter() - intent_start
        metrics["intent_signal_count"] = int(result.signals.shape[0])
        metrics["intent_target_count"] = int(result.digest.shape[0])
        if result.warnings:
            metrics["intent_warnings"] = list(result.warnings)
        if config.enable_audit_trail:
            collector_names = []
            if config.intent_plan is not None:
                collector_names = [
                    collector.name for collector in config.intent_plan.active_collectors()
                ]
            audit_trail.append(
                {
                    "timestamp": time_fn(),
                    "event": "intent_collection_complete",
                    "details": {
                        "collectors": collector_names,
                        "signals": int(result.signals.shape[0]),
                        "targets": int(result.digest.shape[0]),
                    },
                }
            )

    if combined.empty:
        return handle_empty_pipeline(
            config,
            pipeline_start,
            metrics,
            audit_trail,
            redaction_events,
            intent_result,
        )

    aggregation_result = aggregate_records(
        config,
        combined,
        intent_summary_lookup,
        lambda event, payload: relay_progress(
            config,
            event,
            payload,
            {
                "aggregate_started": PIPELINE_EVENT_AGGREGATE_STARTED,
                "aggregate_progress": PIPELINE_EVENT_AGGREGATE_PROGRESS,
                "aggregate_completed": PIPELINE_EVENT_AGGREGATE_COMPLETED,
            },
        ),
    )
    metrics.update({k: v for k, v in aggregation_result.metrics.items() if v is not None})

    if config.enable_audit_trail:
        audit_trail.append(
            {
                "timestamp": time_fn(),
                "event": "aggregation_complete",
                "details": {
                    "aggregated_records": len(aggregation_result.refined_df),
                    "conflicts_resolved": len(aggregation_result.conflicts),
                    "aggregation_seconds": metrics["aggregation_seconds"],
                },
            }
        )

    logger.info(
        "Aggregated %s records with %s conflict resolutions",
        len(aggregation_result.refined_df),
        len(aggregation_result.conflicts),
    )

    validation_result = validate_dataset(
        config,
        aggregation_result.refined_df,
        lambda event, payload: relay_progress(
            config,
            event,
            payload,
            {
                "schema_started": PIPELINE_EVENT_SCHEMA_STARTED,
                "schema_completed": PIPELINE_EVENT_SCHEMA_COMPLETED,
                "expectations_started": PIPELINE_EVENT_EXPECTATIONS_STARTED,
                "expectations_completed": PIPELINE_EVENT_EXPECTATIONS_COMPLETED,
            },
        ),
    )
    metrics.update(validation_result.metrics)
    invalid_record_count = int(
        len(aggregation_result.refined_df) - len(validation_result.validated_df)
    )

    if config.enable_audit_trail and validation_result.schema_errors:
        audit_trail.append(
            {
                "timestamp": time_fn(),
                "event": "schema_validation_errors",
                "details": {
                    "error_count": len(validation_result.schema_errors),
                    "invalid_records": invalid_record_count,
                },
            }
        )

    if config.pii_redaction.enabled:
        validated_df, post_redaction = apply_redaction(config, validation_result.validated_df)
        validation_result.validated_df = validated_df
        if post_redaction:
            redaction_events.extend(post_redaction)
            metrics["redacted_cells"] = metrics.get("redacted_cells", 0) + len(post_redaction)
            if config.enable_audit_trail:
                audit_trail.append(
                    {
                        "timestamp": time_fn(),
                        "event": "pii_redacted_output",
                        "details": {
                            "columns": sorted({event["column"] for event in post_redaction}),
                            "redacted_cells": len(post_redaction),
                            "operator": config.pii_redaction.operator,
                        },
                    }
                )

    else:
        validated_df = validation_result.validated_df

    export_metrics, party_store, daily_list_df = publish_outputs(
        config,
        validated_df,
        aggregation_result.refined_df,
        validation_result.expectation_summary,
        metrics,
        pipeline_start,
        lambda event, payload: relay_progress(
            config,
            event,
            payload,
            {
                "write_started": PIPELINE_EVENT_WRITE_STARTED,
                "write_completed": PIPELINE_EVENT_WRITE_COMPLETED,
            },
        ),
        intent_result=intent_result,
    )
    metrics.update(export_metrics)

    sanitized_notices: list[dict[str, Any]] = []
    if contract_notices:
        sanitized_notices = persist_contract_notices(
            config, contract_notices, hooks.datetime_factory
        )
        if sanitized_notices:
            metrics["contract_notices"] = sanitized_notices
            if config.enable_audit_trail:
                audit_trail.append(
                    {
                        "timestamp": time_fn(),
                        "event": "contract_notices",
                        "details": sanitized_notices,
                    }
                )
            for notice in sanitized_notices:
                logger.warning(
                    "Deduplicated %s row(s) from %s (primary key: %s). Artifact: %s",
                    notice["duplicate_count"],
                    notice["table_name"],
                    ", ".join(notice.get("primary_key", [])),
                    notice["artifact_path"] or "n/a",
                )

    total_records = int(len(aggregation_result.refined_df))
    invalid_records = invalid_record_count

    recommendations: list[str] = []
    if config.enable_recommendations:
        recommendations = generate_recommendations(
            validation_result.validated_df,
            validation_result.expectation_summary,
            validation_result.quality_distribution,
        )
    if sanitized_notices:
        for notice in sanitized_notices:
            sample_keys = notice.get("sample_keys") or []
            key_preview = ", ".join(sample_keys[:3])
            message = (
                f"Deduplicated {notice['duplicate_count']} record(s) in "
                f"{notice['table_name']} based on primary key "
                f"{', '.join(notice.get('primary_key', []))}."
            )
            if key_preview:
                message += f" Sample keys: {key_preview}."
            artifact_path = notice.get("artifact_path")
            if artifact_path:
                message += f" Duplicate rows exported to {artifact_path}."
            recommendations.append(message)

    metrics_copy = dict(metrics)
    if config.enable_audit_trail:
        audit_trail.append(
            {
                "timestamp": time_fn(),
                "event": "pipeline_complete",
                "details": {
                    "total_records": total_records,
                    "invalid_records": invalid_records,
                    "duration_seconds": metrics_copy.get("total_seconds", 0.0),
                },
            }
        )

    report = QualityReport(
        total_records=total_records,
        invalid_records=invalid_records,
        schema_validation_errors=validation_result.schema_errors,
        expectations_passed=validation_result.expectation_summary.success,
        expectation_failures=validation_result.expectation_summary.failures,
        source_breakdown=aggregation_result.source_breakdown,
        data_quality_distribution=validation_result.quality_distribution,
        performance_metrics=metrics_copy,
        recommendations=recommendations,
        audit_trail=audit_trail if config.enable_audit_trail else [],
        conflict_resolutions=aggregation_result.conflicts,
    )

    notify_progress(
        config,
        PIPELINE_EVENT_COMPLETED,
        total_records=report.total_records,
        invalid_records=report.invalid_records,
        duration=metrics_copy["total_seconds"],
    )

    intent_signals = intent_result.signals if intent_result is not None else None
    intent_digest = intent_result.digest if intent_result is not None else None

    return PipelineResult(
        refined=validation_result.validated_df,
        quality_report=report,
        performance_metrics=metrics_copy,
        party_store=party_store,
        pii_redaction_events=redaction_events,
        intent_signals=intent_signals,
        intent_digest=intent_digest,
        daily_list=daily_list_df,
    )


class BasePipelineExecutor:
    """Adapter that executes the base Hotpass pipeline."""

    def run(self, config: PipelineConfig) -> PipelineResult:
        return execute_pipeline(config)
