from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import polars as pl

from ..domain.party import PartyStore, build_party_store_from_refined
from ..formatting import OutputFormat, apply_excel_formatting, create_summary_sheet
from ..storage import DuckDBAdapter, PolarsDataset
from ..transform.scoring import build_daily_list
from .config import PipelineConfig
from .enrichment import write_intent_digest

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..enrichment.intent import IntentRunResult


def _write_csvw_metadata(output_path: Path) -> None:
    from ..validation import load_schema_descriptor  # Local import to avoid cycle

    schema_descriptor = load_schema_descriptor("ssot.schema.json")
    sidecar = output_path.with_suffix(f"{output_path.suffix}-metadata.json")
    metadata = {
        "@context": "http://www.w3.org/ns/csvw",
        "url": output_path.name,
        "tableSchema": schema_descriptor,
    }
    sidecar.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def publish_outputs(
    config: PipelineConfig,
    validated_df: pd.DataFrame,
    refined_df: pd.DataFrame,
    expectation_summary: Any,
    metrics: dict[str, Any],
    pipeline_start: float,
    notify_progress: Callable[[str, dict[str, Any]], None],
    intent_result: IntentRunResult | None = None,
) -> tuple[dict[str, Any], PartyStore, pd.DataFrame | None]:
    validated_dataset = PolarsDataset.from_pandas(validated_df)
    parquet_path = config.output_path.with_suffix(".parquet")
    validated_dataset.write_parquet(parquet_path)
    metrics["parquet_path"] = str(parquet_path)
    metrics["polars_write_seconds"] = validated_dataset.timings.parquet_seconds

    ordered_frame = validated_dataset.query(
        DuckDBAdapter(),
        "SELECT * FROM dataset ORDER BY organization_name",
    )
    validated_dataset.replace(ordered_frame)
    metrics["duckdb_sort_seconds"] = validated_dataset.timings.query_seconds
    validated_df = validated_dataset.to_pandas().reset_index(drop=True)

    hooks = config.runtime_hooks
    perf_counter = hooks.perf_counter

    party_store = build_party_store_from_refined(
        validated_df,
        default_country=config.country_code,
        execution_time=hooks.datetime_factory(),
    )

    suffix = config.output_path.suffix.lower()
    notify_progress("write_started", {"path": str(config.output_path)})
    write_start = perf_counter()
    config.output_path.parent.mkdir(parents=True, exist_ok=True)

    if config.enable_formatting and suffix in {".xlsx", ".xls"}:
        with pd.ExcelWriter(config.output_path, engine="openpyxl") as writer:
            validated_df.to_excel(writer, sheet_name="Data", index=False)
            output_format: OutputFormat = config.output_format or OutputFormat()
            apply_excel_formatting(writer, "Data", validated_df, output_format)

            quality_report_dict = {
                "total_records": len(refined_df),
                "invalid_records": len(refined_df) - len(validated_df),
                "expectations_passed": expectation_summary.success,
            }
            summary_df = create_summary_sheet(validated_df, quality_report_dict)
            summary_df.to_excel(writer, sheet_name="Summary", index=False, header=False)
    elif suffix == ".csv":
        validated_df.to_csv(config.output_path, index=False)
        _write_csvw_metadata(config.output_path)
    elif suffix == ".parquet":
        pl.from_pandas(validated_df, include_index=False).write_parquet(config.output_path)
    else:
        validated_df.to_excel(config.output_path, index=False)

    metrics["write_seconds"] = perf_counter() - write_start
    metrics["total_seconds"] = perf_counter() - pipeline_start
    if metrics["total_seconds"] > 0:
        metrics["rows_per_second"] = len(validated_df) / metrics["total_seconds"]

    notify_progress(
        "write_completed",
        {"path": str(config.output_path), "write_seconds": metrics["write_seconds"]},
    )

    daily_list_df: pd.DataFrame | None = None
    if config.daily_list_path is not None or config.daily_list_size:
        digest_frame = intent_result.digest if intent_result is not None else pd.DataFrame()
        daily_list_df = build_daily_list(
            refined_df=validated_df,
            intent_digest=digest_frame,
            model=None,
            top_n=max(1, int(config.daily_list_size or 0)),
            output_path=config.daily_list_path,
        )
        metrics["daily_list_records"] = int(daily_list_df.shape[0])
        if config.daily_list_path is not None:
            metrics["daily_list_path"] = str(config.daily_list_path)

    if intent_result and config.intent_digest_path:
        write_intent_digest(intent_result, config.intent_digest_path)
        metrics["intent_digest_path"] = str(config.intent_digest_path)

    return metrics, party_store, daily_list_df
