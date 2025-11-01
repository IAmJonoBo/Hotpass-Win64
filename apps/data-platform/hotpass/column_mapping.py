"""Intelligent column detection and mapping utilities."""

from __future__ import annotations

import re
import warnings
from difflib import SequenceMatcher
from typing import Any

import pandas as pd


class ColumnMapper:
    """Maps source columns to target schema using intelligent matching."""

    def __init__(self, target_schema: dict[str, list[str]]) -> None:
        """
        Initialize mapper with target schema and synonyms.

        Args:
            target_schema: Dictionary mapping target column names to lists of synonyms
        """
        self.target_schema = target_schema
        self._normalize_cache: dict[str, str] = {}

    def _normalize_column_name(self, column: str) -> str:
        """Normalize column name for matching."""
        if column in self._normalize_cache:
            return self._normalize_cache[column]

        # Convert to lowercase
        normalized = column.lower()

        # Remove special characters and extra spaces
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip()

        # Cache result
        self._normalize_cache[column] = normalized
        return normalized

    def _calculate_similarity(self, source: str, target: str) -> float:
        """Calculate similarity score between two strings."""
        return SequenceMatcher(None, source, target).ratio()

    def _find_best_match(
        self, source_column: str, target_column: str, synonyms: list[str]
    ) -> tuple[str | None, float]:
        """Find best matching synonym for a source column."""
        normalized_source = self._normalize_column_name(source_column)

        # Check exact match with target
        if normalized_source == self._normalize_column_name(target_column):
            return target_column, 1.0

        # Check exact match with synonyms
        for synonym in synonyms:
            if normalized_source == self._normalize_column_name(synonym):
                return synonym, 1.0

        # Calculate similarity scores
        best_match = None
        best_score = 0.0

        for candidate in [target_column] + synonyms:
            score = self._calculate_similarity(
                normalized_source, self._normalize_column_name(candidate)
            )
            if score > best_score:
                best_score = score
                best_match = candidate

        return best_match, best_score

    def map_columns(
        self, source_columns: list[str], confidence_threshold: float = 0.7
    ) -> dict[str, Any]:
        """
        Map source columns to target schema.

        Args:
            source_columns: List of column names from source data
            confidence_threshold: Minimum confidence score for automatic mapping

        Returns:
            Dictionary with mapping results including:
            - mapped: Dict of source -> target mappings (high confidence)
            - suggestions: Dict of source -> [(target, score)] (medium confidence)
            - unmapped: List of source columns that couldn't be mapped
        """
        mapped: dict[str, str] = {}
        suggestions: dict[str, list[tuple[str, float]]] = {}
        unmapped: list[str] = []

        for source_col in source_columns:
            best_target = None
            best_score = 0.0

            # Try to match against each target column
            for target_col, synonyms in self.target_schema.items():
                match_name, score = self._find_best_match(source_col, target_col, synonyms)

                if score > best_score:
                    best_score = score
                    best_target = target_col

            # Categorize based on confidence
            if best_score >= confidence_threshold and best_target is not None:
                mapped[source_col] = best_target
            elif best_score >= 0.5 and best_target is not None:
                # Medium confidence - suggest to user
                if source_col not in suggestions:
                    suggestions[source_col] = []
                suggestions[source_col].append((best_target, best_score))
            else:
                unmapped.append(source_col)

        return {
            "mapped": mapped,
            "suggestions": suggestions,
            "unmapped": unmapped,
        }

    def apply_mapping(self, df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
        """
        Apply column mapping to a DataFrame.

        Args:
            df: Source DataFrame
            mapping: Dictionary mapping source column names to target names

        Returns:
            DataFrame with renamed columns
        """
        # Only rename columns that exist in the DataFrame
        valid_mapping = {src: tgt for src, tgt in mapping.items() if src in df.columns}

        return df.rename(columns=valid_mapping)


def infer_column_types(df: pd.DataFrame) -> dict[str, str]:
    """
    Infer semantic types for DataFrame columns.

    Returns dictionary mapping column names to inferred types like:
    'email', 'phone', 'url', 'date', 'numeric', 'text', 'categorical'
    """
    column_types: dict[str, str] = {}

    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    phone_pattern = re.compile(r"^[\d\s\+\-\(\)]+$")
    url_pattern = re.compile(r"^https?://|www\.")

    for column in df.columns:
        # Skip if all null
        if df[column].isna().all():
            column_types[column] = "empty"
            continue

        # Get sample of non-null values
        sample = df[column].dropna().head(100).astype(str)

        if len(sample) == 0:
            column_types[column] = "empty"
            continue

        # Check for email pattern
        email_matches = sum(1 for val in sample if email_pattern.match(val.strip()))
        if email_matches / len(sample) > 0.7:
            column_types[column] = "email"
            continue

        # Check for phone pattern
        phone_matches = sum(
            1 for val in sample if phone_pattern.match(val.strip()) and len(val.strip()) >= 7
        )
        if phone_matches / len(sample) > 0.7:
            column_types[column] = "phone"
            continue

        # Check for URL pattern
        url_matches = sum(1 for val in sample if url_pattern.search(val.lower()))
        if url_matches / len(sample) > 0.7:
            column_types[column] = "url"
            continue

        # Check if it's a date
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    category=UserWarning,
                    message=("Could not infer format, so each element will be parsed individually"),
                )
                parsed_dates = pd.to_datetime(sample, errors="coerce")
            if parsed_dates.notna().sum() / len(sample) > 0.7:
                column_types[column] = "date"
                continue
        except (ValueError, TypeError):
            pass

        # Check if numeric
        try:
            pd.to_numeric(sample, errors="coerce")
            if sample.notna().sum() / len(sample) > 0.7:
                column_types[column] = "numeric"
                continue
        except (ValueError, TypeError):
            pass

        # Check if categorical (low cardinality)
        unique_ratio = len(df[column].unique()) / len(df[column])
        if unique_ratio < 0.1:
            column_types[column] = "categorical"
        else:
            column_types[column] = "text"

    return column_types


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """
    Generate a comprehensive profile of a DataFrame.

    Returns statistics and insights about the data including:
    - Row count
    - Column count
    - Memory usage
    - Missing value statistics
    - Inferred column types
    - Duplicate records
    """
    profile: dict[str, Any] = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
        "columns": {},
    }

    # Analyze each column
    for column in df.columns:
        col_profile = {
            "dtype": str(df[column].dtype),
            "missing_count": int(df[column].isna().sum()),
            "missing_percentage": float(df[column].isna().sum() / len(df) * 100),
            "unique_count": int(df[column].nunique()),
            "unique_percentage": float(df[column].nunique() / len(df) * 100),
        }

        # Add sample values (non-null)
        sample_values = df[column].dropna().head(3).tolist()
        col_profile["sample_values"] = [str(v) for v in sample_values]

        profile["columns"][column] = col_profile

    # Check for duplicates
    profile["duplicate_rows"] = int(df.duplicated().sum())
    profile["duplicate_percentage"] = float(df.duplicated().sum() / len(df) * 100)

    # Infer column types
    profile["inferred_types"] = infer_column_types(df)

    return profile
