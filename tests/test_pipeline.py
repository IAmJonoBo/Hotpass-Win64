from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

pytest.importorskip("frictionless")

import hotpass.quality as quality  # noqa: E402
from hotpass.data_sources import ExcelReadOptions
from hotpass.enrichment.intent import (
    IntentCollectorDefinition,  # noqa: E402
    IntentPlan,
    IntentTargetDefinition,
)
from hotpass.pipeline import (
    PIPELINE_EVENT_AGGREGATE_COMPLETED,  # noqa: E402
    PIPELINE_EVENT_AGGREGATE_PROGRESS,
    PIPELINE_EVENT_COMPLETED,
    PIPELINE_EVENT_LOAD_STARTED,
    PIPELINE_EVENT_START,
    PIPELINE_EVENT_WRITE_COMPLETED,
    SSOT_COLUMNS,
    PIIRedactionConfig,
    PipelineConfig,
    PipelineResult,
    _aggregate_group,
    run_pipeline,
)


def test_pipeline_generates_refined_dataset(tmp_path: Path, sample_data_dir: Path) -> None:
    output_path = tmp_path / "refined.xlsx"
    config = PipelineConfig(
        input_dir=sample_data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )

    result: PipelineResult = run_pipeline(config)

    assert output_path.exists(), "Pipeline should persist refined workbook"
    refined = result.refined

    assert list(refined.columns) == SSOT_COLUMNS
    assert len(refined) == 2

    aero_record = refined.loc[refined["organization_name"] == "Aero School"].iloc[0]
    assert aero_record["contact_primary_email"] == "jane.doe@aero.example"
    assert aero_record["contact_primary_phone"] == "+27821234567"
    assert aero_record["website"] == "https://aero.example"
    assert aero_record["province"] == "Gauteng"
    assert aero_record["data_quality_score"] == pytest.approx(1.0, abs=0.01)
    assert "Reachout Database" in aero_record["source_datasets"]
    assert aero_record["last_interaction_date"] == "2025-03-10"

    selection_raw = aero_record["selection_provenance"]
    assert isinstance(selection_raw, str)
    provenance = json.loads(selection_raw)
    assert provenance["website"]["source_dataset"] == "SACAA Cleaned"
    assert provenance["contact_primary_email"]["source_dataset"] == "SACAA Cleaned"
    assert provenance["province"]["source_dataset"] == "SACAA Cleaned"
    assert provenance["contact_primary_phone"]["source_dataset"] == "SACAA Cleaned"

    report = result.quality_report
    assert report.total_records == 2
    assert report.invalid_records == 0
    assert report.expectations_passed
    assert report.schema_validation_errors == []


def test_pipeline_redacts_sensitive_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_data_dir: Path
) -> None:
    output_path = tmp_path / "redacted.xlsx"
    config = PipelineConfig(
        input_dir=sample_data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        pii_redaction=PIIRedactionConfig(
            columns=("contact_primary_email", "contact_primary_phone"),
            operator="replace",
            operator_params={"new_value": "[REDACTED]"},
            capture_entity_scores=False,
        ),
    )

    class _StubDetector:
        analyzer = object()
        anonymizer = object()

        def detect_pii(
            self, text: str, language: str = "en", threshold: float = 0.5
        ) -> list[dict[str, Any]]:
            if "@" in text:
                return [{"entity_type": "EMAIL_ADDRESS", "score": 0.99}]
            if text.startswith("+"):
                return [{"entity_type": "PHONE_NUMBER", "score": 0.95}]
            return []

        def anonymize_text(
            self,
            text: str,
            operation: str = "replace",
            language: str = "en",
            operator_params: dict[str, Any] | None = None,
        ) -> str:
            if operator_params and "new_value" in operator_params:
                return str(operator_params["new_value"])
            return "[REDACTED]"

    monkeypatch.setattr("hotpass.compliance.PIIDetector", lambda: _StubDetector())

    result = run_pipeline(config)
    aero_record = result.refined.loc[result.refined["organization_name"] == "Aero School"].iloc[0]

    assert aero_record["contact_primary_email"] == "[REDACTED]"
    assert aero_record["contact_primary_phone"] == "[REDACTED]"
    assert result.performance_metrics.get("redacted_cells", 0) == len(result.pii_redaction_events)
    assert any(event["column"] == "contact_primary_email" for event in result.pii_redaction_events)
    assert any(event["column"] == "contact_primary_phone" for event in result.pii_redaction_events)


