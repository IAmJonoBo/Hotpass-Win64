"""Streamlit dashboard for Hotpass pipeline monitoring.

This module provides a web-based dashboard for monitoring pipeline runs,
quality metrics, and orchestration status.
"""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

from hotpass.config import get_default_profile
from hotpass.data_sources import ExcelReadOptions
from hotpass.pipeline import PipelineConfig, run_pipeline

# Environment variable names reference secrets intentionally.
AUTH_PASSWORD_ENV = "HOTPASS_DASHBOARD_PASSWORD"  # nosec B105  # pragma: allowlist secret
ALLOWED_ROOTS_ENV = "HOTPASS_DASHBOARD_ALLOWED_ROOTS"
AUTH_STATE_KEY = "hotpass_dashboard_authenticated"
# UI labels include the word "password" by design.
PASSWORD_INPUT_LABEL = "Dashboard Password"  # nosec B105  # pragma: allowlist secret
UNLOCK_BUTTON_LABEL = "Unlock dashboard"
RUN_BUTTON_LABEL = "▶️ Run Pipeline"
DOCS_URL = (
    "https://github.com/IAmJonoBo/Hotpass/tree/main/docs/how-to-guides/orchestrate-and-observe.md"
)
GLOSSARY_URL = "https://github.com/IAmJonoBo/Hotpass/tree/main/docs/reference/data-model.md"
DATA_PREVIEW_CAPTION = (
    "Preview of the first 20 refined records. Use arrow keys or J/K to move between rows, "
    "and consult the glossary for field definitions."
)

__all__ = [
    "ALLOWED_ROOTS_ENV",
    "AUTH_PASSWORD_ENV",
    "AUTH_STATE_KEY",
    "DOCS_URL",
    "GLOSSARY_URL",
    "UNLOCK_BUTTON_LABEL",
    "PASSWORD_INPUT_LABEL",
    "RUN_BUTTON_LABEL",
    "DATA_PREVIEW_CAPTION",
    "load_pipeline_history",
    "save_pipeline_run",
    "main",
    "st",
]


def _load_allowed_roots() -> list[Path]:
    """Load filesystem allowlist from environment or defaults."""

    env_value = os.getenv(ALLOWED_ROOTS_ENV, "")
    if env_value:
        candidates = [entry.strip() for entry in env_value.split(os.pathsep)]
    else:
        candidates = ["./data", "./dist", "./logs"]

    roots: list[Path] = []
    for candidate in candidates:
        if not candidate:
            continue
        roots.append(Path(candidate).expanduser().resolve())
    return roots


def _ensure_path_within_allowlist(
    target: Path, allowlist: Iterable[Path], *, description: str
) -> None:
    """Ensure *target* sits inside at least one allowed root."""

    resolved_target = target.expanduser().resolve()
    allowed = []
    for root in allowlist:
        resolved_root = root.expanduser().resolve()
        allowed.append(resolved_root)
        try:
            resolved_target.relative_to(resolved_root)
            return
        except ValueError:
            continue

    allowed_display = ", ".join(str(root) for root in allowed)
    raise ValueError(
        f"{description} '{resolved_target}' is outside of allowed directories: {allowed_display}"
    )


def _validate_input_directory(path: Path, allowlist: Iterable[Path]) -> Path:
    """Validate input directory selection against allowlist."""

    resolved = path.expanduser().resolve()
    _ensure_path_within_allowlist(resolved, allowlist, description="Input directory")
    return resolved


def _validate_output_path(path: Path, allowlist: Iterable[Path]) -> Path:
    """Validate output path selection against allowlist."""

    resolved = path.expanduser().resolve()
    _ensure_path_within_allowlist(resolved.parent, allowlist, description="Output directory")
    return resolved


def _require_authentication() -> bool:
    """Prompt for password when dashboard authentication is configured."""

    password = os.getenv(AUTH_PASSWORD_ENV)
    if not password:
        return True

    if st.session_state.get(AUTH_STATE_KEY):
        return True

    st.sidebar.header("Authentication")
    provided_password = st.sidebar.text_input(
        PASSWORD_INPUT_LABEL, type="password", help="Enter the shared dashboard secret"
    )
    unlock_pressed = st.sidebar.button(UNLOCK_BUTTON_LABEL, use_container_width=True)

    if unlock_pressed:
        if secrets.compare_digest(provided_password, password):
            st.session_state[AUTH_STATE_KEY] = True
            st.success("Dashboard unlocked for this session.")
            return True
        st.error("Invalid dashboard password. Access denied.")

    st.warning("Authentication required. Provide the dashboard password to continue.")
    return False


