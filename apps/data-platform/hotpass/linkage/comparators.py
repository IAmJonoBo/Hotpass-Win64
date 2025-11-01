"""RapidFuzz-based comparators and preprocessing for linkage."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
from rapidfuzz import fuzz

from ..normalization import (
    clean_string,
    normalize_email,
    normalize_phone,
    normalize_province,
    normalize_website,
    slugify,
)

NAME_COLUMN = "organization_name"
PHONE_COLUMN = "contact_primary_phone"
EMAIL_COLUMN = "contact_primary_email"
WEBSITE_COLUMN = "website"
PROVINCE_COLUMN = "province"


def add_normalized_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of *df* with normalized helper columns."""

    working = df.copy()
    working["linkage_slug"] = working.get("organization_slug")
    working["linkage_slug"] = working["linkage_slug"].apply(slugify)

    def _norm_or_fallback(series: pd.Series, func: Callable[[str | None], str | None]) -> pd.Series:
        return series.apply(lambda value: func(value) if pd.notna(value) else None)

    working["linkage_name"] = working.get(NAME_COLUMN, pd.Series(dtype="object")).apply(
        lambda value: clean_string(value) or None
    )
    working["linkage_email"] = _norm_or_fallback(
        working.get(EMAIL_COLUMN, pd.Series(dtype="object")), normalize_email
    )
    working["linkage_phone"] = _norm_or_fallback(
        working.get(PHONE_COLUMN, pd.Series(dtype="object")), normalize_phone
    )
    working["linkage_website"] = _norm_or_fallback(
        working.get(WEBSITE_COLUMN, pd.Series(dtype="object")), normalize_website
    )
    working["linkage_province"] = _norm_or_fallback(
        working.get(PROVINCE_COLUMN, pd.Series(dtype="object")), normalize_province
    )
    working["linkage_slug"] = working["linkage_slug"].where(
        working["linkage_slug"].astype(bool),
        working["linkage_name"].apply(slugify),
    )
    working["linkage_name"] = working["linkage_name"].fillna("")

    # Maintain the legacy column names used by older rule-based linkage helpers.
    legacy_aliases = {
        "_linkage_slug": "linkage_slug",
        "_linkage_name": "linkage_name",
        "_linkage_email": "linkage_email",
        "_linkage_phone": "linkage_phone",
        "_linkage_website": "linkage_website",
        "_linkage_province": "linkage_province",
    }
    for legacy, target in legacy_aliases.items():
        working[legacy] = working[target]

    return working


def rapidfuzz_token_sort_ratio(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    return fuzz.token_sort_ratio(left, right) / 100.0


def rapidfuzz_partial_ratio(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    return fuzz.partial_ratio(left, right) / 100.0


def rapidfuzz_token_set_ratio(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    return fuzz.token_set_ratio(left, right) / 100.0


def register_duckdb_functions(api: object) -> None:
    """Register RapidFuzz helpers on a DuckDB connection or API wrapper."""

    register = getattr(api, "register_function", None)
    if register is None:
        create_function = getattr(api, "create_function", None)

        if create_function is None:
            return

        def register(name: str, func: Callable[[str | None, str | None], float]) -> None:
            create_function(name, func, return_type="DOUBLE")

    try:
        register("rapidfuzz_token_sort_ratio", rapidfuzz_token_sort_ratio)
        register("rapidfuzz_partial_ratio", rapidfuzz_partial_ratio)
        register("rapidfuzz_token_set_ratio", rapidfuzz_token_set_ratio)
    except Exception:  # pragma: no cover - fallback when UDF registration fails
        return
