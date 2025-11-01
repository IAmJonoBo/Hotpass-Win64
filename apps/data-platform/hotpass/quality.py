"""Validation helpers using Pandera and Great Expectations."""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd
import pandera.pandas as pa
from hotpass.enrichment.validators import ValidationStatus
from pandera.pandas import Column, DataFrameSchema

try:  # pragma: no cover - import guard exercised via unit tests
    from great_expectations.core.batch import Batch
    from great_expectations.core.expectation_suite import ExpectationSuite
    from great_expectations.data_context.data_context import context_factory as ge_context_factory
    from great_expectations.data_context.data_context.ephemeral_data_context import (
        EphemeralDataContext,
    )
    from great_expectations.data_context.types.base import (
        DataContextConfig,
        InMemoryStoreBackendDefaults,
    )
    from great_expectations.execution_engine.pandas_execution_engine import PandasExecutionEngine
    from great_expectations.validator.validator import Validator
except ImportError:  # pragma: no cover - exercised when GE extras not installed
    _GE_RUNTIME: dict[str, Any] | None = None
else:
    _GE_RUNTIME = {
        "Batch": Batch,
        "ExpectationSuite": ExpectationSuite,
        "EphemeralDataContext": EphemeralDataContext,
        "DataContextConfig": DataContextConfig,
        "InMemoryStoreBackendDefaults": InMemoryStoreBackendDefaults,
        "PandasExecutionEngine": PandasExecutionEngine,
        "Validator": Validator,
        "project_manager": ge_context_factory.project_manager,
    }


@dataclass
class ExpectationSummary:
    success: bool
    failures: list[str]


