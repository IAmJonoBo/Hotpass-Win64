"""CLI coverage for explain-provenance command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from tests.helpers.assertions import expect


def _write_sample_dataset(tmp_path: Path) -> Path:
    frame = pd.DataFrame(
        {
            "id": ["row-0", "row-1"],
            "organization_name": ["Test Org", "Sample Org"],
            "provenance_source": ["deterministic", "lookup"],
            "provenance_timestamp": ["2025-10-31T08:00:00Z", "2025-10-31T08:05:00Z"],
            "provenance_confidence": [0.9, 0.7],
            "provenance_strategy": ["offline-first", "offline-first"],
            "provenance_network_status": [
                "skipped: network disabled",
                "skipped: network disabled",
            ],
        }
    )
    dataset_path = tmp_path / "enriched.xlsx"
    frame.to_excel(dataset_path, index=False)
    return dataset_path


def test_explain_provenance_json_success(tmp_path: Path) -> None:
    dataset_path = _write_sample_dataset(tmp_path)
    result = subprocess.run(
        [
            "uv",
            "run",
            "hotpass",
            "explain-provenance",
            "--dataset",
            str(dataset_path),
            "--row-id",
            "0",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    expect(result.returncode == 0, f"explain-provenance should succeed: {result.stderr}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"CLI output must be JSON when --json passed: {exc}") from exc

    provenance = payload.get("provenance", {})
    expect(payload.get("success") is True, "Payload should indicate success")
    expect(
        provenance.get("provenance_source") == "deterministic",
        "Provenance source should match row",
    )
    expect(payload.get("organization_name") == "Test Org", "Should echo organization name")


def test_explain_provenance_row_not_found(tmp_path: Path) -> None:
    dataset_path = _write_sample_dataset(tmp_path)
    result = subprocess.run(
        [
            "uv",
            "run",
            "hotpass",
            "explain-provenance",
            "--dataset",
            str(dataset_path),
            "--row-id",
            "99",
        ],
        capture_output=True,
        text=True,
    )
    expect(result.returncode == 1, "Missing row should return non-zero exit code")
    expect(
        "Unable to locate row" in result.stdout,
        "CLI should explain that the row could not be located",
    )
