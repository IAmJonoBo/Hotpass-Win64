"""Evaluate ScanCode license reports against the Hotpass allowlist."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import yaml
from license_expression import Licensing


def _load_policy(path: Path) -> tuple[set[str], set[str], bool]:
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    allowed = {entry.strip() for entry in policy.get("allowed", [])}
    forbidden = {entry.strip() for entry in policy.get("forbidden", [])}
    fail_on_unknown = bool(policy.get("fail_on_unknown", False))
    return allowed, forbidden, fail_on_unknown


def _iter_license_symbols(expressions: Iterable[str]) -> Iterable[str]:
    licensing = Licensing()
    for expression in expressions:
        if not expression:
            continue
        parsed = licensing.parse(expression, simple=True)
        for symbol in parsed.symbols:
            yield symbol.key


def evaluate(report_path: Path, policy_path: Path) -> int:
    allowed, forbidden, fail_on_unknown = _load_policy(policy_path)
    data = json.loads(report_path.read_text(encoding="utf-8"))
    violations: list[str] = []

    for entry in data.get("files", []):
        expressions: set[str] = set()
        for license_record in entry.get("licenses", []):
            expression = license_record.get("spdx_license_expression") or license_record.get(
                "license_expression"
            )
            if expression:
                expressions.add(expression)
        for symbol in _iter_license_symbols(expressions):
            if symbol in forbidden:
                violations.append(f"{entry.get('path')}: forbidden license {symbol}")
            elif symbol not in allowed and fail_on_unknown:
                violations.append(f"{entry.get('path')}: unknown license {symbol}")

    if violations:
        for violation in violations:
            print(violation)
        print(f"Found {len(violations)} license policy violations")
        return 1

    print("ScanCode report satisfies license policy")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Path to ScanCode JSON report",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        required=True,
        help="Path to license allowlist policy",
    )
    args = parser.parse_args(argv)
    return evaluate(args.report, args.policy)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
