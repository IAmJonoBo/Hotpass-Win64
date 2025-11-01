"""Utilities for scheduling and recording compliance verification cadences.

The verification cadence underpins POPIA, ISO 27001, and SOC 2 reporting.
It needs to be lightweight enough for quarterly execution while providing a
machine-readable log that downstream tooling (dashboards, evidence exports,
Prefect automations) can consume.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_FRAMEWORKS: tuple[str, ...] = ("POPIA", "ISO 27001", "SOC 2")
DEFAULT_CADENCE_DAYS = 90  # Roughly quarterly
DEFAULT_LOG_PATH = Path("data/compliance/verification-log.json")


@dataclass(slots=True)
class VerificationEntry:
    """Record of a single verification session."""

    framework: str
    run_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    reviewers: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "run_at": self.run_at.isoformat(),
            "reviewers": list(self.reviewers),
            "findings": list(self.findings),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VerificationEntry:
        run_at_raw = payload.get("run_at")
        if isinstance(run_at_raw, str):
            run_at = datetime.fromisoformat(run_at_raw)
            if run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=UTC)
        else:
            run_at = datetime.now(tz=UTC)
        reviewers = payload.get("reviewers", [])
        findings = payload.get("findings", [])
        notes = payload.get("notes")
        return cls(
            framework=str(payload.get("framework")),
            run_at=run_at.astimezone(UTC),
            reviewers=list(reviewers),
            findings=list(findings),
            notes=notes if isinstance(notes, str) else None,
        )


def _resolve_log_path(log_path: Path | None) -> Path:
    if log_path is None:
        log_path = DEFAULT_LOG_PATH
    return log_path


def load_verification_log(log_path: Path | None = None) -> list[VerificationEntry]:
    """Load verification entries from disk."""

    target = _resolve_log_path(log_path)
    if not target.exists():
        return []

    with target.open("r", encoding="utf-8") as handle:
        raw_payload = json.load(handle)

    if not isinstance(raw_payload, list):
        msg = "Verification log payload must be a list"
        raise ValueError(msg)

    entries: list[VerificationEntry] = []
    for item in raw_payload:
        if not isinstance(item, dict):
            continue
        entries.append(VerificationEntry.from_dict(item))
    return entries


def save_verification_log(
    entries: Iterable[VerificationEntry], log_path: Path | None = None
) -> Path:
    """Persist verification entries to disk."""

    target = _resolve_log_path(log_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialised = [entry.to_dict() for entry in entries]
    with target.open("w", encoding="utf-8") as handle:
        json.dump(serialised, handle, indent=2)
        handle.write("\n")
    return target


def record_verification_run(
    frameworks: Sequence[str] | None = None,
    *,
    reviewers: Sequence[str] | None = None,
    findings: Sequence[str] | None = None,
    notes: str | None = None,
    log_path: Path | None = None,
    timestamp: datetime | None = None,
) -> Path:
    """Append a verification run covering *frameworks* to the log."""

    current_entries = load_verification_log(log_path)
    timestamp = (timestamp or datetime.now(tz=UTC)).astimezone(UTC)
    reviewers_list = list(reviewers or [])
    findings_list = list(findings or [])
    frameworks = tuple(frameworks or DEFAULT_FRAMEWORKS)

    for framework in frameworks:
        entry = VerificationEntry(
            framework=framework,
            run_at=timestamp,
            reviewers=reviewers_list,
            findings=findings_list,
            notes=notes,
        )
        current_entries.append(entry)

    return save_verification_log(current_entries, log_path=log_path)


def _latest_run(entries: Iterable[VerificationEntry], framework: str) -> datetime | None:
    latest: datetime | None = None
    for entry in entries:
        if entry.framework.lower() != framework.lower():
            continue
        if latest is None or entry.run_at > latest:
            latest = entry.run_at
    return latest


def is_framework_due(
    framework: str,
    *,
    cadence_days: int = DEFAULT_CADENCE_DAYS,
    log_path: Path | None = None,
    now: datetime | None = None,
) -> bool:
    """Return True when a framework's verification is due."""

    entries = load_verification_log(log_path)
    latest = _latest_run(entries, framework)
    if latest is None:
        return True

    now = (now or datetime.now(tz=UTC)).astimezone(UTC)
    due_at = latest + timedelta(days=cadence_days)
    return now >= due_at


def frameworks_due(
    frameworks: Sequence[str] | None = None,
    *,
    cadence_days: int = DEFAULT_CADENCE_DAYS,
    log_path: Path | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Return frameworks whose verification cadence has elapsed."""

    frameworks = tuple(frameworks or DEFAULT_FRAMEWORKS)
    return [
        framework
        for framework in frameworks
        if is_framework_due(
            framework,
            cadence_days=cadence_days,
            log_path=log_path,
            now=now,
        )
    ]


def generate_summary(
    frameworks: Sequence[str] | None = None,
    *,
    cadence_days: int = DEFAULT_CADENCE_DAYS,
    log_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Generate a machine-friendly summary of verification status."""

    entries = load_verification_log(log_path)
    frameworks = tuple(frameworks or DEFAULT_FRAMEWORKS)
    now = (now or datetime.now(tz=UTC)).astimezone(UTC)

    summary: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "cadence_days": cadence_days,
        "frameworks": {},
    }
    for framework in frameworks:
        latest = _latest_run(entries, framework)
        if latest is None:
            summary["frameworks"][framework] = {
                "latest_run_at": None,
                "due": True,
                "reviewers": [],
                "findings": [],
                "notes": None,
            }
            continue

        # Collect the most recent entry details
        latest_entry = max(
            (entry for entry in entries if entry.framework.lower() == framework.lower()),
            key=lambda entry: entry.run_at,
        )
        summary["frameworks"][framework] = {
            "latest_run_at": latest_entry.run_at.isoformat(),
            "due": now >= latest_entry.run_at + timedelta(days=cadence_days),
            "reviewers": latest_entry.reviewers,
            "findings": latest_entry.findings,
            "notes": latest_entry.notes,
        }

    return summary


__all__ = [
    "DEFAULT_FRAMEWORKS",
    "DEFAULT_CADENCE_DAYS",
    "DEFAULT_LOG_PATH",
    "VerificationEntry",
    "load_verification_log",
    "save_verification_log",
    "record_verification_run",
    "is_framework_due",
    "frameworks_due",
    "generate_summary",
]
