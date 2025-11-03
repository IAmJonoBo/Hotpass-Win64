from __future__ import annotations

import pandas as pd
import pytest

from tests.helpers.assertions import expect

pytest.importorskip("frictionless")

from hotpass.validation import validate_with_frictionless


def test_validate_with_frictionless_deduplicates_primary_key() -> None:
    frame = pd.DataFrame(
        {
            "Name of Organisation": ["Alpha Flight", "Alpha Flight", "Beta Flyers"],
            "Province": ["GAU", "GAU", "WC"],
            "Status": ["Approved", "Approved", "Approved"],
            "Website URL": [
                "https://alpha.example",
                "https://alpha.example",
                "https://beta.example",
            ],
            "Contact Person": ["Jane", "Jane", "Ben"],
            "Contact Number": ["123", "123", "456"],
            "Contact Email Address": [
                "ops@alpha.example",
                "ops@alpha.example",
                "info@beta.example",
            ],
        }
    )

    validate_with_frictionless(
        frame,
        schema_descriptor="sacaa_cleaned.schema.json",
        table_name="SACAA Cleaned",
        source_file="test.xlsx#Cleaned",
    )

    expect(len(frame) == 2, "Duplicate primary keys should be deduplicated")
    notices = frame.attrs.get("contract_notices", [])
    expect(len(notices) == 1, "A contract notice should be recorded")
    notice = notices[0]
    expect(
        notice["duplicate_count"] == 2,
        "Notice should record the number of duplicate rows",
    )
    expect(
        notice["primary_key"] == ["Name of Organisation"],
        "Notice should include the primary key",
    )
    expect(
        "Alpha Flight" in notice.get("sample_keys", []),
        "Notice should include the duplicate key preview",
    )
    duplicate_rows = notice.get("duplicate_rows")
    expect(
        isinstance(duplicate_rows, pd.DataFrame) and not duplicate_rows.empty,
        "Duplicate rows should be attached for downstream artefacts",
    )
