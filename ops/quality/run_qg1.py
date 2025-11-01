#!/usr/bin/env python3
"""Run QG-1 (CLI Integrity) checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class CheckResult:
    """Result of an individual integrity check."""

    check_id: str
    description: str
    passed: bool
    message: str
    duration_seconds: float


def _run_command(
    cmd: list[str],
    *,
    timeout: int = 60,
    validator: Callable[[subprocess.CompletedProcess[str]], tuple[bool, str]],
) -> tuple[bool, str, float]:
    """Execute a command and evaluate it with a validator."""
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"Command timed out: {' '.join(cmd)}", time.time() - start
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}", time.time() - start

    passed, message = validator(result)
    return passed, message, time.time() - start


def _check_overview() -> CheckResult:
    """Ensure `hotpass overview` enumerates required commands."""
    required_verbs = {
        "overview",
        "refine",
        "enrich",
        "qa",
        "contracts",
        "setup",
        "net",
        "aws",
        "ctx",
        "env",
    }

    def validator(result: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
        if result.returncode != 0:
            return False, f"`hotpass overview` failed: {result.stderr.strip()}"
        output = result.stdout.lower()
        missing = [verb for verb in required_verbs if verb not in output]
        if missing:
            return False, f"overview missing verbs: {', '.join(missing)}"
        return True, "overview lists all required verbs"

    passed, message, duration = _run_command(
        ["uv", "run", "hotpass", "overview"],
        validator=validator,
    )

    return CheckResult(
        check_id="overview",
        description="`uv run hotpass overview` succeeds and lists core verbs",
        passed=passed,
        message=message,
        duration_seconds=duration,
    )


def _check_command_help(command: str) -> CheckResult:
    """Ensure `hotpass <command> --help` is available."""

    def validator(result: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
        if result.returncode != 0:
            return False, f"{command} --help failed: {result.stderr.strip()}"
        output = result.stdout.lower()
        if command not in output:
            return False, f"{command} --help does not mention '{command}'"
        return True, f"{command} --help available"

    passed, message, duration = _run_command(
        ["uv", "run", "hotpass", command, "--help"],
        validator=validator,
    )

    return CheckResult(
        check_id=f"{command}-help",
        description=f"`uv run hotpass {command} --help` exits successfully",
        passed=passed,
        message=message,
        duration_seconds=duration,
    )


def _check_cli_help() -> CheckResult:
    """Ensure top-level help lists required commands."""
    required_commands = {
        "overview",
        "refine",
        "enrich",
        "qa",
        "contracts",
        "setup",
        "net",
        "aws",
        "ctx",
        "env",
    }

    def validator(result: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
        if result.returncode != 0:
            return False, f"`hotpass --help` failed: {result.stderr.strip()}"
        output = result.stdout.lower()
        missing = [cmd for cmd in required_commands if cmd not in output]
        if missing:
            return False, f"--help missing commands: {', '.join(missing)}"
        return True, "top-level help lists all commands"

    passed, message, duration = _run_command(
        ["uv", "run", "hotpass", "--help"],
        validator=validator,
    )

    return CheckResult(
        check_id="cli-help",
        description="`uv run hotpass --help` lists required commands",
        passed=passed,
        message=message,
        duration_seconds=duration,
    )


def _check_profile_lint() -> CheckResult:
    """Ensure profile linter passes for bundled profiles."""

    def validator(result: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
        if result.returncode != 0:
            output = result.stdout.strip() or result.stderr.strip()
            return False, output or "Profile linter reported failures"

        # Surface the summary lines (Total/Passed/Failed) when available.
        summary = "Profile linter passed"
        for line in reversed(result.stdout.splitlines()):
            if line.startswith("Passed:") or line.startswith("Failed:"):
                summary = line.strip()
                break
        return True, summary

    passed, message, duration = _run_command(
        ["uv", "run", "python", "tools/profile_lint.py"],
        validator=validator,
        timeout=90,
    )

    return CheckResult(
        check_id="profile-lint",
        description="`python tools/profile_lint.py` validates bundled profiles",
        passed=passed,
        message=message,
        duration_seconds=duration,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Hotpass QG-1 (CLI Integrity) checks.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout.",
    )
    return parser


def _format_summary(results: list[CheckResult]) -> dict[str, Any]:
    timestamp = datetime.now(UTC).isoformat()
    passed = all(result.passed for result in results)
    return {
        "gate": "QG-1",
        "name": "CLI Integrity",
        "timestamp": timestamp,
        "passed": passed,
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

    checks = [
        _check_overview(),
        _check_cli_help(),
        *(
            _check_command_help(command)
            for command in (
                "overview",
                "refine",
                "enrich",
                "qa",
                "contracts",
                "setup",
                "net",
                "aws",
                "ctx",
                "env",
            )
        ),
        _check_profile_lint(),
    ]

    summary = _format_summary(checks)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for result in checks:
            status = "PASS" if result.passed else "FAIL"
            print(f"{status}: {result.description}")
            print(f"  {result.message}")
        totals = summary["stats"]
        print(
            f"Completed QG-1 checks: {totals['passed']}/{totals['total_checks']} "
            f"passed in {totals['duration_seconds']:.2f}s",
        )
        print("✓ QG-1 passed" if summary["passed"] else "✗ QG-1 failed")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
