from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd
from pandera.errors import SchemaErrors

from ..quality import run_expectations
from ..storage import PolarsDataset
from ..telemetry import pipeline_stage
from .config import PipelineConfig


def _get_ssot_schema() -> Any:
    from . import build_ssot_schema  # Local import to avoid circular dependency

    return build_ssot_schema()


@dataclass
class ValidationResult:
    validated_df: pd.DataFrame
    schema_errors: list[str]
    expectation_summary: Any
    quality_distribution: dict[str, float]
    metrics: dict[str, Any]


def validate_dataset(
    config: PipelineConfig,
    refined_df: pd.DataFrame,
    notify_progress: Callable[[str, dict[str, Any]], None],
) -> ValidationResult:
    metrics: dict[str, Any] = {}
    schema = _get_ssot_schema()
    schema_errors: list[str] = []
    validated_df = refined_df

    notify_progress("schema_started", {"total_records": len(refined_df)})
    with pipeline_stage("validate", {"records": len(refined_df)}):
        try:
            validated_df = schema.validate(refined_df, lazy=True)
        except SchemaErrors as exc:
            schema_errors = [
                f"{row['column']}: {row['failure_case']}" for _, row in exc.failure_cases.iterrows()
            ]
            invalid_indices = exc.failure_cases["index"].unique().tolist()
            valid_indices = [idx for idx in refined_df.index if idx not in invalid_indices]
            if not valid_indices:
                validated_df = refined_df
                schema_errors.append(
                    f"CRITICAL: All {len(refined_df)} records failed schema validation. "
                    "Output contains unvalidated data."
                )
            else:
                validated_df = schema.validate(refined_df.loc[valid_indices], lazy=False)
        if len(validated_df) == 0 and len(refined_df) > 0:
            validated_df = refined_df
            if "CRITICAL: Schema validation resulted in complete data loss" not in schema_errors:
                schema_errors.append(
                    f"CRITICAL: Schema validation resulted in complete data loss. "
                    f"All {len(refined_df)} records would have been filtered out. "
                    "Writing original data to prevent empty output file."
                )
    notify_progress("schema_completed", {"errors": len(schema_errors)})

    profile = config.industry_profile
    email_threshold = profile.email_validation_threshold if profile else 0.85
    phone_threshold = profile.phone_validation_threshold if profile else 0.85
    website_threshold = profile.website_validation_threshold if profile else 0.85

    notify_progress("expectations_started", {"total_records": len(validated_df)})
    perf_counter = config.runtime_hooks.perf_counter
    expectation_start = perf_counter()
    expectation_summary = run_expectations(
        validated_df,
        email_mostly=email_threshold,
        phone_mostly=phone_threshold,
        website_mostly=website_threshold,
    )
    metrics["expectations_seconds"] = perf_counter() - expectation_start
    notify_progress(
        "expectations_completed",
        {
            "success": expectation_summary.success,
            "failure_count": len(expectation_summary.failures),
        },
    )

    dataset = PolarsDataset.from_pandas(validated_df)
    quality_distribution = dataset.column_stats("data_quality_score")

    return ValidationResult(
        validated_df=validated_df,
        schema_errors=schema_errors,
        expectation_summary=expectation_summary,
        quality_distribution=quality_distribution,
        metrics=metrics,
    )