def load_pipeline_history(history_file: Path) -> list[dict[str, Any]]:
    """Load pipeline execution history from file.

    Args:
        history_file: Path to history JSON file

    Returns:
        List of pipeline run records
    """
    if not history_file.exists():
        return []

    with open(history_file) as f:
        history_data = json.load(f)

    if not isinstance(history_data, list):
        return []

    typed_history: list[dict[str, Any]] = []
    for entry in history_data:
        if isinstance(entry, dict):
            typed_history.append(dict(cast(Mapping[str, Any], entry)))
    return typed_history


def save_pipeline_run(history_file: Path, run_data: Mapping[str, Any]) -> None:
    """Save a pipeline run to history.

    Args:
        history_file: Path to history JSON file
        run_data: Run metadata to save
    """
    history = load_pipeline_history(history_file)
    history.append(dict(run_data))

    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2, default=str)


def main() -> None:
    """Main Streamlit dashboard application."""
    st.set_page_config(
        page_title="Hotpass Pipeline Dashboard",
        page_icon="🔥",
        layout="wide",
    )
    st.title("🔥 Hotpass Data Refinement Dashboard")
    st.markdown("Monitor and control your data refinement pipeline")

    if not _require_authentication():
        return

    allowlist = _load_allowed_roots()

    st.sidebar.header("Configuration")

    input_dir = st.sidebar.text_input(
        "Input Directory",
        value="./data",
        help="Directory containing Excel input files",
    )

    output_path = st.sidebar.text_input(
        "Output Path",
        value="./data/refined_data.xlsx",
        help="Path for refined output file",
    )

    profile_name = st.sidebar.selectbox(
        "Industry Profile",
        options=["aviation", "generic"],
        help="Industry-specific configuration profile",
    )

    excel_chunk_size = st.sidebar.number_input(
        "Excel Chunk Size",
        min_value=0,
        value=0,
        help="Chunk size for reading large Excel files (0 = no chunking)",
    )

    # Main tabs
    tab1, tab2, tab3 = st.tabs(["Pipeline Control", "Execution History", "Quality Metrics"])

    with tab1:
        st.header("Pipeline Execution")

        col1, col2 = st.columns([3, 1])

        with col1:
            st.info("Configure settings in the sidebar, then click 'Run Pipeline' to execute")

        with col2:
            run_button = st.button(RUN_BUTTON_LABEL, type="primary", use_container_width=True)

        if run_button:
            with st.spinner("Running pipeline..."):
                try:
                    input_dir_path = _validate_input_directory(Path(input_dir), allowlist)
                    output_path_obj = _validate_output_path(Path(output_path), allowlist)

                    # Build configuration
                    profile = get_default_profile(profile_name)
                    config = PipelineConfig(
                        input_dir=input_dir_path,
                        output_path=output_path_obj,
                        industry_profile=profile,
                        excel_options=ExcelReadOptions(
                            chunk_size=(excel_chunk_size if excel_chunk_size > 0 else None)
                        ),
                    )

                    # Run pipeline
                    start_time = datetime.now()
                    result = run_pipeline(config)
                    end_time = datetime.now()

                    # Save to history
                    history_file = Path("./logs/pipeline_history.json")
                    run_data = {
                        "timestamp": start_time.isoformat(),
                        "duration_seconds": (end_time - start_time).total_seconds(),
                        "total_records": len(result.refined),
                        "expectations_passed": result.quality_report.expectations_passed,
                        "profile": profile_name,
                        "input_dir": str(input_dir_path),
                        "output_path": str(output_path_obj),
                    }
                    save_pipeline_run(history_file, run_data)

                    # Display results
                    if result.quality_report.expectations_passed:
                        st.success(
                            "✅ Pipeline completed successfully! "
                            "Download the refined workbook or inspect the data preview below "
                            "to confirm the results meet expectations."
                        )
                    else:
                        st.warning(
                            "⚠️ Pipeline completed with validation warnings. "
                            "Review the Quality Report panel for remediation steps and rerun once "
                            "the highlighted issues are fixed."
                        )

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Total Records", len(result.refined))

                    with col2:
                        st.metric(
                            "Duration",
                            f"{(end_time - start_time).total_seconds():.1f}s",
                        )

                    with col3:
                        mean_quality = result.refined["data_quality_score"].mean()
                        st.metric("Avg Quality", f"{mean_quality:.2f}")

                    with col4:
                        invalid = result.quality_report.invalid_records
                        st.metric("Invalid Records", invalid)

                    # Show quality report details
                    with st.expander("📊 Quality Report Details") as report_panel:
                        report_panel.markdown(
                            "Use this report to identify expectations that failed and "
                            "cross-reference remediation guidance in the documentation."
                        )
                        report_panel.json(result.quality_report.to_dict())

                    # Show data preview
                    with st.expander("🔍 Data Preview") as preview_panel:
                        preview_panel.caption(DATA_PREVIEW_CAPTION)
                        preview_panel.markdown(
                            "Need help interpreting fields? See the [data model glossary]"
                            f"({GLOSSARY_URL})."
                        )
                        preview_panel.dataframe(result.refined.head(20), use_container_width=True)

                except ValueError as error:
                    st.error(
                        "⚠️ Input validation failed. Adjust the configured paths or "
                        "options and try again."
                    )
                    st.info(str(error))
                except Exception as e:
                    st.error(
                        "❌ Pipeline failed unexpectedly. Review the stack trace, "
                        "address the failure, and rerun the pipeline."
                    )
                    st.exception(e)

    with tab2:
        st.header("Execution History")

        history_file = Path("./logs/pipeline_history.json")
        history = load_pipeline_history(history_file)

        if history:
            # Convert to DataFrame
            df = pd.DataFrame(history)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp", ascending=False)

            # Summary metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Runs", len(df))

            with col2:
                success_rate = (df["expectations_passed"].sum() / len(df)) * 100
                st.metric("Success Rate", f"{success_rate:.1f}%")

            with col3:
                avg_duration = df["duration_seconds"].mean()
                st.metric("Avg Duration", f"{avg_duration:.1f}s")

            # Recent runs table
            st.subheader("Recent Runs")
            display_df = df[
                [
                    "timestamp",
                    "total_records",
                    "expectations_passed",
                    "duration_seconds",
                    "profile",
                ]
            ].head(20)
            display_df.columns = [
                "Timestamp",
                "Records",
                "Passed",
                "Duration (s)",
                "Profile",
            ]
            st.dataframe(display_df, use_container_width=True)

            # Trend chart
            st.subheader("Quality Trends")
            if len(df) > 1:
                chart_data = df[["timestamp", "total_records"]].set_index("timestamp")
                st.line_chart(chart_data)
        else:
            st.info("No execution history available. Run the pipeline to see results here.")

    with tab3:
        st.header("Quality Metrics")

        history_file = Path("./logs/pipeline_history.json")
        history = load_pipeline_history(history_file)

        if history:
            df = pd.DataFrame(history)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Success Rate by Profile")
                profile_stats = (
                    df.groupby("profile")
                    .agg({"expectations_passed": ["sum", "count"]})
                    .reset_index()
                )
                profile_stats.columns = ["Profile", "Passed", "Total"]
                profile_stats["Success Rate %"] = (
                    profile_stats["Passed"] / profile_stats["Total"] * 100
                ).round(1)
                st.dataframe(profile_stats, use_container_width=True)

            with col2:
                st.subheader("Performance Metrics")
                perf_stats = df.agg(
                    {
                        "duration_seconds": ["mean", "min", "max"],
                        "total_records": ["mean", "min", "max"],
                    }
                ).round(2)
                st.dataframe(perf_stats, use_container_width=True)
        else:
            st.info("No quality metrics available yet. Run the pipeline to collect metrics.")

    # Footer
    st.markdown("---")
    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown("Hotpass Data Refinement Pipeline")
    st.markdown(
        f"Last updated: {timestamp} • Need help? Review the [operations guide]({DOCS_URL})."
    )


if __name__ == "__main__":
    main()
