"""Helpers for rendering and reporting pipeline outputs."""

from __future__ import annotations

import html
from collections.abc import Iterable
from typing import Any

import pandas as pd

from .normalization import clean_string
from .quality import ExpectationSummary


def html_performance_rows(metrics: dict[str, Any]) -> str:
    """Render performance metrics as HTML rows."""
    if not metrics:
        return '<tr><td colspan="2">No performance metrics recorded.</td></tr>'
    rows: list[str] = []
    mapping = [
        ("Load seconds", metrics.get("load_seconds")),
        ("Aggregation seconds", metrics.get("aggregation_seconds")),
        ("Expectations seconds", metrics.get("expectations_seconds")),
        ("Write seconds", metrics.get("write_seconds")),
        ("Total seconds", metrics.get("total_seconds")),
        ("Rows per second", metrics.get("rows_per_second")),
        ("Load rows per second", metrics.get("load_rows_per_second")),
    ]
    for label, raw in mapping:
        if raw is None:
            continue
        if isinstance(raw, int | float):
            value = f"{float(raw):.4f}"
        else:
            value = str(raw)
        rows.append(f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>")
    if not rows:
        return '<tr><td colspan="2">No performance metrics recorded.</td></tr>'
    return "".join(rows)


def html_source_performance(metrics: dict[str, Any]) -> str:
    """Render per-source load timings as HTML."""
    if not metrics:
        return ""
    sources = metrics.get("source_load_seconds", {})
    if not sources:
        return ""
    rows = "".join(
        "<tr><td>{}</td><td>{}</td></tr>".format(
            html.escape(loader),
            html.escape(f"{float(seconds):.4f}"),
        )
        for loader, seconds in sorted(sources.items())
    )
    return (
        "  <h3>Source Load Durations</h3>\n"
        "  <table>\n"
        "    <thead><tr><th>Loader</th><th>Seconds</th></tr></thead>\n"
        f"    <tbody>{rows}</tbody>\n"
        "  </table>\n"
    )


def collect_unique(values: Iterable[str | None]) -> list[str]:
    """Return cleaned, de-duplicated values while preserving the first-seen order."""

    unique: list[str] = []
    for value in values:
        cleaned = clean_string(value)
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


def generate_recommendations(
    validated_df: pd.DataFrame,
    expectation_summary: ExpectationSummary,
    quality_distribution: dict[str, float],
) -> list[str]:
    """Generate actionable recommendations based on data quality analysis."""
    recommendations: list[str] = []

    mean_quality = quality_distribution.get("mean", 0.0)
    if mean_quality < 0.5:
        recommendations.append(
            "CRITICAL: Average data quality score is below 50%. "
            "Review data sources and validation rules."
        )
    elif mean_quality < 0.75:
        recommendations.append(
            "WARNING: Average data quality score is between 50% and 75%. "
            "Target improvements in the lowest scoring datasets."
        )

    low_priority_rows = pd.DataFrame()
    if "priority" in validated_df.columns:
        priority_series = validated_df["priority"].astype("string").str.lower()
        low_priority_rows = validated_df[priority_series == "low"]

    if not low_priority_rows.empty:
        recommendations.append(
            "INFO: Several organisations remain marked as low priority. "
            "Verify that priority settings still reflect business intent."
        )

    if expectation_summary.failures:
        failure_counts: dict[str, int] = {}
        for failure in expectation_summary.failures:
            label = failure.split(":", 1)[0].strip() or "Unnamed expectation"
            failure_counts[label] = failure_counts.get(label, 0) + 1

        for expectation_name, failure_count in sorted(failure_counts.items()):
            recommendations.append(
                f"WARNING: {expectation_name} failed for {failure_count} record(s). "
                "Review expectation configuration or source data."
            )

    if not recommendations:
        recommendations.append(
            "Data quality looks good! All checks passed with strong quality scores."
        )

    return recommendations
