#!/usr/bin/env python3
"""Run QG-5 (Docs & Instructions) validations."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    """Result of a documentation validation check."""

    check_id: str
    description: str
    passed: bool
    message: str
    duration_seconds: float


REQUIRED_TERM_GROUPS = {
    "copilot:profiles": (".github/copilot-instructions.md", ["profile"]),
    "copilot:deterministic": (
        ".github/copilot-instructions.md",
        ["deterministic", "offline"],
    ),
    "copilot:provenance": (".github/copilot-instructions.md", ["provenance", "source"]),
    "agents:profiles": ("AGENTS.md", ["profile", "aviation", "generic"]),
    "agents:deterministic": ("AGENTS.md", ["deterministic", "offline"]),
    "agents:provenance": ("AGENTS.md", ["provenance", "source"]),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Hotpass documentation and instruction checks for QG-5.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary.",
    )
    return parser


def _check_file_exists(path: Path, min_length: int, description: str, check_id: str) -> CheckResult:
    start = time.time()
    if not path.exists():
        return CheckResult(
            check_id=check_id,
            description=description,
            passed=False,
            message=f"Missing required file: {path}",
            duration_seconds=time.time() - start,
        )

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive guard
        return CheckResult(
            check_id=check_id,
            description=description,
            passed=False,
            message=f"Failed to read {path}: {exc}",
            duration_seconds=time.time() - start,
        )

    if len(content.strip()) < min_length:
        return CheckResult(
            check_id=check_id,
            description=description,
            passed=False,
            message=f"{path} is too short (< {min_length} characters)",
            duration_seconds=time.time() - start,
        )

    return CheckResult(
        check_id=check_id,
        description=description,
        passed=True,
        message=f"{path} present with sufficient content",
        duration_seconds=time.time() - start,
    )


def _check_terms(base_path: Path, check_id: str, candidates: list[str]) -> CheckResult:
    start = time.time()
    file_path = base_path
    if not file_path.exists():
        return CheckResult(
            check_id=check_id,
            description=f"Ensure {file_path} references required terminology",
            passed=False,
            message=f"Missing required file for terminology check: {file_path}",
            duration_seconds=time.time() - start,
        )

    content = file_path.read_text(encoding="utf-8").lower()
    matched = any(term in content for term in candidates)
    if not matched:
        return CheckResult(
            check_id=check_id,
            description=f"Ensure {file_path} references required terminology",
            passed=False,
            message=f"{file_path} missing terminology: {', '.join(candidates)}",
            duration_seconds=time.time() - start,
        )

    return CheckResult(
        check_id=check_id,
        description=f"Ensure {file_path} references required terminology",
        passed=True,
        message=f"{file_path} contains required terminology",
        duration_seconds=time.time() - start,
    )


def _check_cli_reference() -> CheckResult:
    start = time.time()
    path = Path("docs/reference/cli.md")
    if not path.exists():
        return CheckResult(
            check_id="cli-reference",
            description="Verify docs/reference/cli.md aligns with CLI verbs",
            passed=False,
            message="docs/reference/cli.md missing",
            duration_seconds=time.time() - start,
        )

    content = path.read_text(encoding="utf-8").lower()
    required_verbs = ["overview", "refine", "enrich", "qa", "contracts"]
    missing = [verb for verb in required_verbs if verb not in content]
    if missing:
        return CheckResult(
            check_id="cli-reference",
            description="Verify docs/reference/cli.md aligns with CLI verbs",
            passed=False,
            message=f"cli.md missing sections for: {', '.join(missing)}",
            duration_seconds=time.time() - start,
        )
    return CheckResult(
        check_id="cli-reference",
        description="Verify docs/reference/cli.md aligns with CLI verbs",
        passed=True,
        message="CLI reference includes core verbs",
        duration_seconds=time.time() - start,
    )


def _build_summary(results: list[CheckResult]) -> dict[str, Any]:
    return {
        "gate": "QG-5",
        "name": "Docs & Instructions",
        "timestamp": datetime.now(UTC).isoformat(),
        "passed": all(result.passed for result in results),
        "stats": {
            "total_checks": len(results),
            "passed": sum(result.passed for result in results),
            "failed": sum(not result.passed for result in results),
            "duration_seconds": sum(result.duration_seconds for result in results),
        },
        "checks": [
            {
                "id": result.check_id,
                "description": result.description,
                "status": "passed" if result.passed else "failed",
                "message": result.message,
                "duration_seconds": result.duration_seconds,
            }
            for result in results
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    checks: list[CheckResult] = []

    checks.append(
        _check_file_exists(
            Path(".github/copilot-instructions.md"),
            min_length=200,
            description="Ensure .github/copilot-instructions.md exists and is populated",
            check_id="copilot-file",
        )
    )
    checks.append(
        _check_file_exists(
            Path("AGENTS.md"),
            min_length=200,
            description="Ensure AGENTS.md exists and is populated",
            check_id="agents-file",
        )
    )
    checks.append(_check_cli_reference())

    for check_id, (relative_path, terms) in REQUIRED_TERM_GROUPS.items():
        checks.append(_check_terms(Path(relative_path), check_id, terms))

    summary = _build_summary(checks)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for result in checks:
            status = "PASS" if result.passed else "FAIL"
            print(f"{status}: {result.description}")
            print(f"  {result.message}")
        stats = summary["stats"]
        print(
            f"Completed QG-5 checks: {stats['passed']}/{stats['total_checks']} "
            f"passed in {stats['duration_seconds']:.2f}s",
        )
        print("✓ QG-5 passed" if summary["passed"] else "✗ QG-5 failed")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
