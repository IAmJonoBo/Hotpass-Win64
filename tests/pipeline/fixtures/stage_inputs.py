"""Helpers providing deterministic inputs for modular pipeline stage tests."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import polars as pl
from hotpass.pipeline.aggregation import AggregationResult
from hotpass.pipeline.validation import ValidationResult


@dataclass(slots=True)
class StubExpectationSummary:
    """Lightweight replacement for expectation summaries in regression tests."""

    success: bool
    failures: list[str]


@dataclass(slots=True)
class ModularStageArtifacts:
    """Container holding reusable DataFrames for staged pipeline execution tests."""

    combined: pd.DataFrame
    refined: pd.DataFrame
    validated: pd.DataFrame
    source_breakdown: dict[str, int]
    expectation_summary: StubExpectationSummary
    quality_distribution: dict[str, float]


def build_modular_stage_artifacts() -> ModularStageArtifacts:
    """Return deterministic inputs that exercise the modular pipeline stages."""

    combined = pd.DataFrame(
        {
            "organization_name": ["Alpha Org", "Beta Org"],
            "organization_slug": ["alpha-org", "beta-org"],
            "data_quality_score": [0.95, 0.72],
        }
    )
    refined = combined.copy(deep=True)
    refined["contact_primary_email"] = [
        "contact@alpha.example",
        "info@beta.example",
    ]
    validated = refined.copy(deep=True)

    expectation_summary = StubExpectationSummary(success=True, failures=[])
    quality_distribution = {"mean": 0.835, "min": 0.72, "max": 0.95}
    source_breakdown = {"Contact Database": 2}

    return ModularStageArtifacts(
        combined=combined,
        refined=refined,
        validated=validated,
        source_breakdown=source_breakdown,
        expectation_summary=expectation_summary,
        quality_distribution=quality_distribution,
    )


def build_aggregation_result(artifacts: ModularStageArtifacts) -> AggregationResult:
    """Create an aggregation result matching the provided artifacts."""

    return AggregationResult(
        refined_df=artifacts.refined.copy(deep=True),
        combined_polars=pl.from_pandas(artifacts.refined.copy(deep=True), include_index=False),
        conflicts=[],
        metrics={"aggregation_seconds": 0.12},
        source_breakdown=dict(artifacts.source_breakdown),
    )


def build_validation_result(
    artifacts: ModularStageArtifacts,
    *,
    expectation_seconds: float = 0.08,
) -> ValidationResult:
    """Return a validation result aligned with the provided artifacts."""

    return ValidationResult(
        validated_df=artifacts.validated.copy(deep=True),
        schema_errors=[],
        expectation_summary=artifacts.expectation_summary,
        quality_distribution=dict(artifacts.quality_distribution),
        metrics={"expectations_seconds": expectation_seconds},
    )