def test_pipeline_flags_records_with_missing_contact(sample_data_dir: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "refined.xlsx"
    config = PipelineConfig(
        input_dir=sample_data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )
    result = run_pipeline(config)
    heli = result.refined.loc[result.refined["organization_name"] == "Heli Ops"].iloc[0]

    assert heli["contact_primary_email"] == "kelly@heliops.example"
    assert heli["contact_secondary_emails"] == "ops@heliops.example"
    assert heli["data_quality_score"] < 1.0
    assert "missing_website" in heli["data_quality_flags"].split(";")
    assert heli["last_interaction_date"] == "2025-02-18"

    heli_selection_raw = heli["selection_provenance"]
    assert isinstance(heli_selection_raw, str)
    provenance = json.loads(heli_selection_raw)
    assert provenance["contact_primary_email"]["source_dataset"] == "SACAA Cleaned"
    assert provenance["contact_primary_phone"]["source_dataset"] == "SACAA Cleaned"


def test_pipeline_exposes_performance_metrics(sample_data_dir: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "refined.xlsx"
    config = PipelineConfig(
        input_dir=sample_data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        excel_options=ExcelReadOptions(chunk_size=1),
        pii_redaction=PIIRedactionConfig(enabled=False),
    )

    result = run_pipeline(config)

    metrics = result.performance_metrics
    assert metrics["total_seconds"] >= 0.0
    assert metrics["load_seconds"] >= 0.0
    assert metrics["rows_per_second"] > 0.0
    assert metrics["polars_transform_seconds"] >= 0.0
    assert metrics["pandas_sort_seconds"] >= 0.0
    assert metrics["duckdb_sort_seconds"] >= 0.0
    assert metrics["polars_sort_speedup"] >= 0.0
    assert result.quality_report.performance_metrics["total_seconds"] == metrics["total_seconds"]


def test_pipeline_emits_progress_events(sample_data_dir: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "refined.xlsx"
    events: list[tuple[str, dict[str, Any]]] = []

    def listener(event: str, payload: dict[str, Any]) -> None:
        events.append((event, payload))

    config = PipelineConfig(
        input_dir=sample_data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        progress_listener=listener,
        pii_redaction=PIIRedactionConfig(enabled=False),
    )

    run_pipeline(config)

    event_names = [event for event, _ in events]
    assert PIPELINE_EVENT_START in event_names
    assert PIPELINE_EVENT_LOAD_STARTED in event_names
    assert PIPELINE_EVENT_AGGREGATE_PROGRESS in event_names
    assert PIPELINE_EVENT_AGGREGATE_COMPLETED in event_names
    assert PIPELINE_EVENT_WRITE_COMPLETED in event_names
    assert event_names[-1] == PIPELINE_EVENT_COMPLETED


def test_aggregate_group_prioritises_reliable_and_recent_values() -> None:
    slug = "aero-school"
    group = pd.DataFrame(
        [
            {
                "organization_name": "Aero School",
                "province": None,
                "area": None,
                "address": "Older Hangar",
                "category": "Flight School",
                "organization_type": "Flight School",
                "status": "Active",
                "website": "https://contact.example",
                "planes": None,
                "description": None,
                "notes": None,
                "priority": "Medium",
                "contact_names": ["Older Ops"],
                "contact_roles": ["Operations"],
                "contact_emails": ["ops@contact.example"],
                "contact_phones": ["+27820001111"],
                "source_dataset": "Contact Database",
                "source_record_id": "contact:1",
                "last_interaction_date": "2025-04-01",
            },
            {
                "organization_name": "Aero School",
                "province": "Gauteng",
                "area": "Gauteng",
                "address": "Hangar 1",
                "category": "Flight School",
                "organization_type": "Flight School",
                "status": "Active",
                "website": "https://reachout.example",
                "planes": None,
                "description": None,
                "notes": None,
                "priority": "High",
                "contact_names": ["Jane Doe"],
                "contact_roles": ["Head"],
                "contact_emails": ["jane.doe@reachout.example"],
                "contact_phones": ["+27825550000"],
                "source_dataset": "Reachout Database",
                "source_record_id": "reachout:1",
                "last_interaction_date": "2025-03-10",
            },
            {
                "organization_name": "Aero School",
                "province": "Gauteng",
                "area": "Gauteng",
                "address": "Hangar 1",
                "category": "Flight School",
                "organization_type": "Flight School",
                "status": "Active",
                "website": "https://reachout.example",
                "planes": None,
                "description": None,
                "notes": None,
                "priority": "Medium",
                "contact_names": ["Legacy Reachout"],
                "contact_roles": ["Ops"],
                "contact_emails": ["legacy@reachout.example"],
                "contact_phones": ["+27827777777"],
                "source_dataset": "Reachout Database",
                "source_record_id": "reachout:legacy",
                "last_interaction_date": "2024-01-01",
            },
            {
                "organization_name": "Aero School",
                "province": "Gauteng",
                "area": "Gauteng",
                "address": "Hangar 1",
                "category": "Flight School",
                "organization_type": "Flight School",
                "status": "Active",
                "website": "https://sacaa.example",
                "planes": None,
                "description": None,
                "notes": None,
                "priority": None,
                "contact_names": ["Regulator"],
                "contact_roles": ["Contact"],
                "contact_emails": ["info@sacaa.example"],
                "contact_phones": [],
                "source_dataset": "SACAA Cleaned",
                "source_record_id": "sacaa:1",
                "last_interaction_date": None,
            },
        ]
    )

    aggregated = _aggregate_group(
        slug,
        group.to_dict(orient="records"),
        country_code="ZA",
    )

    assert aggregated["website"] == "https://sacaa.example"
    assert aggregated["province"] == "Gauteng"
    assert aggregated["contact_primary_email"] == "info@sacaa.example"
    assert (
        aggregated["contact_secondary_emails"]
        == "jane.doe@reachout.example;legacy@reachout.example;ops@contact.example"
    )
    assert aggregated["contact_primary_phone"] == "+27825550000"
    assert aggregated["contact_secondary_phones"] == "+27827777777;+27820001111"
    aggregated_selection = aggregated["selection_provenance"]
    assert isinstance(aggregated_selection, str)
    provenance = json.loads(aggregated_selection)
    assert provenance["website"]["source_dataset"] == "SACAA Cleaned"
    website_provenance = provenance["website"]
    phone_provenance = provenance["contact_primary_phone"]
    assert website_provenance["source_priority"] >= phone_provenance["source_priority"]
    assert provenance["contact_primary_email"]["source_dataset"] == "SACAA Cleaned"
    assert provenance["contact_primary_phone"]["source_dataset"] == "Reachout Database"
    assert provenance["contact_primary_phone"]["last_interaction_date"] == "2025-03-10"


def test_run_expectations_fallback_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quality, "_GE_RUNTIME", None)

    df = pd.DataFrame(
        {
            "organization_name": ["Valid Org", "Blank Org"],
            "organization_slug": ["valid-org", "blank-org"],
            "data_quality_score": [0.9, 0.8],
            "contact_primary_email": ["valid@example.com", ""],
            "contact_primary_email_status": ["deliverable", None],
            "contact_primary_email_confidence": [0.92, None],
            "contact_primary_phone": ["+27123456789", ""],
            "contact_primary_phone_status": ["deliverable", None],
            "contact_primary_phone_confidence": [0.88, None],
            "website": ["https://valid.example", ""],
            "country": ["South Africa", "South Africa"],
            "contact_email_confidence_avg": [0.92, None],
            "contact_phone_confidence_avg": [0.88, None],
            "contact_verification_score_avg": [0.9, None],
        }
    )

    summary = quality.run_expectations(df)

    assert summary.success
    assert summary.failures == []


def test_run_expectations_fallback_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quality, "_GE_RUNTIME", None)

    df = pd.DataFrame(
        {
            "organization_name": ["Org A", "Org B"],
            "organization_slug": ["org-a", "org-b"],
            "data_quality_score": [0.7, 0.6],
            "contact_primary_email": ["invalid", "also_invalid"],
            "contact_primary_email_status": ["undeliverable", "risky"],
            "contact_primary_email_confidence": [0.2, 0.4],
            "contact_primary_phone": ["+27123456789", "+27123456780"],
            "contact_primary_phone_status": ["deliverable", "deliverable"],
            "contact_primary_phone_confidence": [0.9, 0.85],
            "website": ["https://org-a.example", "https://org-b.example"],
            "country": ["South Africa", "South Africa"],
            "contact_email_confidence_avg": [0.3, 0.4],
            "contact_phone_confidence_avg": [0.9, 0.85],
            "contact_verification_score_avg": [0.55, 0.62],
        }
    )

    summary = quality.run_expectations(df, email_mostly=0.9)

    assert not summary.success
    assert any("contact_primary_email format" in failure for failure in summary.failures)


def test_pipeline_handles_all_invalid_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test pipeline handles gracefully when all records fail schema validation."""
    # Patch the schema to reject ALL records
    import hotpass.pipeline as pipeline_module
    import pandera.pandas as pa
    from pandera.pandas import Check, Column, DataFrameSchema

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create valid data that will load successfully
    reachout_org = pd.DataFrame(
        {
            "Organisation Name": ["Valid School", "Good Org"],  # Valid names
            "ID": [1, 2],
            "Reachout Date": ["March 10, 2025", "2025-01-20"],
            "Recent_Touch_Ind": ["Y", "N"],
            "Area": ["Gauteng", "Western Cape"],
            "Distance": [0, 1200],
            "Type": ["Flight School", "Helicopter"],
            "Website": ["www.test1.example", "www.test2.example"],
            "Address": ["Address 1", "Address 2"],
            "Planes": ["Plane 1", "Plane 2"],
            "Description Type": ["Type 1", "Type 2"],
            "Notes": ["Note 1", "Note 2"],
            "Open Questions": ["Q1", "Q2"],
        }
    )
    reachout_contacts = pd.DataFrame(
        {
            "ID": [1, 2],
            "Organisation Name": ["Valid School", "Good Org"],
            "Reachout Date": ["2025-01-15", "2025-01-20"],
            "Firstname": ["John", "Jane"],
            "Surname": ["Doe", "Smith"],
            "Position": ["Manager", "Staff"],
            "Phone": ["082 123 4567", "082 765 4321"],
            "WhatsApp": ["0821234567", "0827654321"],
            "Email": ["john@test.com", "jane@test.com"],
            "Invalid": ["", ""],
            "Unnamed: 10": ["Validated", "Validated"],
        }
    )

    with pd.ExcelWriter(data_dir / "Reachout Database.xlsx") as writer:
        reachout_org.to_excel(writer, sheet_name="Organisation", index=False)
        reachout_contacts.to_excel(writer, sheet_name="Contact Info", index=False)

    def patched_build_schema():
        # Create a schema that will fail all records by requiring
        # organization_name to match an impossible pattern
        def string_col(nullable: bool = True) -> Column:
            return Column(pa.String, nullable=nullable)

        # Pattern that will never match any realistic organization name
        impossible_pattern = r"^IMPOSSIBLE_TEST_PATTERN_WILL_NEVER_MATCH_XYZ$"

        schema = DataFrameSchema(
            {
                "organization_name": Column(
                    pa.String,
                    nullable=False,
                    checks=Check(lambda s: s.str.match(impossible_pattern)),
                ),
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
                "contact_secondary_emails": string_col(),
                "contact_secondary_phones": string_col(),
                "data_quality_score": Column(pa.Float, nullable=False),
                "data_quality_flags": Column(pa.String, nullable=False),
                "selection_provenance": Column(pa.String, nullable=False),
                "last_interaction_date": string_col(),
                "priority": string_col(),
                "privacy_basis": Column(pa.String, nullable=False),
            },
            coerce=True,
            name="hotpass_ssot_all_fail",
        )
        return schema

    monkeypatch.setattr(pipeline_module, "build_ssot_schema", patched_build_schema)

    output_path = tmp_path / "output.xlsx"
    config = PipelineConfig(
        input_dir=data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )

    # Run pipeline - should not raise an error
    result = run_pipeline(config)

    # Verify the output file exists
    assert output_path.exists()
    output_df = pd.read_excel(output_path)

    # When all records fail validation, we should still write the data (with our fix)
    # Previously this would result in an empty file
    assert len(output_df) > 0, "Output should contain data when all fail validation"

    # Verify quality report reflects the issues
    assert len(result.quality_report.schema_validation_errors) > 0
    assert result.quality_report.total_records > 0


def test_pipeline_merges_intent_signals(tmp_path: Path, sample_data_dir: Path) -> None:
    output_path = tmp_path / "refined.xlsx"
    config = PipelineConfig(
        input_dir=sample_data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )

    plan = IntentPlan(
        enabled=True,
        collectors=(
            IntentCollectorDefinition(
                name="news",
                options={
                    "events": {
                        "aero-school": [
                            {
                                "headline": "Aero School secures defence contract",
                                "intent": 0.85,
                                "timestamp": "2025-10-25T08:00:00Z",
                                "url": "https://example.test/aero/contract",
                            }
                        ]
                    }
                },
            ),
        ),
        targets=(IntentTargetDefinition(identifier="Aero School", slug="aero-school"),),
    )
    config.intent_plan = plan
    config.intent_credentials = {"api_key": "stub"}  # pragma: allowlist secret

    result = run_pipeline(config)
    refined = result.refined

    aero = refined.loc[refined["organization_name"] == "Aero School"].iloc[0]
    assert aero["intent_signal_score"] >= 0.5
    assert "news" in (aero["intent_signal_types"] or "")
    assert result.intent_digest is not None
    assert not result.intent_digest.empty
    digest_match = result.intent_digest.loc[result.intent_digest["target_slug"] == "aero-school"]
    assert not digest_match.empty
    digest_score = digest_match["intent_signal_score"].iloc[0]
    assert digest_score == pytest.approx(aero["intent_signal_score"], rel=1e-6)


def test_pipeline_exports_daily_list_and_signal_store(
    tmp_path: Path, sample_data_dir: Path
) -> None:
    output_path = tmp_path / "refined.xlsx"
    signal_store_path = tmp_path / "intent-signals.json"
    daily_list_path = tmp_path / "daily-list.csv"

    config = PipelineConfig(
        input_dir=sample_data_dir,
        output_path=output_path,
        expectation_suite_name="default",
        country_code="ZA",
        pii_redaction=PIIRedactionConfig(enabled=False),
        intent_signal_store_path=signal_store_path,
        daily_list_path=daily_list_path,
        daily_list_size=1,
    )

    plan = IntentPlan(
        enabled=True,
        collectors=(
            IntentCollectorDefinition(
                name="news",
                options={
                    "events": {
                        "aero-school": [
                            {
                                "headline": "Aero School secures defence contract",
                                "intent": 0.85,
                                "timestamp": "2025-10-25T08:00:00Z",
                                "url": "https://example.test/aero/contract",
                            }
                        ]
                    }
                },
            ),
            IntentCollectorDefinition(
                name="tech-adoption",
                options={
                    "events": {
                        "aero-school": [
                            {
                                "technology": "Telemetry Platform",
                                "intent": 0.7,
                                "timestamp": "2025-10-25T12:00:00Z",
                            }
                        ]
                    }
                },
            ),
        ),
        targets=(IntentTargetDefinition(identifier="Aero School", slug="aero-school"),),
        storage_path=signal_store_path,
    )
    config.intent_plan = plan
    config.intent_credentials = {"api_key": "stub"}  # pragma: allowlist secret

    result = run_pipeline(config)

    assert signal_store_path.exists()
    assert daily_list_path.exists()
    assert result.daily_list is not None
    assert result.daily_list.iloc[0]["organization_slug"] == "aero-school"
    assert "lead_score" in result.daily_list.columns
