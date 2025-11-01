"""Utilities for benchmarking the Hotpass pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_sources import ExcelReadOptions
from .pipeline import PipelineConfig, PipelineResult, run_pipeline


@dataclass(frozen=True)
class BenchmarkResult:
    """Summary of repeated pipeline executions."""

    runs: int
    metrics: dict[str, Any]
    samples: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs": self.runs,
            "metrics": dict(self.metrics),
            "samples": [dict(sample) for sample in self.samples],
        }


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


_BENCHMARK_FIELDS: list[tuple[str, str]] = [
    ("Load seconds", "load_seconds"),
    ("Aggregation seconds", "aggregation_seconds"),
    ("Polars transform seconds", "polars_transform_seconds"),
    ("Polars materialize seconds", "polars_materialize_seconds"),
    ("Pandas sort seconds", "pandas_sort_seconds"),
    ("Polars sort speedup", "polars_sort_speedup"),
    ("DuckDB sort seconds", "duckdb_sort_seconds"),
    ("Polars write seconds", "polars_write_seconds"),
    ("Expectations seconds", "expectations_seconds"),
    ("Write seconds", "write_seconds"),
    ("Total seconds", "total_seconds"),
    ("Rows per second", "rows_per_second"),
    ("Load rows per second", "load_rows_per_second"),
]


def benchmark_fields() -> list[tuple[str, str]]:
    """Expose the metrics captured in benchmark summaries."""

    return list(_BENCHMARK_FIELDS)


def run_benchmark(
    *,
    input_dir: Path,
    output_path: Path,
    runs: int = 3,
    expectation_suite_name: str = "default",
    country_code: str = "ZA",
    excel_options: ExcelReadOptions | None = None,
) -> BenchmarkResult:
    """Execute the pipeline repeatedly and aggregate performance metrics."""

    if runs <= 0:
        msg = "runs must be a positive integer"
        raise ValueError(msg)

    samples: list[dict[str, Any]] = []
    metric_totals: dict[str, list[float]] = {}
    source_totals: dict[str, list[float]] = {}

    for _ in range(runs):
        config = PipelineConfig(
            input_dir=input_dir,
            output_path=output_path,
            expectation_suite_name=expectation_suite_name,
            country_code=country_code,
            excel_options=excel_options,
        )
        result: PipelineResult = run_pipeline(config)
        sample_metrics = dict(result.performance_metrics)
        samples.append(sample_metrics)

        for key, value in sample_metrics.items():
            if key == "source_load_seconds" and isinstance(value, dict):
                for loader, seconds in value.items():
                    if isinstance(seconds, int | float):
                        source_totals.setdefault(loader, []).append(float(seconds))
                continue
            if isinstance(value, int | float):
                metric_totals.setdefault(key, []).append(float(value))

    aggregated: dict[str, Any] = {key: _average(values) for key, values in metric_totals.items()}
    if source_totals:
        aggregated["source_load_seconds"] = {
            loader: _average(values) for loader, values in source_totals.items()
        }

    return BenchmarkResult(runs=runs, metrics=aggregated, samples=samples)
