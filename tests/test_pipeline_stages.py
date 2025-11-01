from __future__ import annotations

import json
from pathlib import Path

import pytest
from hotpass.compliance import PIIRedactionConfig
from hotpass.pipeline.aggregation import aggregate_records
from hotpass.pipeline.config import PipelineConfig
from hotpass.pipeline.ingestion import ingest_sources

pytest.importorskip("frictionless")


def _make_config(sample_data_dir: Path, tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        input_dir=sample_data_dir,
        output_path=tmp_path / "refined.xlsx",
        expectation_suite_name="default",
        country_code="ZA",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )


def test_ingest_sources_normalises_inputs(sample_data_dir: Path, tmp_path: Path) -> None:
    config = _make_config(sample_data_dir, tmp_path)

    combined, timings, warnings = ingest_sources(config)

    assert set(combined["source_dataset"].unique()) == {
        "Contact Database",
        "Reachout Database",
        "SACAA Cleaned",
    }
    assert {slug for slug in combined["organization_slug"].unique() if slug} == {
        "aero-school",
        "heli-ops",
    }
    aero_rows = combined[combined["organization_name"] == "Aero School"]
    assert {value for value in aero_rows["province"].unique() if value} == {
        "Gauteng",
    }
    assert warnings == []
    assert set(timings) >= {
        "Contact Database",
        "Reachout Database",
        "SACAA Cleaned",
    }


def test_aggregate_records_prioritises_high_quality_data(
    sample_data_dir: Path, tmp_path: Path
) -> None:
    config = _make_config(sample_data_dir, tmp_path)
    combined, _, _ = ingest_sources(config)

    events: list[tuple[str, dict[str, object]]] = []

    def _notify(event: str, payload: dict[str, object]) -> None:
        events.append((event, payload))

    result = aggregate_records(
        config,
        combined,
        intent_summaries=None,
        notify_progress=_notify,
    )

    assert any(event == "aggregate_started" for event, _ in events)
    assert any(event == "aggregate_completed" for event, _ in events)

    refined = result.refined_df
    assert list(refined["organization_name"]) == ["Aero School", "Heli Ops"]

    aero = refined.loc[refined["organization_name"] == "Aero School"].iloc[0]
    datasets = {part.strip() for part in str(aero["source_datasets"]).split(";") if part}
    assert datasets == {"Contact Database", "Reachout Database", "SACAA Cleaned"}
    assert aero["contact_primary_email"] == "jane.doe@aero.example"
    assert "ops@aero.example" in str(aero["contact_secondary_emails"])

    provenance = json.loads(str(aero["selection_provenance"]))
    assert provenance["contact_primary_email"]["source_dataset"] == "SACAA Cleaned"

    assert result.source_breakdown == {
        "Contact Database": 2,
        "Reachout Database": 2,
        "SACAA Cleaned": 2,
    }
    assert result.metrics["aggregation_seconds"] >= 0.0
