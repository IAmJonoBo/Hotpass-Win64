"""Regression tests for governed ingest schemas and validation pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.helpers.fixtures import fixture

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("frictionless")

from hotpass.error_handling import HotpassError  # noqa: E402
from hotpass.pipeline import PipelineConfig, run_pipeline  # noqa: E402


@fixture()
def sample_workbooks(tmp_path: Path) -> Path:
    """Create minimal but valid ingest workbooks in a temporary directory."""
    reachout = tmp_path / "Reachout Database.xlsx"
    contact = tmp_path / "Contact Database.xlsx"
    sacaa = tmp_path / "SACAA Flight Schools - Refined copy__CLEANED.xlsx"

    with pd.ExcelWriter(reachout) as writer:
        pd.DataFrame(
            [
                {
                    "Organisation Name": "Test Org",
                    "ID": 1,
                    "Reachout Date": "2024-01-15",
                    "Recent_Touch_Ind": "Y",
                    "Area": "Gauteng",
                    "Distance": "0",
                    "Type": "Flight School",
                    "Website": "https://example.com",
                    "Address": "123 Street",
                    "Planes": "1",
                    "Description Type": "Primary",
                    "Notes": "Note",
                    "Open Questions": "None",
                }
            ]
        ).to_excel(writer, sheet_name="Organisation", index=False)
        pd.DataFrame(
            [
                {
                    "ID": 1,
                    "Organisation Name": "Test Org",
                    "Reachout Date": "2024-01-15",
                    "Firstname": "Jane",
                    "Surname": "Doe",
                    "Position": "Owner",
                    "Phone": "+27123456789",
                    "WhatsApp": "+27123456789",
                    "Email": "jane@example.com",
                    "Invalid": "N",
                    "Unnamed: 10": None,
                }
            ]
        ).to_excel(writer, sheet_name="Contact Info", index=False)

    with pd.ExcelWriter(contact) as writer:
        pd.DataFrame(
            [
                {
                    "C_ID": 1,
                    "Company": "Test Org",
                    "QuickNooks_Name": "Quick",
                    "Last_Order_Date": "2024-02-01",
                    "Category": "Flight",
                    "Strat": "A",
                    "Priority": "High",
                    "Status": "Active",
                    "LoadDate": "2024-02-02",
                    "Checked": "Y",
                    "Website": "https://example.com",
                }
            ]
        ).to_excel(writer, sheet_name="Company_Cat", index=False)
        pd.DataFrame(
            [
                {
                    "C_ID": 1,
                    "Company": "Test Org",
                    "Status": "Active",
                    "FirstName": "Jane",
                    "Surname": "Doe",
                    "Position": "Owner",
                    "Cellnumber": "+27123456789",
                    "Email": "jane@example.com",
                    "Landline": "+27876543210",
                }
            ]
        ).to_excel(writer, sheet_name="Company_Contacts", index=False)
        pd.DataFrame(
            [
                {
                    "C_ID": 1,
                    "Company": "Test Org",
                    "Type": "HQ",
                    "Airport": "ORT",
                    "Unnamed: 4": "Hangar 1",
                }
            ]
        ).to_excel(writer, sheet_name="Company_Addresses", index=False)
        pd.DataFrame(
            [
                {
                    "Unnamed: 0": 1,
                    "School": "Test Org",
                    "Contact person (role)": "Jane",
                    "Phone": "+27123456789",
                    "Email": "jane@example.com",
                    "Addresses": "123 Street",
                    "Planes": "1",
                    "Website": "https://example.com",
                    "Description": "Flight",
                    "Type": "Flight School",
                }
            ]
        ).to_excel(writer, sheet_name="10-10-25 Capture", index=False)

    with pd.ExcelWriter(sacaa) as writer:
        pd.DataFrame(
            [
                {
                    "Name of Organisation": "Test Org",
                    "Province": "Gauteng",
                    "Status": "Active",
                    "Website URL": "https://example.com",
                    "Contact Person": "Jane Doe",
                    "Contact Number": "+27123456789",
                    "Contact Email Address": "jane@example.com",
                }
            ]
        ).to_excel(writer, sheet_name="Cleaned", index=False)

    return tmp_path


def test_pipeline_valid_payload_creates_contract_artifacts(
    sample_workbooks: Path, tmp_path: Path
) -> None:
    output_path = tmp_path / "refined.xlsx"
    config = PipelineConfig(
        input_dir=sample_workbooks,
        output_path=output_path,
        enable_formatting=False,
    )
    result = run_pipeline(config)

    assert output_path.exists(), "expected Excel export"
    parquet_path = output_path.with_suffix(".parquet")
    assert parquet_path.exists(), "validated parquet snapshot missing"

    # DuckDB can read the parquet snapshot without errors and return a record
    with duckdb.connect() as conn:
        query = "SELECT COUNT(*) AS total FROM read_parquet(?)"
        frame = conn.execute(query, [str(parquet_path)]).fetch_df()
    assert int(frame.loc[0, "total"]) == 1

    assert result.quality_report.expectations_passed is True
    assert not result.quality_report.schema_validation_errors


def test_pipeline_rejects_missing_required_column(sample_workbooks: Path, tmp_path: Path) -> None:
    # Remove a required column to trigger Frictionless schema failure
    reachout_path = sample_workbooks / "Reachout Database.xlsx"
    df = pd.read_excel(reachout_path, sheet_name="Organisation")
    df = df.drop(columns=["Organisation Name"])
    contact_sheet = pd.read_excel(reachout_path, sheet_name="Contact Info")
    with pd.ExcelWriter(reachout_path) as writer:
        df.to_excel(writer, sheet_name="Organisation", index=False)
        contact_sheet.to_excel(writer, sheet_name="Contact Info", index=False)

    config = PipelineConfig(
        input_dir=sample_workbooks,
        output_path=tmp_path / "refined.xlsx",
        enable_formatting=False,
    )

    with pytest.raises(HotpassError) as excinfo:
        run_pipeline(config)

    context = excinfo.value.context
    assert context.category.value == "schema_mismatch"
    assert "Organisation Name" in ";".join(context.details.get("missing_fields", []))


def test_pipeline_enforces_expectation_suite(sample_workbooks: Path, tmp_path: Path) -> None:
    # Introduce an invalid email to violate Great Expectations suite
    contact_path = sample_workbooks / "Contact Database.xlsx"
    contacts = pd.read_excel(contact_path, sheet_name="Company_Contacts")
    contacts.loc[0, "Email"] = "invalid-email"
    company_cat = pd.read_excel(contact_path, sheet_name="Company_Cat")
    addresses = pd.read_excel(contact_path, sheet_name="Company_Addresses")
    capture = pd.read_excel(contact_path, sheet_name="10-10-25 Capture")
    with pd.ExcelWriter(contact_path) as writer:
        company_cat.to_excel(writer, sheet_name="Company_Cat", index=False)
        contacts.to_excel(writer, sheet_name="Company_Contacts", index=False)
        addresses.to_excel(writer, sheet_name="Company_Addresses", index=False)
        capture.to_excel(writer, sheet_name="10-10-25 Capture", index=False)

    config = PipelineConfig(
        input_dir=sample_workbooks,
        output_path=tmp_path / "refined.xlsx",
        enable_formatting=False,
    )

    with pytest.raises(HotpassError) as excinfo:
        run_pipeline(config)

    context = excinfo.value.context
    assert context.category.value == "validation_failure"
    assert "email" in context.message.lower()
