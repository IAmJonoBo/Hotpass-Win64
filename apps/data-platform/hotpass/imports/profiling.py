from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
import math
import re

import pandas as pd


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", re.IGNORECASE)
PHONE_REGEX = re.compile(r"^[\d\-\+\(\)\s]{5,}$")


@dataclass(slots=True)
class Issue:
    """Describes a problem or observation discovered during profiling."""

    severity: str  # info|warning|error
    message: str
    code: str | None = None
    column: str | None = None


@dataclass(slots=True)
class ColumnProfile:
    name: str
    inferred_type: str
    confidence: float
    null_fraction: float
    distinct_values: int
    sample_values: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


@dataclass(slots=True)
class SheetProfile:
    name: str
    rows: int
    columns: list[ColumnProfile]
    sample_rows: list[dict[str, Any]]
    role: str = "unknown"
    join_keys: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


@dataclass(slots=True)
class ProfileResult:
    workbook: str
    sheets: list[SheetProfile]
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workbook": self.workbook,
            "sheets": [_sheet_to_dict(sheet) for sheet in self.sheets],
            "issues": [_issue_to_dict(issue) for issue in self.issues],
        }


def profile_workbook(
    workbook_path: Path,
    *,
    sample_rows: int = 5,
    max_rows_per_sheet: int | None = None,
) -> ProfileResult:
    """Profile an Excel workbook, inferring column types and quality metrics."""

    issues: list[Issue] = []
    sheets: list[SheetProfile] = []

    if not workbook_path.exists():
        issues.append(Issue("error", f"Workbook not found: {workbook_path}", code="file_not_found"))
        return ProfileResult(workbook=str(workbook_path), sheets=[], issues=issues)

    try:
        excel = pd.ExcelFile(workbook_path, engine="openpyxl")
    except Exception as exc:  # pragma: no cover - depends on file system
        issues.append(Issue("error", f"Unable to open workbook: {exc}", code="open_failed"))
        return ProfileResult(workbook=str(workbook_path), sheets=[], issues=issues)

    if not excel.sheet_names:
        issues.append(Issue("warning", "Workbook has no sheets", code="empty_workbook"))
        return ProfileResult(workbook=str(workbook_path), sheets=[], issues=issues)

    for sheet_name in excel.sheet_names:
        sheet_issues: list[Issue] = []
        try:
            sheet_df = excel.parse(sheet_name=sheet_name)
            if max_rows_per_sheet is not None and len(sheet_df) > max_rows_per_sheet:
                sheet_df = sheet_df.head(max_rows_per_sheet)
                sheet_issues.append(
                    Issue(
                        "info",
                        f"Row count truncated to {max_rows_per_sheet} for profiling",
                        code="row_truncated",
                    )
                )
        except Exception as exc:  # pragma: no cover - depends on input data
            sheet_issues.append(
                Issue("error", f"Failed to read sheet: {exc}", code="sheet_read_failed")
            )
            sheets.append(
                SheetProfile(
                    name=sheet_name,
                    rows=0,
                    columns=[],
                    sample_rows=[],
                    issues=sheet_issues,
                )
            )
            continue

        column_profiles: list[ColumnProfile] = []
        for column in sheet_df.columns:
            column_profile = _profile_column(column, sheet_df[column])
            column_profiles.append(column_profile)

        if sample_rows > 0:
            sample_df = sheet_df.head(sample_rows)
            sample_records = sample_df.map(_safe_string).to_dict(orient="records")
        else:
            sample_records = []

        role = _classify_sheet(sheet_df.columns.astype(str))
        join_keys = _infer_join_keys(sheet_df.columns.astype(str))

        sheets.append(
            SheetProfile(
                name=sheet_name,
                rows=int(sheet_df.shape[0]),
                columns=column_profiles,
                sample_rows=sample_records,
                role=role,
                join_keys=join_keys,
                issues=sheet_issues,
            )
        )

    return ProfileResult(workbook=str(workbook_path), sheets=sheets, issues=issues)


def _profile_column(name: str, series: pd.Series) -> ColumnProfile:
    non_null = series.dropna()
    null_fraction = float(series.isna().mean()) if len(series) else 0.0
    distinct_values = int(non_null.nunique(dropna=True))
    sample_values = [_safe_string(value) for value in non_null.head(5)]

    inferred_type, confidence, type_issues = _infer_type(non_null)

    issues: list[Issue] = []
    issues.extend(type_issues)

    if null_fraction > 0.5 and non_null.size:
        issues.append(
            Issue(
                "warning",
                f"{null_fraction:.0%} null values detected",
                column=name,
                code="high_null_fraction",
            )
        )

    if distinct_values == 0 and non_null.empty:
        issues.append(
            Issue(
                "info",
                "Column is entirely empty",
                column=name,
                code="empty_column",
            )
        )

    return ColumnProfile(
        name=name,
        inferred_type=inferred_type,
        confidence=confidence,
        null_fraction=null_fraction,
        distinct_values=distinct_values,
        sample_values=sample_values,
        issues=issues,
    )


