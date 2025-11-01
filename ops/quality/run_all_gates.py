#!/usr/bin/env python
"""Master quality gate runner for Hotpass.

This script runs all quality gates (QG-1 through QG-5) and generates
a summary report. It can be used locally or in CI.

Usage:
    python ops/quality/run_all_gates.py          # Run all gates
    python ops/quality/run_all_gates.py --gate 1 # Run specific gate
    python ops/quality/run_all_gates.py --json   # JSON output for CI
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TA_ARTIFACT_DIR = Path("dist/quality-gates")
TA_SUMMARY_PATH = TA_ARTIFACT_DIR / "latest-ta.json"
TA_HISTORY_PATH = TA_ARTIFACT_DIR / "history.ndjson"


@dataclass
class GateResult:
    """Result from running a quality gate."""

    gate_id: str
    name: str
    passed: bool
    message: str
    duration_seconds: float


def _summarize_success(payload: dict[str, object] | None) -> str:
    """Build a concise success message from a gate payload."""
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


def _summarize_failure(payload: dict[str, object] | None, fallback: str) -> str:
    """Build a concise failure message from a gate payload."""
    if not isinstance(payload, dict):
        return fallback

    entries = payload.get("steps") or payload.get("checks") or payload.get("results")
    if isinstance(entries, list):
        failures: list[str] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if status in {"failed", "fail", False}:
                identifier = item.get("id") or item.get("checkpoint")
                message = item.get("message") or item.get("detail")
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


def _invoke_gate_script(
    script_rel_path: str,
    gate_id: str,
    gate_name: str,
    *,
    extra_args: list[str] | None = None,
) -> GateResult:
    """Execute a gate script and translate the result into GateResult."""
    import time

    start = time.time()

    try:
        cmd = [
            sys.executable,
            script_rel_path,
            "--json",
        ]
        if extra_args:
            cmd.extend(extra_args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        payload: dict[str, object] | None = None
        stdout = result.stdout.strip()
        if stdout:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = None

        if result.returncode == 0:
            message = _summarize_success(payload)
            return GateResult(
                gate_id=gate_id,
                name=gate_name,
                passed=True,
                message=message,
                duration_seconds=time.time() - start,
            )

        failure_message = result.stderr.strip() or "Gate script reported failure"
        failure_message = _summarize_failure(payload, failure_message)

        return GateResult(
            gate_id=gate_id,
            name=gate_name,
            passed=False,
            message=failure_message,
            duration_seconds=time.time() - start,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return GateResult(
            gate_id=gate_id,
            name=gate_name,
            passed=False,
            message=f"Error running gate script {script_rel_path}: {exc}",
            duration_seconds=time.time() - start,
        )


def run_qg1_cli_integrity() -> GateResult:
    """QG-1: CLI Integrity Gate."""
    return _invoke_gate_script(
        "ops/quality/run_qg1.py",
        "QG-1",
        "CLI Integrity",
    )


def run_qg2_data_quality() -> GateResult:
    """QG-2: Data Quality Gate."""
    return _invoke_gate_script(
        "ops/quality/run_qg2.py",
        "QG-2",
        "Data Quality",
    )


def run_qg3_enrichment_chain() -> GateResult:
    """QG-3: Enrichment Chain Gate."""
    return _invoke_gate_script(
        "ops/quality/run_qg3.py",
        "QG-3",
        "Enrichment Chain",
    )


def run_qg4_mcp_discoverability() -> GateResult:
    """QG-4: MCP Discoverability Gate."""
    return _invoke_gate_script(
        "ops/quality/run_qg4.py",
        "QG-4",
        "MCP Discoverability",
    )


def run_qg5_docs_instruction() -> GateResult:
    """QG-5: Docs/Instruction Gate."""
    return _invoke_gate_script(
        "ops/quality/run_qg5.py",
        "QG-5",
        "Docs/Instructions",
    )


def _build_summary_payload(results: list[GateResult]) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "gates": [
            {
                "id": r.gate_id,
                "name": r.name,
                "passed": r.passed,
                "message": r.message,
                "duration_seconds": r.duration_seconds,
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "all_passed": all(r.passed for r in results),
        },
        "artifact_path": str(TA_SUMMARY_PATH),
    }


def _persist_summary(payload: dict[str, Any]) -> None:
    try:
        TA_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        TA_SUMMARY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        history_record = {
            "timestamp": payload.get("timestamp"),
            "summary": payload.get("summary"),
            "gates": payload.get("gates"),
            "artifact_path": payload.get("artifact_path"),
        }
        with TA_HISTORY_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(history_record))
            handle.write("\n")
    except Exception:  # pragma: no cover - best effort persistence
        pass


def main() -> int:
    """Main entry point for quality gate runner."""
    parser = argparse.ArgumentParser(description="Run Hotpass quality gates")
    parser.add_argument(
        "--gate",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run specific gate only (1-5)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )

    args = parser.parse_args()

    # Define gates to run
    gates = {
        1: ("QG-1: CLI Integrity", run_qg1_cli_integrity),
        2: ("QG-2: Data Quality", run_qg2_data_quality),
        3: ("QG-3: Enrichment Chain", run_qg3_enrichment_chain),
        4: ("QG-4: MCP Discoverability", run_qg4_mcp_discoverability),
        5: ("QG-5: Docs/Instructions", run_qg5_docs_instruction),
    }

    # Run specified gate or all gates
    if args.gate:
        gates_to_run = {args.gate: gates[args.gate]}
    else:
        gates_to_run = gates

    results: list[GateResult] = []

    if not args.json:
        print("=" * 70)
        print("Hotpass Quality Gate Runner")
        print("=" * 70)
        print()

    for _gate_num, (gate_name, gate_func) in gates_to_run.items():
        if not args.json:
            print(f"Running {gate_name}...")

        result = gate_func()
        results.append(result)

        if not args.json:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"  {status}: {result.message}")
            print(f"  Duration: {result.duration_seconds:.2f}s")
            print()

    payload = _build_summary_payload(results)
    _persist_summary(payload)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0 if payload["summary"]["all_passed"] else 1
    else:
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        summary = payload["summary"]
        print(f"Total gates: {summary['total']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Total duration: {sum(r.duration_seconds for r in results):.2f}s")
        print(f"TA Summary: {payload['artifact_path']}")
        print()

        if summary["all_passed"]:
            print("✓ All quality gates passed!")
            return 0
        else:
            print("✗ Some quality gates failed")
            failed = [r for r in results if not r.passed]
            for result in failed:
                print(f"  - {result.gate_id}: {result.message}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
