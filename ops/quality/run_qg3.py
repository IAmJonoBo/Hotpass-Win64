#!/usr/bin/env python3
"""Run QG-3 (Enrichment Chain) validations."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_PROVENANCE_COLUMNS = [
    "provenance_source",
    "provenance_timestamp",
    "provenance_confidence",
    "provenance_strategy",
    "provenance_network_status",
]


@dataclass
class StepResult:
    """Result of an individual validation step."""

    step_id: str
    description: str
    passed: bool
    message: str
    duration_seconds: float


def _project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in (current,) + tuple(current.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Unable to locate project root")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute QG-3 enrichment chain validations.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="CLI profile identifier to apply (optional).",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow network-based enrichment (defaults to deterministic-only).",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=_project_root() / "dist" / "quality-gates" / "qg3-enrichment-chain",
        help="Directory where artifacts (input/output) are written.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary.",
    )
    return parser


def _create_sample_workbook(path: Path) -> StepResult:
    """Generate a deterministic sample workbook for enrichment."""
    start = time.time()
    data = {
        "organization_name": ["Test Flight School", "Aerodrome Academy"],
        "contact_email": ["", ""],
        "website": ["", ""],
    }
    df = pd.DataFrame(data)
    try:
        df.to_excel(path, index=False)
        message = f"Sample workbook created at {path}"
        passed = True
    except Exception as exc:  # pragma: no cover - defensive guard
        message = f"Failed to create sample workbook: {exc}"
        passed = False
    return StepResult(
        step_id="prepare-input",
        description="Create deterministic sample workbook",
        passed=passed,
        message=message,
        duration_seconds=time.time() - start,
    )


def _run_enrichment(
    input_path: Path,
    output_path: Path,
    *,
    profile: str,
    allow_network: bool,
) -> StepResult:
    """Run the enrichment CLI with deterministic settings."""
    start = time.time()
    cmd = [
        "uv",
        "run",
        "hotpass",
        "enrich",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        f"--allow-network={'true' if allow_network else 'false'}",
    ]
    if profile:
        cmd.extend(["--profile", profile])

    env = os.environ.copy()
    # Force deterministic/offline run unless explicitly allowed
    env.setdefault("ALLOW_NETWORK_RESEARCH", "false" if not allow_network else "true")
    env.setdefault("FEATURE_ENABLE_REMOTE_RESEARCH", "1" if allow_network else "0")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
            env=env,
        )
    except FileNotFoundError:
        return StepResult(
            step_id="run-enrich",
            description="Run `uv run hotpass enrich`",
            passed=False,
            message="`uv` command not found; ensure uv is installed in the environment",
            duration_seconds=time.time() - start,
        )
    except subprocess.TimeoutExpired:
        return StepResult(
            step_id="run-enrich",
            description="Run `uv run hotpass enrich`",
            passed=False,
            message="Enrichment command timed out after 180 seconds",
            duration_seconds=time.time() - start,
        )

    if result.returncode == 0 and output_path.exists():
        message = f"Enrichment succeeded; output at {output_path}"
        passed = True
    else:
        error_text = result.stderr.strip() or result.stdout.strip()
        message = f"Enrichment failed: {error_text}" if error_text else "Enrichment failed"
        passed = False

    return StepResult(
        step_id="run-enrich",
        description="Run `uv run hotpass enrich` with deterministic settings",
        passed=passed,
        message=message,
        duration_seconds=time.time() - start,
    )


def _validate_output(output_path: Path) -> StepResult:
    """Verify output workbook contains provenance columns."""
    start = time.time()
    if not output_path.exists():
        return StepResult(
            step_id="validate-output",
            description="Validate enriched output workbook",
            passed=False,
            message=f"Output workbook missing at {output_path}",
            duration_seconds=time.time() - start,
        )

    try:
        df = pd.read_excel(output_path)
    except Exception as exc:  # pragma: no cover - defensive guard
        return StepResult(
            step_id="validate-output",
            description="Validate enriched output workbook",
            passed=False,
            message=f"Failed to read enriched workbook: {exc}",
            duration_seconds=time.time() - start,
        )

    missing = [col for col in REQUIRED_PROVENANCE_COLUMNS if col not in df.columns]
    if missing:
        return StepResult(
            step_id="validate-output",
            description="Validate enriched output workbook",
            passed=False,
            message=f"Missing provenance columns: {', '.join(missing)}",
            duration_seconds=time.time() - start,
        )

    return StepResult(
        step_id="validate-output",
        description="Validate enriched output workbook",
        passed=True,
        message="Enriched workbook contains required provenance columns",
        duration_seconds=time.time() - start,
    )


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_summary(
    results: list[StepResult],
    *,
    run_dir: Path,
    input_path: Path,
    output_path: Path,
    allow_network: bool,
    profile: str,
) -> dict[str, Any]:
    passed = all(result.passed for result in results)
    return {
        "gate": "QG-3",
        "name": "Enrichment Chain",
        "timestamp": datetime.now(UTC).isoformat(),
        "passed": passed,
        "artifacts": {
            "run_dir": str(run_dir),
            "input_workbook": str(input_path),
            "output_workbook": str(output_path),
        },
        "configuration": {
            "profile": profile or "default",
            "allow_network": allow_network,
        },
        "stats": {
            "total_steps": len(results),
            "passed": sum(result.passed for result in results),
            "failed": sum(not result.passed for result in results),
            "duration_seconds": sum(result.duration_seconds for result in results),
        },
        "steps": [
            {
                "id": result.step_id,
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

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.artifacts_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    input_path = run_dir / "input.xlsx"
    output_path = run_dir / "enriched.xlsx"

    results: list[StepResult] = []
    prepare_result = _create_sample_workbook(input_path)
    results.append(prepare_result)

    if prepare_result.passed:
        enrich_result = _run_enrichment(
            input_path,
            output_path,
            profile=args.profile,
            allow_network=args.allow_network,
        )
        results.append(enrich_result)
    else:
        enrich_result = None

    if prepare_result.passed and enrich_result and enrich_result.passed:
        results.append(_validate_output(output_path))

    summary = _build_summary(
        results,
        run_dir=run_dir,
        input_path=input_path,
        output_path=output_path,
        allow_network=args.allow_network,
        profile=args.profile,
    )

    _write_summary(run_dir / "summary.json", summary)
    latest_path = args.artifacts_dir / "latest.json"
    _write_summary(latest_path, summary)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for step in results:
            status = "PASS" if step.passed else "FAIL"
            print(f"{status}: {step.description}")
            print(f"  {step.message}")
        totals = summary["stats"]
        print(
            f"Completed QG-3 steps: {totals['passed']}/{totals['total_steps']} "
            f"passed in {totals['duration_seconds']:.2f}s",
        )
        print("✓ QG-3 passed" if summary["passed"] else "✗ QG-3 failed")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