def _infer_type(series: pd.Series) -> tuple[str, float, list[Issue]]:
    """Return inferred type, confidence, and any issues."""

    issues: list[Issue] = []
    if series.empty:
        return "unknown", 0.0, issues

    # Coerce to str for regex tests
    as_str = series.astype(str)

    # Email detection
    email_matches = as_str.str.match(EMAIL_REGEX, na=False)
    email_ratio = float(email_matches.mean()) if len(email_matches) else 0.0
    if email_ratio >= 0.8:
        if email_ratio < 1.0:
            issues.append(
                Issue(
                    "warning",
                    f"{(1 - email_ratio):.0%} of values do not match email format",
                    code="email_mismatch",
                )
            )
        return "email", email_ratio, issues

    # Phone detection
    phone_matches = as_str.str.match(PHONE_REGEX, na=False)
    phone_ratio = float(phone_matches.mean())
    if phone_ratio >= 0.8:
        return "phone", phone_ratio, issues

    # Datetime detection
    datetime_series = pd.to_datetime(series, errors="coerce")
    datetime_ratio = float(datetime_series.notna().mean())
    if datetime_ratio >= 0.7:
        if datetime_ratio < 1.0:
            issues.append(
                Issue(
                    "warning",
                    f"{(1 - datetime_ratio):.0%} of values could not be parsed as datetime",
                    code="datetime_mismatch",
                )
            )
        return "datetime", datetime_ratio, issues

    # Numeric detection
    numeric_series = pd.to_numeric(series, errors="coerce")
    numeric_ratio = float(numeric_series.notna().mean())
    if numeric_ratio >= 0.7:
        if numeric_ratio < 1.0:
            issues.append(
                Issue(
                    "warning",
                    f"{(1 - numeric_ratio):.0%} of values are non-numeric",
                    code="numeric_mismatch",
                )
            )
        return "number", numeric_ratio, issues

    # Categorical detection (few unique values)
    unique_ratio = float(series.nunique(dropna=True) / max(len(series), 1))
    if unique_ratio < 0.1:
        return "category", 0.6, issues

    # Default to string
    return "string", 0.5, issues


def _issue_to_dict(issue: Issue) -> dict[str, Any]:
    return asdict(issue)


def _sheet_to_dict(sheet: SheetProfile) -> dict[str, Any]:
    return {
        "name": sheet.name,
        "rows": sheet.rows,
        "columns": [
            {
                "name": column.name,
                "inferred_type": column.inferred_type,
                "confidence": column.confidence,
                "null_fraction": column.null_fraction,
                "distinct_values": column.distinct_values,
                "sample_values": column.sample_values,
                "issues": [_issue_to_dict(issue) for issue in column.issues],
            }
            for column in sheet.columns
        ],
        "sample_rows": sheet.sample_rows,
        "role": sheet.role,
        "join_keys": sheet.join_keys,
        "issues": [_issue_to_dict(issue) for issue in sheet.issues],
    }


def _classify_sheet(columns: Iterable[str]) -> str:
    lowered = [str(col).strip().lower() for col in columns]
    meaningful = [name for name in lowered if name and not name.startswith("unnamed")]
    if not meaningful:
        return "reference"

    contains = lambda keyword: any(keyword in name for name in meaningful)

    if contains("email") and (contains("phone") or contains("cell") or contains("contact")):
        return "contacts"
    if contains("address") or contains("airport"):
        return "addresses"
    if contains("note") or contains("issue") or contains("comments"):
        return "notes"
    transactional_hints = {"order", "invoice", "amount", "captured"}
    if any(any(hint in name for hint in transactional_hints) for name in meaningful):
        return "transactions"
    reference_hints = {"category", "status", "priority", "lookup", "code"}
    if len(meaningful) <= 4 and all(
        any(hint in name for hint in reference_hints) for name in meaningful
    ):
        return "reference"
    return "master"


def _infer_join_keys(columns: Iterable[str]) -> list[str]:
    join_keys = []
    for name in columns:
        lowered = str(name).strip().lower()
        if not lowered:
            continue
        if lowered in {"id", "identifier", "record id"}:
            join_keys.append(name)
            continue
        if lowered.endswith("_id") or lowered.endswith(" id"):
            join_keys.append(name)
            continue
        if lowered in {"c_id", "company id", "organisation id", "organization id"}:
            join_keys.append(name)
    return join_keys


def _safe_string(value: Any) -> str:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if value is None:
        return ""
    return str(value)
