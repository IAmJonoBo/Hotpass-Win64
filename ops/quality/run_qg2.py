#!/usr/bin/env python3
"""Run QG-2 (Data Quality) validations using Great Expectations sample workbooks."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from hotpass.error_handling import DataContractError

try:  # Great Expectations is an optional dependency
    from hotpass.validation import run_checkpoint
except RuntimeError as exc:  # pragma: no cover - handled at runtime
    RUN_CHECKPOINT_IMPORT_ERROR: RuntimeError | None = exc
else:
    RUN_CHECKPOINT_IMPORT_ERROR = None


@dataclass
class CheckpointSpec:
    """Configuration for a checkpoint run."""

    checkpoint_name: str
    workbook_name: str
    sheet_name: str


CHECKPOINTS: tuple[CheckpointSpec, ...] = (
    CheckpointSpec("reachout_organisation", "Reachout Database.xlsx", "Organisation"),
    CheckpointSpec("reachout_contact_info", "Reachout Database.xlsx", "Contact Info"),
    CheckpointSpec("sacaa_cleaned", "SACAA Flight Schools - Refined copy__CLEANED.xlsx", "Cleaned"),
    CheckpointSpec("contact_company_cat", "Contact Database.xlsx", "Company_Cat"),
    CheckpointSpec("contact_company_contacts", "Contact Database.xlsx", "Company_Contacts"),
    CheckpointSpec("contact_company_addresses", "Contact Database.xlsx", "Company_Addresses"),
    CheckpointSpec("contact_capture", "Contact Database.xlsx", "10-10-25 Capture"),
)


def _project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in (current,) + tuple(current.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Unable to locate project root (missing pyproject.toml)")


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute Great Expectations checkpoints for QG-2",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_project_root() / "data",
        help="Directory containing sample workbooks",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=_project_root() / "dist" / "quality-gates" / "qg2-data-quality",
        help="Directory where summaries and Data Docs are written",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="generic",
        help="Profile name (reserved for future filtering)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.artifacts_dir / timestamp
    docs_dir = run_dir / "data-docs"
    run_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    if RUN_CHECKPOINT_IMPORT_ERROR is not None:
        summary = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "artifacts_dir": str(run_dir),
            "data_docs": str(docs_dir),
            "profile": args.profile,
            "passed": False,
            "results": [],
            "error": f"Great Expectations not available: {RUN_CHECKPOINT_IMPORT_ERROR}",
        }
        _write_summary(run_dir / "summary.json", summary)
        _write_summary(args.artifacts_dir / "latest.json", summary)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("✗ QG-2 aborted: Great Expectations dependency missing")
        return 1

    results: list[dict[str, Any]] = []
    failures = 0

    for spec in CHECKPOINTS:
        workbook_path = args.data_dir / spec.workbook_name
        source_file = f"{spec.workbook_name}#{spec.sheet_name}"

        if not workbook_path.exists():
            failures += 1
            message = f"Workbook not found at {workbook_path}"
            results.append(
                {
                    "checkpoint": spec.checkpoint_name,
                    "workbook": spec.workbook_name,
                    "sheet": spec.sheet_name,
                    "status": "failed",
                    "rows": 0,
                    "message": message,
                }
            )
            continue

        try:
            df = pd.read_excel(workbook_path, sheet_name=spec.sheet_name)
        except Exception as exc:  # pragma: no cover - defensive guard
            failures += 1
            results.append(
                {
                    "checkpoint": spec.checkpoint_name,
                    "workbook": spec.workbook_name,
                    "sheet": spec.sheet_name,
                    "status": "failed",
                    "rows": 0,
                    "message": f"Failed to load workbook: {exc}",
                }
            )
            continue

        try:
            validation_result = run_checkpoint(
                df,
                checkpoint_name=spec.checkpoint_name,
                source_file=source_file,
                data_docs_dir=docs_dir,
            )
            message = (
                "Validation passed" if validation_result.success else "Validation reported failure"
            )
            results.append(
                {
                    "checkpoint": spec.checkpoint_name,
                    "workbook": spec.workbook_name,
                    "sheet": spec.sheet_name,
                    "status": "passed" if validation_result.success else "failed",
                    "rows": len(df),
                    "message": message,
                }
            )
            if not validation_result.success:
                failures += 1
        except DataContractError as exc:
            failures += 1
            results.append(
                {
                    "checkpoint": spec.checkpoint_name,
                    "workbook": spec.workbook_name,
                    "sheet": spec.sheet_name,
                    "status": "failed",
                    "rows": len(df),
                    "message": exc.context.message,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            failures += 1
            results.append(
                {
                    "checkpoint": spec.checkpoint_name,
                    "workbook": spec.workbook_name,
                    "sheet": spec.sheet_name,
                    "status": "failed",
                    "rows": len(df),
                    "message": f"Unexpected error: {exc}",
                }
            )

    docs_count = sum(1 for _ in docs_dir.rglob("*.html"))

    summary = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "artifacts_dir": str(run_dir),
        "data_docs": str(docs_dir),
        "profile": args.profile,
        "passed": failures == 0,
        "stats": {
            "total": len(results),
            "passed": sum(1 for item in results if item["status"] == "passed"),
            "failed": failures,
            "docs_html_files": docs_count,
        },
        "results": results,
    }

    _write_summary(run_dir / "summary.json", summary)
    _write_summary(args.artifacts_dir / "latest.json", summary)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for item in results:
            status = "PASS" if item["status"] == "passed" else "FAIL"
            print(f"{status}: {item['checkpoint']} ({item['workbook']}#{item['sheet']})")
            print(f"  {item['message']}")
        doc_summary = summary["stats"]["docs_html_files"]
        print(
            f"Data Docs location: {summary['data_docs']} ({doc_summary} HTML files)",
        )
        if summary["passed"]:
            print("✓ QG-2 succeeded")
        else:
            print("✗ QG-2 failed")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
