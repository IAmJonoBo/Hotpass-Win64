"""CLI helper to record a compliance verification run."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from hotpass.compliance_verification import (
    DEFAULT_FRAMEWORKS,
    frameworks_due,
    generate_summary,
    record_verification_run,
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--framework",
        "-f",
        dest="frameworks",
        action="append",
        choices=sorted(DEFAULT_FRAMEWORKS),
        help="Framework(s) to record (default: all frameworks)",
    )
    parser.add_argument(
        "--reviewer",
        "-r",
        dest="reviewers",
        action="append",
        help="Reviewer(s) who performed the verification",
    )
    parser.add_argument(
        "--finding",
        dest="findings",
        action="append",
        help="Finding(s) captured during verification",
    )
    parser.add_argument(
        "--notes",
        dest="notes",
        help="Additional context or next actions",
    )
    parser.add_argument(
        "--log-path",
        dest="log_path",
        type=Path,
        default=None,
        help="Path to the verification log (default: data/compliance/verification-log.json)",
    )
    parser.add_argument(
        "--timestamp",
        dest="timestamp",
        type=str,
        default=None,
        help="ISO8601 timestamp for the verification run (default: now)",
    )
    parser.add_argument(
        "--summary",
        dest="summary",
        type=Path,
        default=None,
        help="Optional path to write the JSON summary output",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    timestamp = (
        datetime.fromisoformat(args.timestamp).replace(tzinfo=UTC)
        if args.timestamp
        else datetime.now(tz=UTC)
    )

    log_path = record_verification_run(
        frameworks=args.frameworks,
        reviewers=args.reviewers,
        findings=args.findings,
        notes=args.notes,
        log_path=args.log_path,
        timestamp=timestamp,
    )

    summary = generate_summary(log_path=log_path, now=timestamp)
    due = frameworks_due(
        args.frameworks or DEFAULT_FRAMEWORKS,
        log_path=log_path,
        now=timestamp,
    )

    print(f"Recorded verification run at {timestamp.isoformat()} for log {log_path}")
    if due:
        print("Frameworks still due immediately:", ", ".join(due))
    else:
        print("All selected frameworks are within cadence thresholds.")

    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