def _run_with_great_expectations(
    sanitized: pd.DataFrame,
    *,
    email_mostly: float,
    phone_mostly: float,
    website_mostly: float,
    runtime_override: Mapping[str, Any] | None = None,
) -> ExpectationSummary | None:
    """
    Validate a sanitized DataFrame using Great Expectations.

    Parameters
    ----------
    sanitized : pd.DataFrame
        The DataFrame to validate.
    email_mostly : float
        The minimum fraction of valid emails required to pass the expectation.
    phone_mostly : float
        The minimum fraction of valid phone numbers required to pass the expectation.
    website_mostly : float
        The minimum fraction of valid website URLs required to pass the expectation.
    runtime_override : Mapping[str, Any] or None, optional
        Optional runtime components override for testing. Used internally to inject stub
        implementations or mock Great Expectations components.

    Returns
    -------
    ExpectationSummary or None
        The summary of validation results, or None if Great Expectations is unavailable.
    """
    runtime = runtime_override if runtime_override is not None else _GE_RUNTIME
    if runtime is None:
        return None

    config = runtime["DataContextConfig"](
        config_version=4,
        expectations_store_name="expectations_store",
        validation_results_store_name="validation_results_store",
        checkpoint_store_name="checkpoint_store",
        data_docs_sites={},
        analytics_enabled=False,
        store_backend_defaults=runtime["InMemoryStoreBackendDefaults"](init_temp_docs_sites=False),
    )

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=ResourceWarning,
            message="Implicitly cleaning up <TemporaryDirectory",
        )
        warnings.filterwarnings(
            "ignore",
            category=UserWarning,
            message=("`result_format` configured at the Validator-level will not be persisted"),
        )

        context = runtime["EphemeralDataContext"](project_config=config)
        project_manager = runtime["project_manager"]
        previous_project = project_manager.get_project()
        project_manager.set_project(context)

        try:
            validator = runtime["Validator"](
                execution_engine=runtime["PandasExecutionEngine"](),
                expectation_suite=runtime["ExpectationSuite"](name="hotpass"),
                batches=[runtime["Batch"](data=sanitized)],
                data_context=context,
            )
            validator.set_default_expectation_argument("catch_exceptions", True)

            validator.expect_column_values_to_not_be_null("organization_name")
            validator.expect_column_values_to_not_be_null("organization_slug")
            validator.expect_column_values_to_be_between(
                "data_quality_score", min_value=0.0, max_value=1.0, mostly=1.0
            )
            validator.expect_column_values_to_match_regex(
                "contact_primary_email",
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                mostly=email_mostly,
            )
            validator.expect_column_values_to_match_regex(
                "contact_primary_phone",
                r"^\+\d{6,}$",
                mostly=phone_mostly,
            )
            validator.expect_column_values_to_match_regex(
                "website", r"^https?://", mostly=website_mostly
            )
            validator.expect_column_values_to_be_in_set("country", {"South Africa"})
            allowed_statuses = {status.value for status in ValidationStatus}
            validator.expect_column_values_to_be_in_set(
                "contact_primary_email_status", allowed_statuses
            )
            validator.expect_column_values_to_be_in_set(
                "contact_primary_phone_status", allowed_statuses
            )
            validator.expect_column_values_to_be_between(
                "contact_primary_email_confidence",
                min_value=0.0,
                max_value=1.0,
                mostly=1.0,
            )
            validator.expect_column_values_to_be_between(
                "contact_primary_phone_confidence",
                min_value=0.0,
                max_value=1.0,
                mostly=1.0,
            )
            validator.expect_column_values_to_be_between(
                "contact_email_confidence_avg", min_value=0.0, max_value=1.0, mostly=1.0
            )
            validator.expect_column_values_to_be_between(
                "contact_phone_confidence_avg", min_value=0.0, max_value=1.0, mostly=1.0
            )
            validator.expect_column_values_to_be_between(
                "contact_verification_score_avg",
                min_value=0.0,
                max_value=1.0,
                mostly=1.0,
            )

            validation = validator.validate()
        finally:
            project_manager.set_project(previous_project)
            cleanup_manager = getattr(context, "_temp_dir_manager", None)
            if cleanup_manager is not None:
                exit_method = getattr(cleanup_manager, "__exit__", None)
                if callable(exit_method):
                    exit_method(None, None, None)
                elif hasattr(cleanup_manager, "cleanup"):
                    cleanup_manager.cleanup()

    failures: list[str] = []
    for result in validation.results:
        if result.success:
            continue
        expectation_config = cast(dict[str, Any], result.expectation_config)
        expectation = expectation_config.get("type", "unknown_expectation")
        kwargs = cast(dict[str, Any], expectation_config.get("kwargs", {}))
        column = kwargs.get("column")
        if column:
            expectation = f"{expectation} ({column})"
        ge_result = cast(dict[str, Any], result.result)
        unexpected = ge_result.get("unexpected_list") or ge_result.get("partial_unexpected_list")
        if unexpected:
            sample = list(unexpected)[:3]
            failures.append(f"{expectation}: unexpected {sample}")
        else:
            failures.append(str(expectation))

    return ExpectationSummary(success=bool(validation.success), failures=failures)


def build_ssot_schema() -> DataFrameSchema:
    def string_col(nullable: bool = True) -> Column:
        return Column(pa.String, nullable=nullable)

    return DataFrameSchema(
        {
            "organization_name": Column(pa.String, nullable=False),
            "organization_slug": Column(pa.String, nullable=False),
            "province": string_col(),
            "country": Column(pa.String, nullable=False),
            "area": string_col(),
            "address_primary": string_col(),
            "organization_category": string_col(),
            "organization_type": string_col(),
            "status": string_col(),
            "website": string_col(),
            "planes": string_col(),
            "description": string_col(),
            "notes": string_col(),
            "source_datasets": Column(pa.String, nullable=False),
            "source_record_ids": Column(pa.String, nullable=False),
            "contact_primary_name": string_col(),
            "contact_primary_role": string_col(),
            "contact_primary_email": string_col(),
            "contact_primary_phone": string_col(),
            "contact_primary_email_confidence": Column(pa.Float, nullable=True),
            "contact_primary_email_status": string_col(),
            "contact_primary_phone_confidence": Column(pa.Float, nullable=True),
            "contact_primary_phone_status": string_col(),
            "contact_primary_lead_score": Column(pa.Float, nullable=True),
            "contact_validation_flags": string_col(),
            "contact_secondary_emails": string_col(),
            "contact_secondary_phones": string_col(),
            "contact_email_confidence_avg": Column(pa.Float, nullable=True),
            "contact_phone_confidence_avg": Column(pa.Float, nullable=True),
            "contact_verification_score_avg": Column(pa.Float, nullable=True),
            "contact_lead_score_avg": Column(pa.Float, nullable=True),
            "data_quality_score": Column(pa.Float, nullable=False),
            "data_quality_flags": Column(pa.String, nullable=False),
            "selection_provenance": Column(pa.String, nullable=False),
            "last_interaction_date": string_col(),
            "priority": string_col(),
            "privacy_basis": Column(pa.String, nullable=False),
        },
        coerce=True,
        name="hotpass_ssot",
    )


