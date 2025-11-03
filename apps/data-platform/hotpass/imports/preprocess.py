from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from .profiling import Issue


def apply_import_preprocessing(config, frame: pd.DataFrame) -> tuple[pd.DataFrame, list[Issue]]:
    """
    Apply configured column mappings and remediation rules to the ingested frame.

    Parameters
    ----------
    config : PipelineConfig-like object with import_mappings/import_rules attributes.
    frame : pandas.DataFrame

    Returns
    -------
    (DataFrame, list[Issue])
    """

    issues: list[Issue] = []
    result = frame.copy()

    mappings = getattr(config, "import_mappings", []) or []
    if mappings:
        rename_map: dict[str, str] = {}
        for spec in mappings:
            source = _as_string(spec.get("source"))
            target = _as_string(spec.get("target"))
            if not source or not target:
                issues.append(
                    Issue(
                        "warning",
                        f"Ignoring invalid mapping specification: {spec!r}",
                        code="invalid_mapping",
                    )
                )
                continue
            if source not in result.columns:
                issues.append(
                    Issue(
                        "warning",
                        f"Source column '{source}' not present",
                        column=source,
                        code="mapping_missing_source",
                    )
                )
                continue
            rename_map[source] = target
            default_value = spec.get("default")
            if default_value is not None:
                result[source] = result[source].fillna(default_value)
            if spec.get("strip", False):
                result[source] = result[source].astype(str).str.strip()
            transform = spec.get("transform")
            if transform == "lower":
                result[source] = result[source].astype(str).str.lower()
            elif transform == "upper":
                result[source] = result[source].astype(str).str.upper()
        if rename_map:
            result = result.rename(columns=rename_map)

        # Drop columns flagged for removal after rename
        for spec in mappings:
            if spec.get("drop"):
                target = _as_string(spec.get("target")) or _as_string(spec.get("source"))
                if target in result.columns:
                    result = result.drop(columns=[target])
                    issues.append(
                        Issue(
                            "info",
                            f"Dropped column '{target}' per import configuration",
                            column=target,
                            code="column_dropped",
                        )
                    )

    rules = getattr(config, "import_rules", []) or []
    for rule in rules:
        rule_type = _as_string(rule.get("type"))
        if not rule_type:
            issues.append(
                Issue("warning", f"Ignoring rule without type: {rule!r}", code="invalid_rule")
            )
            continue
        handler = _RULE_HANDLERS.get(rule_type)
        if handler is None:
            issues.append(Issue("warning", f"Unknown rule type '{rule_type}'", code="unknown_rule"))
            continue
        try:
            result, rule_issues = handler(result, rule)
            issues.extend(rule_issues)
        except Exception as exc:  # pragma: no cover - defensive
            issues.append(Issue("error", f"Rule '{rule_type}' failed: {exc}", code="rule_failed"))

    return result, issues


