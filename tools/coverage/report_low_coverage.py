"""Fail the build when modules fall below the required coverage thresholds."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

DEFAULT_MIN_LINES = 60.0
DEFAULT_MIN_BRANCHES = 50.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "coverage_xml",
        type=Path,
        help="Path to coverage XML output (e.g., coverage.xml)",
    )
    parser.add_argument(
        "--min-lines",
        type=float,
        default=DEFAULT_MIN_LINES,
        help="Minimum acceptable line coverage percentage (default: %(default)s)",
    )
    parser.add_argument(
        "--min-branches",
        type=float,
        default=DEFAULT_MIN_BRANCHES,
        help="Minimum acceptable branch coverage percentage (default: %(default)s)",
    )
    parser.add_argument(
        "--max-modules",
        type=int,
        default=10,
        help="Maximum number of offending modules to list before truncating output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.coverage_xml.exists():
        print(f"Coverage file not found: {args.coverage_xml}", file=sys.stderr)
        return 2

    tree = ET.parse(args.coverage_xml)
    root = tree.getroot()

    offenders: list[str] = []
    for package in root.findall(".//package"):
        for clazz in package.findall("class"):
            name = clazz.get("filename") or clazz.get("name") or "unknown"
            lines = float(clazz.get("line-rate", 0)) * 100
            branches = float(clazz.get("branch-rate", 0)) * 100
            if lines < args.min_lines or branches < args.min_branches:
                offenders.append(
                    f"{name}: lines={lines:.1f}% (<{args.min_lines}%), branches={branches:.1f}% (<{args.min_branches}%)"
                )

    if offenders:
        print("Low coverage detected:", file=sys.stderr)
        for entry in offenders[: args.max_modules]:
            print(f"  - {entry}", file=sys.stderr)
        if len(offenders) > args.max_modules:
            print(f"  ... and {len(offenders) - args.max_modules} more", file=sys.stderr)
        return 1

    print("All modules meet coverage thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
