"""Tests for the compliance verification cadence helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.helpers.fixtures import fixture

pytest.importorskip("frictionless")

from hotpass.compliance_verification import (
    DEFAULT_FRAMEWORKS,  # noqa: E402
    frameworks_due,
    generate_summary,
    is_framework_due,
    load_verification_log,
    record_verification_run,
)

from tests.helpers.assertions import expect


@fixture()
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "verification-log.json"


def test_framework_due_when_no_history(log_path: Path) -> None:
    """Without history the framework should be due immediately."""

    expect(load_verification_log(log_path) == [], "No history should return empty log")
    expect(
        is_framework_due("POPIA", log_path=log_path) is True,
        "Framework should be due when no run history exists",
    )


def test_record_run_marks_framework_not_due_until_next_quarter(log_path: Path) -> None:
    """Recording a run should reset the cadence window for all frameworks."""

    timestamp = datetime(2024, 10, 1, tzinfo=UTC)
    record_verification_run(
        frameworks=("POPIA", "SOC 2"),
        reviewers=("Alice", "Bob"),
        findings=("Consent logs reviewed",),
        notes="Quarterly verification completed",
        log_path=log_path,
        timestamp=timestamp,
    )

    ninety_days_later = timestamp + timedelta(days=90)
    soon_after = timestamp + timedelta(days=1)
    expect(
        is_framework_due("POPIA", log_path=log_path, now=soon_after) is False,
        "Recorded run should mark POPIA as not due immediately afterwards",
    )
    expect(
        is_framework_due("SOC 2", log_path=log_path, now=soon_after) is False,
        "Recorded run should mark SOC 2 as not due immediately afterwards",
    )
    expect(
        is_framework_due("ISO 27001", log_path=log_path, now=soon_after) is True,
        "Frameworks not included in run should remain due",
    )
    expect(
        is_framework_due("POPIA", log_path=log_path, now=ninety_days_later) is True,
        "POPIA should become due again after cadence interval elapses",
    )


def test_generate_summary_reflects_latest_run(log_path: Path) -> None:
    """The summary should surface the last reviewers and findings per framework."""

    ts = datetime(2024, 1, 15, tzinfo=UTC)
    record_verification_run(
        frameworks=DEFAULT_FRAMEWORKS,
        reviewers=("Alice",),
        findings=("Updated evidence catalog", "Verified DSAR backlog"),
        notes="Cadence executed",
        log_path=log_path,
        timestamp=ts,
    )

    summary = generate_summary(log_path=log_path, now=ts + timedelta(days=10))
    framework_summary = summary["frameworks"]["POPIA"]
    expect(
        framework_summary["due"] is False,
        "Framework should not be due within cadence window",
    )
    expect(
        framework_summary["reviewers"] == ["Alice"],
        "Summary should capture latest reviewers",
    )
    expect(
        "Updated evidence catalog" in framework_summary["findings"],
        "Findings should include recorded evidence string",
    )
    expect(
        framework_summary["notes"] == "Cadence executed",
        "Summary notes should echo recorded notes",
    )

    # Move past the cadence window and ensure due flips to True
    overdue_summary = generate_summary(log_path=log_path, now=ts + timedelta(days=200))
    expect(
        overdue_summary["frameworks"]["POPIA"]["due"] is True,
        "Framework should be due once cadence window has elapsed",
    )


def test_frameworks_due_handles_case_insensitivity(log_path: Path) -> None:
    """Framework lookups should not be case-sensitive."""

    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    record_verification_run(frameworks=("popia",), log_path=log_path, timestamp=timestamp)

    due_frameworks = frameworks_due(
        ("POPIA",), log_path=log_path, now=timestamp + timedelta(days=30)
    )
    expect(due_frameworks == [], "Framework should not be due within cadence window")
    due_frameworks = frameworks_due(
        ("POPIA",), log_path=log_path, now=timestamp + timedelta(days=120)
    )
    expect(
        due_frameworks == ["POPIA"],
        "Framework should become due after cadence interval",
    )