def _handle_fill_missing(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    columns = _ensure_iterable(spec.get("columns"))
    value = spec.get("value", "")
    for column in columns:
        if column not in frame.columns:
            issues.append(
                Issue(
                    "warning",
                    f"fill_missing skipped missing column '{column}'",
                    column=column,
                    code="fill_missing_missing_column",
                )
            )
            continue
        before = frame[column].isna().sum()
        frame[column] = frame[column].fillna(value)
        after = frame[column].isna().sum()
        if before > after:
            issues.append(
                Issue(
                    "info",
                    f"Filled {before - after} null values in '{column}'",
                    column=column,
                    code="fill_missing_applied",
                )
            )
    return frame, issues


def _handle_lowercase(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    columns = _ensure_iterable(spec.get("columns"))
    for column in columns:
        if column not in frame.columns:
            issues.append(
                Issue(
                    "warning",
                    f"lowercase skipped missing column '{column}'",
                    column=column,
                    code="lowercase_missing_column",
                )
            )
            continue
        frame[column] = frame[column].astype(str).str.lower()
        issues.append(
            Issue("info", f"Lowercased column '{column}'", column=column, code="lowercase_applied")
        )
    return frame, issues


def _handle_strip_whitespace(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    columns = _ensure_iterable(spec.get("columns"))
    for column in columns:
        if column not in frame.columns:
            issues.append(
                Issue(
                    "warning",
                    f"strip_whitespace skipped missing column '{column}'",
                    column=column,
                    code="strip_missing_column",
                )
            )
            continue
        frame[column] = frame[column].astype(str).str.strip()
        issues.append(
            Issue("info", f"Trimmed whitespace for '{column}'", column=column, code="strip_applied")
        )
    return frame, issues


def _handle_dedupe(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    subset = _ensure_iterable(spec.get("subset"))
    if not subset:
        return frame, issues
    missing = [column for column in subset if column not in frame.columns]
    if missing:
        issues.append(
            Issue(
                "warning",
                f"dedupe skipped; missing columns {missing}",
                code="dedupe_missing_columns",
            )
        )
        return frame, issues
    before = len(frame)
    frame = frame.drop_duplicates(subset=subset, keep="first")
    dropped = before - len(frame)
    if dropped > 0:
        issues.append(
            Issue(
                "info", f"Removed {dropped} duplicate rows based on {subset}", code="dedupe_applied"
            )
        )
    return frame, issues


def _handle_drop_rows(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    columns = _ensure_iterable(spec.get("columns"))
    if not columns:
        return frame, issues
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        issues.append(
            Issue(
                "warning",
                f"drop_rows skipped; missing columns {missing}",
                code="drop_rows_missing_columns",
            )
        )
        return frame, issues
    before = len(frame)
    frame = frame.dropna(subset=columns)
    dropped = before - len(frame)
    if dropped > 0:
        issues.append(
            Issue(
                "info",
                f"Dropped {dropped} rows missing values in {columns}",
                code="drop_rows_applied",
            )
        )
    return frame, issues


def _handle_rename_columns(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    mapping = spec.get("mapping") or {}
    if not isinstance(mapping, Mapping):
        return frame, [
            Issue(
                "warning", "rename_columns mapping must be an object", code="rename_invalid_mapping"
            )
        ]
    rename_map: dict[str, str] = {}
    issues: list[Issue] = []
    for source, target in mapping.items():
        source_str = _as_string(source)
        target_str = _as_string(target)
        if not source_str or not target_str:
            issues.append(
                Issue(
                    "warning",
                    f"rename_columns skipped invalid pair {source}->{target}",
                    code="rename_invalid_pair",
                )
            )
            continue
        if source_str not in frame.columns:
            issues.append(
                Issue(
                    "warning",
                    f"rename_columns missing source column '{source_str}'",
                    column=source_str,
                    code="rename_missing_source",
                )
            )
            continue
        rename_map[source_str] = target_str
    if rename_map:
        frame = frame.rename(columns=rename_map)
        issues.append(
            Issue("info", f"Renamed columns: {rename_map}", code="rename_columns_applied")
        )
    return frame, issues


def _handle_normalize_date(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    columns = _ensure_iterable(spec.get("columns"))
    issues: list[Issue] = []
    if not columns:
        return frame, issues
    fmt = spec.get("format")
    errors = spec.get("errors", "coerce")
    for column in columns:
        if column not in frame.columns:
            issues.append(
                Issue(
                    "warning",
                    f"normalize_date skipped missing column '{column}'",
                    column=column,
                    code="normalize_date_missing_column",
                )
            )
            continue
        before_na = frame[column].isna().sum()
        parsed = pd.to_datetime(frame[column], format=fmt, errors=errors)
        frame[column] = parsed.dt.strftime(spec.get("output_format", "%Y-%m-%d"))
        after_na = frame[column].isna().sum()
        if after_na > before_na:
            issues.append(
                Issue(
                    "warning",
                    f"normalize_date introduced {after_na - before_na} nulls for '{column}'",
                    column=column,
                    code="normalize_date_added_nulls",
                )
            )
        else:
            issues.append(
                Issue(
                    "info",
                    f"normalize_date applied to column '{column}'",
                    column=column,
                    code="normalize_date_applied",
                )
            )
    return frame, issues


def _handle_drop_layout_rows(
    frame: pd.DataFrame, spec: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[Issue]]:
    leading_columns = _ensure_iterable(spec.get("columns"))
    patterns = [
        str(p).strip().lower()
        for p in _ensure_iterable(spec.get("patterns") or ["#", "total", "overview"])
    ]
    issues: list[Issue] = []
    if not leading_columns:
        leading_columns = [frame.columns[0]] if len(frame.columns) else []
    drop_mask = pd.Series(False, index=frame.index)
    for column in leading_columns:
        if column not in frame.columns:
            issues.append(
                Issue(
                    "warning",
                    f"drop_layout_rows skipped missing column '{column}'",
                    column=column,
                    code="drop_layout_missing_column",
                )
            )
            continue
        series = frame[column].astype(str).str.strip().str.lower()
        mask = series.isin({"", "nan"}) | series.isnull()
        for pattern in patterns:
            mask |= series.str.startswith(pattern, na=False)
        drop_mask |= mask
    dropped = int(drop_mask.sum())
    if dropped > 0:
        frame = frame.loc[~drop_mask].reset_index(drop=True)
        issues.append(
            Issue("info", f"Dropped {dropped} layout rows", code="drop_layout_rows_applied")
        )
    return frame, issues


_RULE_HANDLERS: dict[str, Any] = {
    "fill_missing": _handle_fill_missing,
    "lowercase": _handle_lowercase,
    "strip_whitespace": _handle_strip_whitespace,
    "dedupe": _handle_dedupe,
    "drop_rows": _handle_drop_rows,
    "rename_columns": _handle_rename_columns,
    "normalize_date": _handle_normalize_date,
    "drop_layout_rows": _handle_drop_layout_rows,
}


def _ensure_iterable(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _as_string(value: Any) -> str | None:
    if value is None:
        return None
    stringified = str(value).strip()
    return stringified or None


__all__ = ["apply_import_preprocessing"]
