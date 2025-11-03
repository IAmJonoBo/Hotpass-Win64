"""QA command - run quality assurance checks and validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..utils import run_command

TA_ARTIFACT_PATH = Path("dist/quality-gates/latest-ta.json")
TA_HISTORY_PATH = Path("dist/quality-gates/history.ndjson")


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    """Build the qa command parser."""
    parser = subparsers.add_parser(
        "qa",
        help="Run quality assurance checks and validation",
        description=(
            "Run various quality assurance checks including fitness functions, "
            "profile validation, contract checks, and technical acceptance tests."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "target",
        type=str,
        nargs="?",
        default="all",
        choices=[
            "all",
            "cli",
            "contracts",
            "docs",
            "profiles",
            "ta",
            "fitness",
            "data-quality",
        ],
        help="Which QA checks to run (default: all)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )

    return parser


def register() -> CLICommand:
    return CLICommand(
        name="qa",
        help="Run quality assurance checks and validation",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    """Handle the qa command execution."""
    console = Console()
    _ = profile  # unused but required by interface

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Running QA Checks[/bold cyan]\nTarget: {namespace.target}",
            border_style="cyan",
        )
    )
    console.print()

    results = []
    overall_success = True

    # Get profile name if specified
    profile_name = getattr(namespace, "profile", None)

    # Define QA check runners
    checks_to_run = []

    if namespace.target in ("all", "cli"):
        checks_to_run.append(("CLI Integrity", run_cli_integrity))

    if namespace.target in ("all", "fitness"):
        checks_to_run.append(("Fitness Functions", run_fitness_functions))

    if namespace.target in ("all", "data-quality"):
        checks_to_run.append(("Data Quality (GE)", lambda: run_data_quality(profile_name)))

    if namespace.target in ("all", "profiles"):
        checks_to_run.append(("Profile Validation", lambda: run_profile_validation(profile_name)))

    if namespace.target in ("all", "contracts"):
        checks_to_run.append(("Contract Checks", run_contract_checks))

    if namespace.target in ("all", "docs"):
        checks_to_run.append(("Documentation Checks", run_docs_checks))

    if namespace.target == "ta":
        checks_to_run.append(("Technical Acceptance", run_ta_checks))

    # Run checks
    for check_name, check_func in checks_to_run:
        console.print(f"[cyan]Running:[/cyan] {check_name}")
        success, message = check_func()
        results.append((check_name, success, message))

        if success:
            console.print(f"  [green]✓[/green] {message}")
        else:
            console.print(f"  [red]✗[/red] {message}")
            overall_success = False

        console.print()

    # Display summary table
    table = Table(title="QA Check Results", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Message", style="white")

    for check_name, success, message in results:
        status = "[green]PASS[/green]" if success else "[red]FAIL[/red]"
        table.add_row(check_name, status, message)

    console.print(table)
    console.print()

    if overall_success:
        console.print("[green]✓ All QA checks passed[/green]")
        return 0
    else:
        console.print("[red]✗ Some QA checks failed[/red]")
        return 1


def run_fitness_functions() -> tuple[bool, str]:
    """Run fitness function checks."""
    try:
        command = [sys.executable, "ops/quality/fitness_functions.py"]
        result = run_command(command, check=False, capture_output=True)
        if result.returncode == 0:
            return True, "All fitness functions satisfied"
        else:
            return False, f"Fitness functions failed:\n{result.stdout}"
    except Exception as e:
        return False, f"Error running fitness functions: {e}"


def run_cli_integrity() -> tuple[bool, str]:
    """Run CLI integrity checks (QG-1)."""
    try:
        return _run_gate_script("ops/quality/run_qg1.py")
    except Exception as e:
        return False, f"Error running CLI integrity checks: {e}"


def _summarize_gate_success(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return "Gate completed successfully"

    stats = payload.get("stats")
    summary: str | None = None
    if isinstance(stats, dict):
        total = (
            stats.get("total_checks")
            or stats.get("total_steps")
            or stats.get("total")
            or stats.get("total_items")
        )
        passed = stats.get("passed")
        if isinstance(total, int) and isinstance(passed, int):
            summary = f"{passed}/{total} checks passed"

    artifacts = payload.get("artifacts")
    if isinstance(artifacts, dict):
        artifact_path = (
            artifacts.get("output_workbook")
            or artifacts.get("data_docs")
            or artifacts.get("run_dir")
            or artifacts.get("summary")
        )
        if isinstance(artifact_path, str):
            summary = f"{summary or 'Gate completed successfully'}; artifacts at {artifact_path}"

    data_docs = payload.get("data_docs")
    if isinstance(data_docs, str):
        summary = f"{summary or 'Gate completed successfully'}; Data Docs at {data_docs}"

    return summary or "Gate completed successfully"


def _summarize_gate_failure(payload: dict[str, Any] | None, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback

    entries = payload.get("steps") or payload.get("checks") or payload.get("results")
    if isinstance(entries, list):
        failures: list[str] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if status in {"fail", "failed", False}:
                identifier = item.get("id") or item.get("checkpoint")
                message = item.get("message") or item.get("detail") or item.get("error")
                if identifier and message:
                    failures.append(f"{identifier}: {message}")
                elif message:
                    failures.append(str(message))
        if failures:
            return "; ".join(failures)
    error = payload.get("error")
    if isinstance(error, str):
        return error
    return fallback


def _run_gate_script(
    script_path: str,
    *,
    profile_name: str | None = None,
    extra_args: list[str] | None = None,
) -> tuple[bool, str]:
    """Invoke a gate script and return success flag + summary message."""
    cmd = [sys.executable, script_path, "--json"]
    if profile_name:
        cmd.extend(["--profile", profile_name])
    if extra_args:
        cmd.extend(extra_args)

    result = run_command(cmd, check=False, capture_output=True)

    payload: dict[str, Any] | None = None
    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = None

    if result.returncode == 0:
        return True, _summarize_gate_success(payload)

    failure_message = result.stderr.strip() or "Gate script reported failure"
    failure_message = _summarize_gate_failure(payload, failure_message)
    return False, failure_message


def run_data_quality(profile_name: str | None = None) -> tuple[bool, str]:
    """Run Great Expectations data quality checks."""
    try:
        return _run_gate_script(
            "ops/quality/run_qg2.py",
            profile_name=profile_name,
        )
    except Exception as e:
        return False, f"Error running data quality checks: {e}"


def run_profile_validation(profile_name: str | None = None) -> tuple[bool, str]:
    """Run profile validation checks."""
    try:
        # Check if profile linter exists
        linter_path = Path("tools/profile_lint.py")
        if not linter_path.exists():
            return True, "Profile linter not yet implemented (coming in Sprint 3)"

        # Run profile linter
        cmd = [sys.executable, str(linter_path)]
        if profile_name:
            cmd.extend(["--profile", profile_name])

        result = run_command(cmd, check=False, capture_output=True)

        if result.returncode == 0:
            return True, "All profiles valid"
        else:
            return False, f"Profile validation failed:\n{result.stdout}"
    except Exception as e:
        return False, f"Error running profile validation: {e}"


def run_contract_checks() -> tuple[bool, str]:
    """Run contract checks."""
    try:
        # Check if contract tests exist
        contract_tests = Path("tests/contracts")
        if not contract_tests.exists():
            return True, "No contract tests found (optional)"

        result = run_command(
            [sys.executable, "-m", "pytest", "tests/contracts", "-v"],
            check=False,
            capture_output=True,
        )

        if result.returncode == 0:
            return True, "All contract tests passed"
        else:
            return False, "Some contract tests failed"
    except Exception as e:
        return False, f"Error running contract checks: {e}"


def run_docs_checks() -> tuple[bool, str]:
    """Run documentation checks (QG-5)."""
    try:
        return _run_gate_script("ops/quality/run_qg5.py")
    except Exception as e:
        return False, f"Error checking documentation: {e}"


def run_ta_checks() -> tuple[bool, str]:
    """Run technical acceptance checks (all quality gates)."""
    try:
        cmd = [
            sys.executable,
            "ops/quality/run_all_gates.py",
            "--json",
        ]
        result = run_command(cmd, check=False, capture_output=True)

        payload: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = None

        persisted_path: Path | None = None
        if isinstance(payload, dict):
            persisted_path = _persist_ta_summary(payload)

        if result.returncode == 0 and isinstance(payload, dict):
            summary = payload.get("summary", {})
            gates = payload.get("gates", [])
            total = summary.get("total")
            passed = summary.get("passed")
            if isinstance(total, int) and isinstance(passed, int):
                message = f"Technical Acceptance: {passed}/{total} gates passed"
            else:
                message = "Technical Acceptance gates passed"

            artifact_path: str | None = None
            if persisted_path is not None:
                artifact_path = str(persisted_path)
            else:
                raw_path = payload.get("artifact_path")
                if isinstance(raw_path, str) and raw_path:
                    artifact_path = raw_path
            if artifact_path:
                message = f"{message}; summary saved to {artifact_path}"
            history_path = payload.get("history_path")
            if isinstance(history_path, str) and history_path:
                message = f"{message}; history appended to {history_path}"

            failed_gates: list[str] = []
            for gate in gates if isinstance(gates, list) else []:
                if not isinstance(gate, dict):
                    continue
                if not gate.get("passed"):
                    gate_id = gate.get("id", "unknown")
                    gate_message = gate.get("message") or gate.get("error") or "failed"
                    failed_gates.append(f"{gate_id}: {gate_message}")

            if failed_gates:
                message = f"Technical Acceptance failed: {'; '.join(failed_gates)}"
                return False, message

            return True, message

        failure_message = result.stderr.strip() or "Technical Acceptance checks failed"
        failure_message = _summarize_gate_failure(payload, failure_message)
        return False, failure_message
    except Exception as e:
        return False, f"Error running TA checks: {e}"


def _persist_ta_summary(payload: dict[str, Any]) -> Path | None:
    """Persist the TA summary payload to the shared artifact path."""

    artifact_path_value = payload.get("artifact_path")
    if isinstance(artifact_path_value, str) and artifact_path_value:
        destination: Path = Path(artifact_path_value)
        artifact_from_payload = True
    else:
        destination = TA_ARTIFACT_PATH
        artifact_from_payload = False

    try:
        if not artifact_from_payload:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["artifact_path"] = str(destination)
        if TA_HISTORY_PATH.exists():
            payload.setdefault("history_path", str(TA_HISTORY_PATH))
        return destination
    except Exception:
        return None
