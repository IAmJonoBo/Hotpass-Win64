"""Smart import utilities (profiling, mapping suggestions)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hotpass.imports import profile_workbook

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile


def register() -> CLICommand:
    return CLICommand(
        name="imports",
        help="Smart import tooling (profiling, mapping suggestions)",
        builder=_build,
        handler=_command_handler,
    )


def _build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "imports",
        help="Smart import utilities",
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.set_defaults(imports_action=None)

    action_subparsers = parser.add_subparsers(dest="imports_action")

    profile_parser = action_subparsers.add_parser(
        "profile",
        help="Analyse a workbook and infer schema information",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    profile_parser.add_argument(
        "--workbook",
        type=Path,
        required=True,
        help="Path to the workbook to profile",
    )
    profile_parser.add_argument(
        "--sample-rows",
        type=int,
        default=5,
        help="Number of sample rows to include in the response",
    )
    profile_parser.add_argument(
        "--max-rows",
        type=int,
        dest="max_rows",
        help="Limit the number of rows profiled per sheet (defaults to all rows)",
    )
    profile_parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the profiling result as JSON",
    )

    return parser


def _command_handler(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    if args.imports_action == "profile":
        return _handle_profile(args)
    print("No imports action specified. Use `hotpass imports profile --help` for usage.")
    return 1


def _handle_profile(args: argparse.Namespace) -> int:
    result = profile_workbook(
        args.workbook,
        sample_rows=args.sample_rows,
        max_rows_per_sheet=args.max_rows,
    )
    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)

    # Return non-zero when critical errors were recorded
    has_errors = any(issue.severity == "error" for issue in result.issues)
    if not has_errors:
        for sheet in result.sheets:
            if any(issue.severity == "error" for issue in sheet.issues):
                has_errors = True
                break
    return 1 if has_errors else 0