def run_expectations(
    df: pd.DataFrame,
    *,
    email_mostly: float = 0.85,
    phone_mostly: float = 0.85,
    website_mostly: float = 0.85,
) -> ExpectationSummary:
    sanitized = df.copy()
    contact_columns = [
        "contact_primary_email",
        "contact_primary_phone",
        "website",
    ]
    for column in contact_columns:
        sanitized[column] = (
            sanitized[column]
            .astype(str)
            .replace(r"^\s*$", pd.NA, regex=True)
            .where(sanitized[column].notna(), pd.NA)
        )

    ge_summary = _run_with_great_expectations(
        sanitized,
        email_mostly=email_mostly,
        phone_mostly=phone_mostly,
        website_mostly=website_mostly,
        runtime_override=None,
    )
    if ge_summary is not None:
        return ge_summary

    # Manual fallback when lightweight GE dataset API is unavailable.
    failures: list[str] = []
    success = True

    def _record_failure(condition: bool, message: str) -> None:
        nonlocal success
        if not condition:
            success = False
            failures.append(message)

    _record_failure(sanitized["organization_name"].notna().all(), "organization_name nulls")
    _record_failure(sanitized["organization_slug"].notna().all(), "organization_slug nulls")
    _record_failure(
        sanitized["data_quality_score"].between(0.0, 1.0).all(),
        "data_quality_score bounds",
    )

    def _record_mostly(series: pd.Series, pattern: str, mostly: float, message: str) -> None:
        relevant = series.dropna()
        if relevant.empty:
            return
        matches = relevant.astype(str).str.match(pattern)
        success_ratio = float(matches.mean())
        if success_ratio >= mostly:
            return
        _record_failure(
            False,
            f"{message} success_rate={success_ratio:.0%} threshold={mostly:.0%}",
        )

    _record_mostly(
        sanitized["contact_primary_email"],
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        email_mostly,
        "contact_primary_email format",
    )
    _record_mostly(
        sanitized["contact_primary_phone"],
        r"^\+\d{6,}$",
        phone_mostly,
        "contact_primary_phone format",
    )
    _record_mostly(sanitized["website"], r"^https?://", website_mostly, "website scheme")

    _record_failure((sanitized["country"] == "South Africa").all(), "country constraint")
    allowed_statuses = {status.value for status in ValidationStatus}
    _record_failure(
        sanitized["contact_primary_email_status"].dropna().isin(allowed_statuses).all(),
        "contact_primary_email_status set",
    )
    _record_failure(
        sanitized["contact_primary_phone_status"].dropna().isin(allowed_statuses).all(),
        "contact_primary_phone_status set",
    )
    for column in (
        "contact_primary_email_confidence",
        "contact_primary_phone_confidence",
        "contact_email_confidence_avg",
        "contact_phone_confidence_avg",
        "contact_verification_score_avg",
    ):
        if column in sanitized:
            series = sanitized[column].dropna()
            if not series.empty:
                _record_failure(
                    series.between(0.0, 1.0).all(),
                    f"{column} bounds",
                )

    return ExpectationSummary(success=success, failures=failures)
