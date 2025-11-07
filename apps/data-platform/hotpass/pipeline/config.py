from __future__ import annotations

import html
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from ..automation.http import AutomationHTTPConfig
from ..compliance import PIIRedactionConfig
from ..config import IndustryProfile, get_default_profile
from ..data_sources import ExcelReadOptions
from ..data_sources.agents import AcquisitionPlan
from ..enrichment.intent import IntentPlan
from ..pipeline_reporting import html_performance_rows, html_source_performance
from ..transform.scoring import LeadScorer


def _default_datetime_factory() -> datetime:
    """Return a timezone-aware timestamp aligned with prior behaviour."""

    return datetime.now(tz=UTC)


@dataclass
class PipelineRuntimeHooks:
    """Injectable runtime hooks for deterministic pipeline execution."""

    time_fn: Callable[[], float] = time.time
    perf_counter: Callable[[], float] = time.perf_counter
    datetime_factory: Callable[[], datetime] = _default_datetime_factory


if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..data_sources.agents.runner import AgentTiming
    from ..domain.party import PartyStore
    from ..linkage import LinkageResult

ProgressListener = Callable[[str, dict[str, Any]], None]


SSOT_COLUMNS: list[str] = [
    "organization_name",
    "organization_slug",
    "province",
    "country",
    "area",
    "address_primary",
    "organization_category",
    "organization_type",
    "status",
    "website",
    "planes",
    "description",
    "notes",
    "source_datasets",
    "source_record_ids",
    "contact_primary_name",
    "contact_primary_role",
    "contact_primary_email",
    "contact_primary_phone",
    "contact_primary_email_confidence",
    "contact_primary_email_status",
    "contact_primary_phone_confidence",
    "contact_primary_phone_status",
    "contact_primary_lead_score",
    "intent_signal_score",
    "intent_signal_count",
    "intent_signal_types",
    "intent_last_observed_at",
    "intent_top_insights",
    "contact_validation_flags",
    "contact_secondary_emails",
    "contact_secondary_phones",
    "contact_email_confidence_avg",
    "contact_phone_confidence_avg",
    "contact_verification_score_avg",
    "contact_lead_score_avg",
    "data_quality_score",
    "data_quality_flags",
    "selection_provenance",
    "last_interaction_date",
    "priority",
    "privacy_basis",
]


@dataclass
class PipelineConfig:
    input_dir: Path
    output_path: Path
    expectation_suite_name: str = "default"
    country_code: str = "ZA"
    excel_options: ExcelReadOptions | None = None
    industry_profile: IndustryProfile | None = None
    output_format: Any | None = None  # Deferred import in initialise_config
    enable_formatting: bool = True
    enable_audit_trail: bool = True
    enable_recommendations: bool = True
    progress_listener: ProgressListener | None = None
    runtime_hooks: PipelineRuntimeHooks = field(default_factory=PipelineRuntimeHooks)
    pii_redaction: PIIRedactionConfig = field(default_factory=PIIRedactionConfig)
    acquisition_plan: AcquisitionPlan | None = None
    agent_credentials: Mapping[str, str] = field(default_factory=dict)
    intent_plan: IntentPlan | None = None
    intent_credentials: Mapping[str, str] = field(default_factory=dict)
    intent_digest_path: Path | None = None
    intent_signal_store_path: Path | None = None
    daily_list_path: Path | None = None
    daily_list_size: int = 50
    automation_webhooks: tuple[str, ...] = field(default_factory=tuple)
    crm_endpoint: str | None = None
    crm_token: str | None = None
    automation_http: AutomationHTTPConfig = field(default_factory=AutomationHTTPConfig)
    research_settings: Mapping[str, Any] | None = None
    preloaded_agent_frame: pd.DataFrame | None = None
    preloaded_agent_timings: list[AgentTiming] = field(default_factory=list)
    preloaded_agent_warnings: list[str] = field(default_factory=list)
    backfill: bool = False
    incremental: bool = False
    since: datetime | None = None
    random_seed: int | None = None
    run_id: str | None = None
    import_mappings: list[Mapping[str, Any]] = field(default_factory=list)
    import_rules: list[Mapping[str, Any]] = field(default_factory=list)
    dist_dir: Path = field(default_factory=lambda: Path.cwd() / "dist")
    s3_endpoint_url: str | None = None
    aws_endpoint_url: str | None = None


