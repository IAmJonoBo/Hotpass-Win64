"""Column mapping utilities regression tests."""

from __future__ import annotations

import pandas as pd
from hotpass.column_mapping import ColumnMapper, infer_column_types, profile_dataframe

from tests.helpers.assertions import expect


def test_map_columns_groups_confidence_buckets() -> None:
    mapper = ColumnMapper(
        {
            "organization_name": ["company name", "org name"],
            "contact_email": ["email", "primary email"],
            "province": ["state"],
        }
    )

    result = mapper.map_columns(
        ["Company Name", "Email address", "Region"], confidence_threshold=0.8
    )

    expect(
        result["mapped"].get("Company Name") == "organization_name",
        "Exact synonym should be mapped above threshold",
    )
    expect(
        "Email address" in result["suggestions"],
        "Similar column should surface as suggestion when below threshold",
    )
    expect(
        result["unmapped"] == ["Region"],
        "Unknown columns should be marked as unmapped",
    )


def test_apply_mapping_only_renames_present_columns() -> None:
    df = pd.DataFrame(
        {
            "Company": ["Acme"],
            "Phone": ["123"],
        }
    )

    mapper = ColumnMapper({"organization_name": ["company"]})
    renamed = mapper.apply_mapping(df, {"Company": "organization_name", "Email": "contact_email"})

    expect("organization_name" in renamed.columns, "Mapped column should be renamed")
    expect("Email" not in renamed.columns, "Missing source columns must be ignored")


def test_infer_column_types_detects_common_patterns() -> None:
    size = 30
    df = pd.DataFrame(
        {
            "emails": [f"user{i}@example.com" for i in range(size)],
            "phones": ["+27 21 123 4567"] * size,
            "urls": ["https://hotpass.example"] * size,
            "numbers": [str(i) for i in range(size)],
            "dates": ["2024-01-01"] * size,
            "categories": ["A"] * (size - 1) + ["B"],
            "notes": ["Some text"] * size,
        }
    )

    inferred = infer_column_types(df)

    expect(inferred["emails"] == "email", "Email column should be detected")
    expect(inferred["phones"] == "phone", "Phone column should be detected")
    expect(inferred["urls"] == "url", "URL column should be detected")
    expect(
        set(inferred) == set(df.columns),
        "All columns should be represented in inferred types",
    )


def test_profile_dataframe_reports_statistics() -> None:
    df = pd.DataFrame(
        {
            "organization_name": ["Acme", "Acme"],
            "contact_email": ["user@example.com", None],
        }
    )

    profile = profile_dataframe(df)

    expect(profile["row_count"] == 2, "Row count should match input")
    expect(profile["duplicate_rows"] == 0, "Duplicate rows should reflect exact matches")
    expect(
        profile["columns"]["contact_email"]["missing_count"] == 1,
        "Missing values should be counted",
    )
    expect(
        profile["inferred_types"].get("organization_name") is not None,
        "Profile should capture inferred type for organization name",
    )
