from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("frictionless")

from hotpass.evidence import record_consent_audit_log, record_export_access_event  # noqa: E402


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_record_consent_audit_log_deterministic(tmp_path):
    """Consent audit logging accepts a deterministic clock for reproducible tests."""

    fixed_time = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

    def _clock() -> datetime:
        return fixed_time

    path = record_consent_audit_log(
        {"status": "ok"},
        base_dir=tmp_path,
        run_id="run-42",
        clock=_clock,
    )

    expect(
        path.name == "consent_audit_run-42_20250101T120000Z.json",
        "Audit file name should include run and timestamp",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    expect(
        payload["recorded_at"] == fixed_time.isoformat(),
        "Recorded timestamp should match injected clock",
    )
    expect(payload["run_id"] == "run-42", "Run id should persist")
    expect(payload["report"] == {"status": "ok"}, "Report payload should round-trip")


def test_record_export_access_event_deterministic(tmp_path):
    """Export access logging accepts deterministic timestamps and digests."""

    output_file = tmp_path / "refined.xlsx"
    output_file.write_bytes(b"data")

    fixed_time = datetime(2025, 1, 2, 6, 30, tzinfo=UTC)

    def _clock() -> datetime:
        return fixed_time

    log_path = record_export_access_event(
        output_file,
        total_records=3,
        log_dir=tmp_path / "logs",
        context={"task": "prefect"},
        clock=_clock,
    )

    expect(
        log_path.parent == tmp_path / "logs",
        "Export log should land in provided directory",
    )
    expect(
        log_path.name == "export_access_20250102T063000Z.json",
        "Log name should embed timestamp",
    )

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    expect(
        payload["recorded_at"] == fixed_time.isoformat(),
        "Recorded timestamp should match injected clock",
    )
    expect(payload["total_records"] == 3, "Total records should be persisted")
    # pragma: allowlist nextline secret
    expected_sha = "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7"
    expect(payload["sha256"] == expected_sha, "SHA256 digest should match input data")
    expect(payload["context"] == {"task": "prefect"}, "Context metadata should persist")
    expect(
        payload["output_path"] == str(output_file.resolve()),
        "Output path should be absolute",
    )