@dataclass
class QualityReport:
    total_records: int
    invalid_records: int
    schema_validation_errors: list[str]
    expectations_passed: bool
    expectation_failures: list[str]
    source_breakdown: dict[str, int]
    data_quality_distribution: dict[str, float]
    performance_metrics: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    conflict_resolutions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "invalid_records": self.invalid_records,
            "schema_validation_errors": list(self.schema_validation_errors),
            "expectations_passed": self.expectations_passed,
            "expectation_failures": list(self.expectation_failures),
            "source_breakdown": dict(self.source_breakdown),
            "data_quality_distribution": dict(self.data_quality_distribution),
            "performance_metrics": dict(self.performance_metrics),
            "recommendations": list(self.recommendations),
            "audit_trail": list(self.audit_trail),
            "conflict_resolutions": list(self.conflict_resolutions),
        }

    def to_markdown(self) -> str:
        lines = ["# Hotpass Quality Report", ""]
        lines.extend(
            [
                "## Quality Metrics",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                f"| Total records | {self.total_records} |",
                f"| Invalid records | {self.invalid_records} |",
                f"| Expectations passed | {'Yes' if self.expectations_passed else 'No'} |",
                f"| Mean quality score | {self.data_quality_distribution.get('mean', 0.0):.2f} |",
                f"| Min quality score | {self.data_quality_distribution.get('min', 0.0):.2f} |",
                f"| Max quality score | {self.data_quality_distribution.get('max', 0.0):.2f} |",
                "",
            ]
        )

        lines.append("## Source Breakdown")
        lines.append("")
        if self.source_breakdown:
            lines.extend(["| Source | Records |", "| --- | ---: |"])
            for source, count in sorted(self.source_breakdown.items()):
                lines.append(f"| {source} | {count} |")
        else:
            lines.append("No source data recorded.")
        lines.append("")

        lines.append("## Schema Validation Errors")
        lines.append("")
        if self.schema_validation_errors:
            lines.extend(f"- {error}" for error in self.schema_validation_errors)
        else:
            lines.append("None")
        lines.append("")

        lines.append("## Expectation Failures")
        lines.append("")
        if self.expectation_failures:
            lines.extend(f"- {failure}" for failure in self.expectation_failures)
        else:
            lines.append("None")
        lines.append("")

        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            lines.extend(f"- {rec}" for rec in self.recommendations)
            lines.append("")

        if self.conflict_resolutions:
            lines.append("## Conflict Resolutions")
            lines.append("")
            lines.append("| Field | Chosen Source | Value | Alternatives |")
            lines.append("| --- | --- | --- | --- |")
            for conflict in self.conflict_resolutions[:10]:
                field = conflict.get("field", "Unknown")
                source = conflict.get("chosen_source", "Unknown")
                value = str(conflict.get("value", ""))[:50]
                alt_count = len(conflict.get("alternatives", []))
                lines.append(f"| {field} | {source} | {value} | {alt_count} alternatives |")
            if len(self.conflict_resolutions) > 10:
                remaining = len(self.conflict_resolutions) - 10
                lines.append(f"| ... | ... | ... | {remaining} more conflicts |")
            lines.append("")

        lines.append("## Performance Metrics")
        lines.append("")
        if self.performance_metrics:
            lines.extend(["| Metric | Value |", "| --- | ---: |"])
            primary_metrics = [
                ("Load seconds", self.performance_metrics.get("load_seconds")),
                (
                    "Aggregation seconds",
                    self.performance_metrics.get("aggregation_seconds"),
                ),
                (
                    "Expectations seconds",
                    self.performance_metrics.get("expectations_seconds"),
                ),
                ("Write seconds", self.performance_metrics.get("write_seconds")),
                ("Total seconds", self.performance_metrics.get("total_seconds")),
                ("Rows per second", self.performance_metrics.get("rows_per_second")),
                (
                    "Load rows per second",
                    self.performance_metrics.get("load_rows_per_second"),
                ),
            ]
            for label, raw_value in primary_metrics:
                if raw_value is None:
                    continue
                if isinstance(raw_value, int | float):
                    value = f"{float(raw_value):.4f}"
                else:
                    value = str(raw_value)
                lines.append(f"| {label} | {value} |")
            lines.append("")

            source_metrics = self.performance_metrics.get("source_load_seconds", {})
            if source_metrics:
                lines.append("### Source Load Durations")
                lines.append("")
                lines.extend(["| Loader | Seconds |", "| --- | ---: |"])
                for loader, seconds in sorted(source_metrics.items()):
                    lines.append(f"| {loader} | {float(seconds):.4f} |")
                lines.append("")
        else:
            lines.append("No performance metrics recorded.")
            lines.append("")

        return "\n".join(lines) + "\n"

    def to_html(self) -> str:
        def _metrics_row(label: str, value: str) -> str:
            escaped_label = html.escape(label)
            escaped_value = html.escape(value)
            return f'<tr><th scope="row">{escaped_label}</th><td>{escaped_value}</td></tr>'

        quality_rows = [
            _metrics_row("Total records", str(self.total_records)),
            _metrics_row("Invalid records", str(self.invalid_records)),
            _metrics_row("Expectations passed", "Yes" if self.expectations_passed else "No"),
            _metrics_row(
                "Mean quality score",
                f"{self.data_quality_distribution.get('mean', 0.0):.2f}",
            ),
            _metrics_row(
                "Min quality score",
                f"{self.data_quality_distribution.get('min', 0.0):.2f}",
            ),
            _metrics_row(
                "Max quality score",
                f"{self.data_quality_distribution.get('max', 0.0):.2f}",
            ),
        ]

        source_rows = "".join(
            f"<tr><td>{html.escape(source)}</td><td>{count}</td></tr>"
            for source, count in sorted(self.source_breakdown.items())
        )
        if not source_rows:
            source_rows = '<tr><td colspan="2">No source data recorded.</td></tr>'

        schema_items = (
            "".join(f"<li>{html.escape(error)}</li>" for error in self.schema_validation_errors)
            or "<li>None</li>"
        )
        expectation_items = (
            "".join(f"<li>{html.escape(failure)}</li>" for failure in self.expectation_failures)
            or "<li>None</li>"
        )

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8" />\n'
            "  <title>Hotpass Quality Report</title>\n"
            "  <style>\n"
            "    body { font-family: Arial, sans-serif; margin: 2rem; }\n"
            "    table { border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }\n"
            "    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }\n"
            "    th { background: #f7f7f7; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <h1>Hotpass Quality Report</h1>\n"
            "  <h2>Quality Metrics</h2>\n"
            "  <table>\n"
            "    <tbody>\n"
            f"      {''.join(quality_rows)}\n"
            "    </tbody>\n"
            "  </table>\n"
            "  <h2>Source Breakdown</h2>\n"
            "  <table>\n"
            "    <thead><tr><th>Source</th><th>Records</th></tr></thead>\n"
            "    <tbody>\n"
            f"      {source_rows}\n"
            "    </tbody>\n"
            "  </table>\n"
            "  <h2>Schema Validation Errors</h2>\n"
            f"  <ul>{schema_items}</ul>\n"
            "  <h2>Expectation Failures</h2>\n"
            f"  <ul>{expectation_items}</ul>\n"
            "  <h2>Performance Metrics</h2>\n"
            "  <table>\n"
            f"    <tbody>{html_performance_rows(self.performance_metrics)}</tbody>\n"
            "  </table>\n"
            f"  {html_source_performance(self.performance_metrics)}"
            "</body>\n"
            "</html>\n"
        )


@dataclass
class PipelineResult:
    refined: pd.DataFrame
    quality_report: QualityReport
    performance_metrics: dict[str, Any]
    compliance_report: dict[str, Any] | None = None
    party_store: PartyStore | None = None
    linkage: LinkageResult | None = None
    pii_redaction_events: list[dict[str, Any]] = field(default_factory=list)
    intent_signals: pd.DataFrame | None = None
    intent_digest: pd.DataFrame | None = None
    daily_list: pd.DataFrame | None = None


DEFAULT_LEAD_SCORER = LeadScorer()


def initialise_config(config: PipelineConfig) -> PipelineConfig:
    """Populate implicit configuration defaults."""

    if config.industry_profile is None:
        config.industry_profile = get_default_profile("generic")

    if config.output_format is None:
        from ..formatting import OutputFormat  # Local import to avoid cycle

        config.output_format = OutputFormat()

    return config
