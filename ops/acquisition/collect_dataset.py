"""CLI entry point for compliant dataset acquisition with provenance logging."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .guardrails import CollectionGuards, ProvenanceLedger, RobotsTxtGuard, TermsOfServicePolicy

DEFAULT_LEDGER = Path("data/ledgers/acquisition.jsonl")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        type=Path,
        required=True,
        help="JSONL file containing records to log",
    )
    parser.add_argument(
        "--source-url",
        required=True,
        help="Source URL for provenance tracking",
    )
    parser.add_argument(
        "--license",
        required=True,
        help="License identifier for the dataset",
    )
    parser.add_argument(
        "--robots",
        required=True,
        help="robots.txt location (URL or local path)",
    )
    parser.add_argument(
        "--tos-path",
        type=Path,
        required=True,
        help="Path to terms-of-service text to hash",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_LEDGER,
        help="Path to append-only provenance ledger",
    )
    parser.add_argument(
        "--user-agent",
        default="HotpassDataCollector",
        help="User agent for robots.txt evaluation",
    )
    return parser


def load_records(path: Path) -> list[tuple[str, dict[str, object]]]:
    records: list[tuple[str, dict[str, object]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            record_id = str(payload.get("id", index))
            metadata = {k: v for k, v in payload.items() if k != "id"}
            records.append((record_id, metadata))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    tos_policy = TermsOfServicePolicy.from_path(args.tos_path)
    robots_guard = RobotsTxtGuard(args.robots, user_agent=args.user_agent)
    ledger = ProvenanceLedger(args.ledger)

    guards = CollectionGuards(robots_guard=robots_guard, ledger=ledger, tos_policy=tos_policy)

    records = load_records(args.records)
    guards.guard_many(records, source_url=args.source_url, license=args.license)

    print(f"Logged {len(records)} records to {args.ledger}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
